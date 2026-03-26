from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ocw_workbench.exporters.electrical_exporter import export_electrical_mapping
from ocw_workbench.exporters.assembly_exporter import export_assembly
from ocw_workbench.exporters.bom_exporter import export_bom_csv, export_bom_yaml
from ocw_workbench.exporters.manufacturing_exporter import export_manufacturing
from ocw_workbench.exporters.schematic_exporter import export_schematic
from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.services.constraint_service import ConstraintService
from ocw_workbench.services.electrical_service import ElectricalService
from ocw_workbench.services.layout_service import LayoutService
from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.services.manufacturing_service import ManufacturingService
from ocw_workbench.services.schematic_service import SchematicService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.variant_service import VariantService
from ocw_workbench.utils.yaml_io import dump_yaml, load_yaml


class PipelineRunner:
    def __init__(
        self,
        template_service: TemplateService | None = None,
        variant_service: VariantService | None = None,
        layout_service: LayoutService | None = None,
        constraint_service: ConstraintService | None = None,
        electrical_service: ElectricalService | None = None,
        schematic_service: SchematicService | None = None,
        controller_builder: ControllerBuilder | None = None,
        library_service: LibraryService | None = None,
        manufacturing_service: ManufacturingService | None = None,
    ) -> None:
        self.template_service = template_service or TemplateService()
        self.variant_service = variant_service or VariantService()
        self.layout_service = layout_service or LayoutService()
        self.constraint_service = constraint_service or ConstraintService()
        self.electrical_service = electrical_service or ElectricalService()
        self.schematic_service = schematic_service or SchematicService()
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)
        self.library_service = library_service or LibraryService()
        self.manufacturing_service = manufacturing_service or ManufacturingService()

    def run_full_pipeline(
        self,
        project_config: str | Path | dict[str, Any],
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        config = load_project_config(project_config)
        project_meta = config["project"]
        project_id = project_meta["id"]
        print(f"Running pipeline for {project_id}")

        generated = self._generate_project(config)
        controller = deepcopy(generated["controller"])
        components = deepcopy(generated["components"])
        firmware = self._build_firmware_config(generated, config)
        pipeline_cfg = deepcopy(config.get("pipeline", {}))
        layout_cfg = deepcopy(pipeline_cfg.get("layout", {}))
        constraint_cfg = deepcopy(pipeline_cfg.get("constraints", {}))
        meta = {
            "project_id": project_id,
            "project_name": project_meta.get("name"),
            "source_kind": project_meta["source"]["kind"],
            "source_id": project_meta["source"]["id"],
        }

        layout_result = self.layout_service.place(
            controller,
            components,
            strategy=str(layout_cfg.get("strategy", generated.get("layout", {}).get("strategy", "grid"))),
            config=deepcopy(layout_cfg.get("config", generated.get("layout", {}).get("config", {}))),
        )
        placed_components = deepcopy(layout_result["placed_components"])
        print("Layout applied")

        constraint_report = self.constraint_service.validate(
            controller,
            placed_components,
            config=deepcopy(constraint_cfg.get("config")),
        )
        if not constraint_report["errors"]:
            print("Constraint validation passed")

        geometry = self._build_geometry_snapshot(controller, placed_components)
        print("Geometry snapshot created")

        kicad_layout = self._build_kicad_layout(project_id, controller, placed_components)
        print("KiCad export created")

        electrical_mapping = self.electrical_service.map_controller(
            controller,
            placed_components,
            firmware=firmware,
            meta=meta,
        )
        print("Electrical mapping created")

        schematic = self.schematic_service.build_from_mapping(electrical_mapping)
        print("Schematic export created")

        bom = self.manufacturing_service.build_bom(controller, placed_components)
        manufacturing = self.manufacturing_service.build_manufacturing(controller, placed_components)
        assembly = self.manufacturing_service.build_assembly(controller, placed_components)
        print("Manufacturing exports created")

        output_paths = self._write_outputs(
            project_id=project_meta.get("output_prefix", project_id),
            output_dir=output_dir,
            kicad_layout=kicad_layout,
            electrical_mapping=electrical_mapping,
            schematic=schematic,
            bom=bom,
            manufacturing=manufacturing,
            assembly=assembly,
        )

        warnings = []
        warnings.extend(deepcopy(layout_result.get("warnings", [])))
        warnings.extend(deepcopy(constraint_report.get("warnings", [])))
        warnings.extend(deepcopy(kicad_layout.get("warnings", [])))
        warnings.extend(deepcopy(electrical_mapping.get("warnings", [])))
        warnings.extend(deepcopy(schematic.get("warnings", [])))

        return {
            "project": deepcopy(project_meta),
            "generated_project": generated,
            "controller": controller,
            "layout_result": layout_result,
            "constraint_report": constraint_report,
            "geometry": geometry,
            "kicad_layout": kicad_layout,
            "electrical_mapping": electrical_mapping,
            "schematic": schematic,
            "bom": bom,
            "manufacturing": manufacturing,
            "assembly": assembly,
            "warnings": warnings,
            "output_paths": output_paths,
        }

    def _generate_project(self, config: dict[str, Any]) -> dict[str, Any]:
        project_meta = config["project"]
        source = project_meta["source"]
        overrides = deepcopy(config.get("overrides", {}))

        if source["kind"] == "template":
            return self.template_service.generate_from_template(source["id"], overrides=overrides)
        if source["kind"] == "variant":
            return self.variant_service.generate_from_variant(source["id"], overrides=overrides)
        raise ValueError(f"Unsupported project source kind: {source['kind']}")

    def _build_firmware_config(self, generated: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        firmware = deepcopy(generated.get("firmware", {}))
        project_firmware = deepcopy(config.get("firmware", {}))
        firmware.update(project_firmware)

        io_strategy = firmware.get("io_strategy")
        if isinstance(io_strategy, str):
            firmware["io_strategy"] = {"default": io_strategy}

        defaults = generated.get("defaults", {})
        if "io_strategy" in defaults:
            if "io_strategy" not in firmware:
                default_strategy = defaults["io_strategy"]
                if isinstance(default_strategy, str):
                    firmware["io_strategy"] = {"default": default_strategy}
                elif isinstance(default_strategy, dict):
                    firmware["io_strategy"] = deepcopy(default_strategy)
            elif isinstance(firmware["io_strategy"], dict) and isinstance(defaults["io_strategy"], dict):
                merged = deepcopy(defaults["io_strategy"])
                merged.update(firmware["io_strategy"])
                firmware["io_strategy"] = merged

        return firmware

    def _build_geometry_snapshot(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        surface = self.controller_builder.resolve_surface(controller).to_dict()
        cutouts = self.controller_builder.build_cutout_primitives(components)
        keepouts = self.controller_builder.build_keepouts(components)
        return {
            "surface": surface,
            "cutouts": cutouts,
            "keepouts": keepouts,
        }

    def _build_kicad_layout(
        self,
        project_id: str,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        surface = controller.get("surface", {})
        board = {
            "name": project_id,
            "width_mm": float(surface.get("width", controller["width"])),
            "height_mm": float(surface.get("height", controller["depth"])),
        }
        if surface.get("shape") == "rounded_rect" and surface.get("corner_radius") is not None:
            board["corner_radius_mm"] = float(surface["corner_radius"])

        footprints: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        reference_counts: dict[str, int] = {}

        for component in components:
            library_ref = component.get("library_ref")
            if not isinstance(library_ref, str) or not library_ref:
                warnings.append(
                    {
                        "component_id": component.get("id"),
                        "code": "missing_library_ref",
                        "message": f"Component '{component.get('id', '<unknown>')}' is missing library_ref for KiCad export",
                    }
                )
                continue
            library_component = self.library_service.get(library_ref)
            pcb = library_component.get("pcb", {})
            footprint_name = pcb.get("default_footprint")
            if not isinstance(footprint_name, str) or not footprint_name:
                warnings.append(
                    {
                        "component_id": component["id"],
                        "code": "missing_footprint",
                        "message": f"Skipping component '{component['id']}': no default footprint defined",
                    }
                )
                continue

            component_type = str(component.get("type", "component"))
            prefix = _reference_prefix(component_type)
            reference_counts[prefix] = reference_counts.get(prefix, 0) + 1
            side = str(component.get("side", pcb.get("placement_side", "top"))).lower()
            if side not in {"top", "bottom"}:
                raise ValueError(f"Unknown footprint side for component '{component['id']}': {side}")
            footprints.append(
                {
                    "reference": f"{prefix}{reference_counts[prefix]}",
                    "component_id": component["id"],
                    "footprint": footprint_name,
                    "x_mm": float(component["x"]),
                    "y_mm": float(component["y"]),
                    "rotation_deg": float(component.get("rotation", 0.0) or 0.0),
                    "side": side,
                }
            )

        mounting_holes = [
            {
                "id": hole.get("id", f"mh{index + 1}"),
                "x_mm": float(hole["x"]),
                "y_mm": float(hole["y"]),
                "diameter_mm": float(hole["diameter"]),
            }
            for index, hole in enumerate(controller.get("mounting_holes", []))
        ]

        keepouts = []
        for feature in self.controller_builder.build_keepouts(components):
            entry = {
                "id": f"{feature['component_id']}_{feature['feature']}",
                "component_id": feature["component_id"],
                "type": feature["shape"],
                "x_mm": float(feature["x"]),
                "y_mm": float(feature["y"]),
                "kind": feature["feature"],
            }
            if feature.get("diameter") is not None:
                entry["diameter_mm"] = float(feature["diameter"])
            if feature.get("width") is not None:
                entry["width_mm"] = float(feature["width"])
            if feature.get("height") is not None:
                entry["height_mm"] = float(feature["height"])
            if feature.get("depth") is not None:
                entry["depth_mm"] = float(feature["depth"])
            keepouts.append(entry)

        return {
            "board": board,
            "coordinate_system": {
                "unit": "mm",
                "origin": "top_left",
            },
            "footprints": footprints,
            "mounting_holes": mounting_holes,
            "keepouts": keepouts,
            "warnings": warnings,
        }

    def _write_outputs(
        self,
        project_id: str,
        output_dir: str | Path | None,
        kicad_layout: dict[str, Any],
        electrical_mapping: dict[str, Any],
        schematic: dict[str, Any],
        bom: dict[str, Any],
        manufacturing: dict[str, Any],
        assembly: dict[str, Any],
    ) -> dict[str, str]:
        if output_dir is None:
            return {}

        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        kicad_path = target_dir / f"{project_id}.kicad.layout.yaml"
        electrical_path = target_dir / f"{project_id}.electrical.yaml"
        schematic_path = target_dir / f"{project_id}.schematic.yaml"
        bom_yaml_path = target_dir / f"{project_id}.bom.yaml"
        bom_csv_path = target_dir / f"{project_id}.bom.csv"
        manufacturing_path = target_dir / f"{project_id}.manufacturing.yaml"
        assembly_path = target_dir / f"{project_id}.assembly.yaml"

        dump_yaml(kicad_path, kicad_layout)
        export_electrical_mapping(electrical_mapping, electrical_path)
        export_schematic(schematic, schematic_path)
        export_bom_yaml(bom, bom_yaml_path)
        export_bom_csv(bom, bom_csv_path)
        export_manufacturing(manufacturing, manufacturing_path)
        export_assembly(assembly, assembly_path)
        return {
            "kicad_layout": str(kicad_path),
            "electrical": str(electrical_path),
            "schematic": str(schematic_path),
            "bom_yaml": str(bom_yaml_path),
            "bom_csv": str(bom_csv_path),
            "manufacturing": str(manufacturing_path),
            "assembly": str(assembly_path),
        }


def load_project_config(project_config: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(project_config, (str, Path)):
        payload = load_yaml(project_config)
    elif isinstance(project_config, dict):
        payload = deepcopy(project_config)
    else:
        raise TypeError(f"Unsupported project config representation: {type(project_config)!r}")

    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("Project config is missing required field 'project'")
    project_id = project.get("id")
    name = project.get("name")
    source = project.get("source")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("Project config is missing a valid 'project.id'")
    if not isinstance(name, str) or not name:
        raise ValueError(f"Project '{project_id}' is missing a valid 'project.name'")
    if not isinstance(source, dict):
        raise ValueError(f"Project '{project_id}' is missing required field 'project.source'")
    kind = source.get("kind")
    source_id = source.get("id")
    if kind not in {"template", "variant"}:
        raise ValueError(f"Project '{project_id}' has unsupported source kind: {kind}")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError(f"Project '{project_id}' is missing a valid 'project.source.id'")

    for field in ("overrides", "firmware", "pipeline"):
        if field in payload and not isinstance(payload[field], dict):
            raise ValueError(f"Project '{project_id}' field '{field}' must be a mapping")

    return payload


def run_full_pipeline(
    project_config: str | Path | dict[str, Any],
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    return PipelineRunner().run_full_pipeline(project_config, output_dir=output_dir)


def _reference_prefix(component_type: str) -> str:
    return {
        "encoder": "ENC",
        "button": "BTN",
        "display": "DSP",
        "fader": "FDR",
        "pad": "PAD",
        "rgb_button": "RGB",
    }.get(component_type, "U")
