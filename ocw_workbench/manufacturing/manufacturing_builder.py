from __future__ import annotations

from collections import Counter
from typing import Any

from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.manufacturing.models import ManufacturingOperation, ManufacturingPart
from ocw_workbench.manufacturing.normalizer import normalize_profile, recommend_process


class ManufacturingBuilder:
    def __init__(self, controller_builder: ControllerBuilder | None = None) -> None:
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)

    def build(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_profile(profile)
        surface = self.controller_builder.resolve_surface(controller).to_dict()
        cutouts = self.controller_builder.build_cutout_primitives(components)
        keepouts = self.controller_builder.build_keepouts(components)
        warnings: list[str] = []

        top_operations = self._top_plate_operations(cutouts, controller, normalized)
        top_part = self._part(
            part_id="top_plate",
            name="Top Plate",
            part_type="panel",
            width=float(surface["width"]),
            height=float(surface["height"]),
            thickness_mm=float(normalized["materials"]["top_plate"]["thickness_mm"]),
            material=str(normalized["materials"]["top_plate"]["material"]),
            operations=top_operations,
        )

        depth = float(controller.get("depth", surface["height"]))
        height = float(controller.get("height", 30.0))
        bottom_part = self._part(
            part_id="bottom_plate",
            name="Bottom Plate",
            part_type="panel",
            width=float(surface["width"]),
            height=float(surface["height"]),
            thickness_mm=float(normalized["materials"]["bottom_plate"]["thickness_mm"]),
            material=str(normalized["materials"]["bottom_plate"]["material"]),
            operations=self._mounting_hole_operations(controller, normalized, part_id="bottom_plate"),
        )
        side_parts = [
            self._part("left_side", "Left Side", "side_panel", depth, height, float(normalized["materials"]["side_panels"]["thickness_mm"]), str(normalized["materials"]["side_panels"]["material"]), []),
            self._part("right_side", "Right Side", "side_panel", depth, height, float(normalized["materials"]["side_panels"]["thickness_mm"]), str(normalized["materials"]["side_panels"]["material"]), []),
            self._part("front_panel", "Front Panel", "side_panel", float(surface["width"]), height, float(normalized["materials"]["side_panels"]["thickness_mm"]), str(normalized["materials"]["side_panels"]["material"]), []),
            self._part("back_panel", "Back Panel", "side_panel", float(surface["width"]), height, float(normalized["materials"]["side_panels"]["thickness_mm"]), str(normalized["materials"]["side_panels"]["material"]), []),
        ]
        materials = [
            {"part_id": part.part_id, "material": part.material, "thickness_mm": part.thickness_mm}
            for part in [top_part, bottom_part] + side_parts
        ]
        recommended_processes = {
            part.part_id: part.process_recommendation
            for part in [top_part, bottom_part] + side_parts
        }
        panel_operations = [item.to_dict() for item in top_operations + bottom_part.operations]

        return {
            "schema_version": normalized["schema_version"],
            "export_type": "manufacturing",
            "meta": {"part_count": 2 + len(side_parts), "component_count": len(components)},
            "controller": {"id": controller.get("id", "controller"), "surface": surface},
            "materials": materials,
            "parts": [part.to_dict() for part in [top_part, bottom_part] + side_parts],
            "panel_operations": panel_operations,
            "cutouts": cutouts,
            "holes": [item.to_dict() for item in self._mounting_hole_operations(controller, normalized, part_id="top_plate")],
            "recommended_processes": recommended_processes,
            "assembly_notes": [
                "Mount panel-mounted controls before installing the PCB.",
                "Verify display window dimensions against the selected module.",
            ],
            "warnings": warnings,
            "keepouts": keepouts,
        }

    def _part(
        self,
        part_id: str,
        name: str,
        part_type: str,
        width: float,
        height: float,
        thickness_mm: float,
        material: str,
        operations: list[ManufacturingOperation],
    ) -> ManufacturingPart:
        counts = Counter(operation.type for operation in operations)
        return ManufacturingPart(
            part_id=part_id,
            name=name,
            type=part_type,
            dimensions_mm={"width": width, "height": height},
            thickness_mm=thickness_mm,
            material=material,
            process_recommendation=recommend_process(material, part_type, has_complex_cutouts=bool(operations)),
            operation_summary=dict(counts),
            operations=operations,
        )

    def _top_plate_operations(
        self,
        cutouts: list[dict[str, Any]],
        controller: dict[str, Any],
        profile: dict[str, Any],
    ) -> list[ManufacturingOperation]:
        operations: list[ManufacturingOperation] = []
        tolerance_circle = float(profile["tolerances"]["circular_hole_mm"])
        tolerance_rect = float(profile["tolerances"]["rect_cutout_mm"])
        for feature in cutouts:
            shape = str(feature["shape"])
            op_type = "circular_hole" if shape == "circle" else "rectangular_cutout"
            dims = {"diameter_mm": float(feature["diameter"])} if shape == "circle" else {
                "width_mm": float(feature["width"]),
                "height_mm": float(feature["height"]),
            }
            operations.append(
                ManufacturingOperation(
                    operation_id=f"op:top:{feature['component_id']}:cutout",
                    part_id="top_plate",
                    type=op_type,
                    shape=shape,
                    position={"x_mm": float(feature["x"]), "y_mm": float(feature["y"])},
                    dimensions=dims,
                    source_component_id=feature["component_id"],
                    tolerance_mm=tolerance_circle if shape == "circle" else tolerance_rect,
                    notes="Derived from component panel cutout",
                )
            )
        operations.extend(self._mounting_hole_operations(controller, profile, part_id="top_plate"))
        return operations

    def _mounting_hole_operations(
        self,
        controller: dict[str, Any],
        profile: dict[str, Any],
        part_id: str,
    ) -> list[ManufacturingOperation]:
        tolerance = float(profile["tolerances"]["circular_hole_mm"])
        operations: list[ManufacturingOperation] = []
        for index, hole in enumerate(controller.get("mounting_holes", [])):
            operations.append(
                ManufacturingOperation(
                    operation_id=f"op:{part_id}:mounting:{index + 1}",
                    part_id=part_id,
                    type="mounting_hole",
                    shape="circle",
                    position={"x_mm": float(hole["x"]), "y_mm": float(hole["y"])},
                    dimensions={"diameter_mm": float(hole["diameter"])},
                    tolerance_mm=tolerance,
                    notes="Controller mounting hole",
                )
            )
        return operations
