from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.services.manufacturing_service import ManufacturingService
from ocw_workbench.services.plugin_service import get_plugin_service, reset_plugin_service


class ExportPluginService:
    def __init__(
        self,
        manufacturing_service: ManufacturingService | None = None,
        library_service: LibraryService | None = None,
        controller_builder: ControllerBuilder | None = None,
    ) -> None:
        self.manufacturing_service = manufacturing_service or ManufacturingService()
        self.library_service = library_service or LibraryService()
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)

    def list_exporters(self) -> list[str]:
        return sorted(self._exporters())

    def export(self, exporter_id: str, project: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
        exporters = self._exporters()
        if exporter_id not in exporters:
            raise KeyError(f"Unknown exporter id: {exporter_id}")
        payload = self.build_payload(project)
        result = exporters[exporter_id](payload, str(output_path))
        return result if isinstance(result, dict) else {"output_path": str(output_path), "warnings": payload["warnings"]}

    def build_payload(self, project: dict[str, Any]) -> dict[str, Any]:
        controller, components = self._resolve_project(project)
        bom = deepcopy(project.get("bom")) if isinstance(project.get("bom"), dict) else self.manufacturing_service.build_bom(controller, components)
        manufacturing = (
            deepcopy(project.get("manufacturing"))
            if isinstance(project.get("manufacturing"), dict)
            else self.manufacturing_service.build_manufacturing(controller, components)
        )
        assembly = (
            deepcopy(project.get("assembly"))
            if isinstance(project.get("assembly"), dict)
            else self.manufacturing_service.build_assembly(controller, components)
        )
        component_records, warnings = self._component_records(components)
        surface = self.controller_builder.resolve_surface(controller).to_dict()
        cutouts = self.controller_builder.build_cutout_primitives(components)
        keepouts = self.controller_builder.build_keepouts(components)
        return {
            "controller": deepcopy(controller),
            "components": deepcopy(components),
            "bom": bom,
            "manufacturing": manufacturing,
            "assembly": assembly,
            "geometry": {
                "surface": surface,
                "cutouts": cutouts,
                "keepouts": keepouts,
            },
            "component_records": component_records,
            "warnings": warnings + deepcopy(bom.get("warnings", [])) + deepcopy(manufacturing.get("warnings", [])),
        }

    def _resolve_project(self, project: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        controller = project.get("controller")
        components = project.get("components")
        if isinstance(controller, dict) and isinstance(components, list):
            return deepcopy(controller), deepcopy(components)
        generated = project.get("generated_project")
        if isinstance(generated, dict):
            controller = generated.get("controller")
            components = generated.get("components")
            if isinstance(controller, dict) and isinstance(components, list):
                return deepcopy(controller), deepcopy(components)
        raise ValueError("Export project payload must contain 'controller' and 'components'")

    def _component_records(self, components: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        reference_counts: dict[str, int] = defaultdict(int)
        records: list[dict[str, Any]] = []
        for component in components:
            component_type = str(component.get("type", "component"))
            prefix = _reference_prefix(component_type)
            reference_counts[prefix] += 1
            record = {
                "component_id": component.get("id"),
                "type": component_type,
                "library_ref": component.get("library_ref"),
                "designator": f"{prefix}{reference_counts[prefix]}",
                "x_mm": float(component.get("x", 0.0) or 0.0),
                "y_mm": float(component.get("y", 0.0) or 0.0),
                "rotation_deg": float(component.get("rotation", 0.0) or 0.0),
                "library_item": None,
            }
            library_ref = component.get("library_ref")
            if isinstance(library_ref, str) and library_ref:
                try:
                    library_item = self.library_service.get(library_ref)
                    record["library_item"] = library_item
                    record["footprint"] = library_item.get("pcb", {}).get("default_footprint")
                except Exception:
                    warnings.append(f"Missing library data for component '{library_ref}'")
                    record["footprint"] = None
            else:
                warnings.append(f"Component '{component.get('id', '<unknown>')}' is missing library_ref")
                record["footprint"] = None
            records.append(record)
        return records, warnings

    def _exporters(self) -> dict[str, Any]:
        exporters = get_plugin_service().exporters()
        if {"jlcpcb", "mouser_bom", "eurorack_panel", "svg_panel"} <= set(exporters):
            return exporters
        reset_plugin_service()
        return get_plugin_service().exporters()


def _reference_prefix(component_type: str) -> str:
    return {
        "encoder": "ENC",
        "button": "BTN",
        "display": "DSP",
        "fader": "FDR",
        "pad": "PAD",
        "rgb_button": "RGB",
    }.get(component_type, "U")
