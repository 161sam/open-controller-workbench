from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.constraints.ergonomics import ergonomic_proximity_warning, ergonomic_type_warning
from ocw_workbench.constraints.models import ComponentArea, ConstraintFinding
from ocw_workbench.constraints.report import ConstraintReport
from ocw_workbench.constraints.rules import (
    merge_constraint_config,
    validate_edge_distance,
    validate_inside_surface,
    validate_mounting_hole_overlap,
    validate_spacing,
)
from ocw_workbench.generator.controller_builder import ControllerBuilder


class ConstraintValidator:
    def __init__(self, controller_builder: ControllerBuilder | None = None) -> None:
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)

    def validate(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        config: dict[str, Any] | None = None,
    ) -> ConstraintReport:
        report = ConstraintReport()
        controller_data = self._as_dict(controller)
        cfg = merge_constraint_config(config)
        surface = self.controller_builder.resolve_surface(controller_data)
        resolved_components = self.controller_builder.resolve_components(components)
        keepouts = self.controller_builder.build_keepouts(components)
        cutouts = self.controller_builder.build_cutout_primitives(components)
        pcb_reference = self.controller_builder.describe_pcb_reference(controller_data)

        component_areas = [
            self._area_from_shape(
                component_id=item["id"],
                component_type=item["type"],
                x=item["x"],
                y=item["y"],
                rotation=float(item.get("rotation", 0.0) or 0.0),
                shape=item["resolved_mechanical"].keepout_top,
            )
            for item in resolved_components
        ]
        keepout_areas = [
            self._area_from_feature(feature, component_lookup=resolved_components)
            for feature in keepouts
        ]
        cutout_areas = [
            self._area_from_feature(feature, component_lookup=resolved_components)
            for feature in cutouts
        ]
        bottom_keepout_areas = [
            self._area_from_feature(feature, component_lookup=resolved_components)
            for feature in keepouts
            if str(feature.get("feature")) == "keepout_bottom"
        ]

        for area in component_areas:
            finding = validate_inside_surface(surface, area, "inside_surface_component", "component")
            if finding is not None:
                report.add(finding)
            edge_min = cfg["edge_distance_by_type_mm"].get(area.component_type, cfg["default_edge_distance_mm"])
            finding = validate_edge_distance(surface, area, edge_min)
            if finding is not None:
                report.add(finding)

        for area in keepout_areas:
            finding = validate_inside_surface(surface, area, "inside_surface_keepout", "keepout")
            if finding is not None:
                report.add(finding)

        for area in cutout_areas:
            finding = validate_inside_surface(surface, area, "inside_surface_cutout", "cutout")
            if finding is not None:
                report.add(finding)

        pcb_surface = self._surface_from_mapping(pcb_reference.get("surface"))
        if pcb_surface is not None:
            for area in bottom_keepout_areas:
                finding = validate_inside_surface(pcb_surface, area, "component_pcb_clearance", "pcb support area")
                if finding is not None:
                    report.add(
                        ConstraintFinding(
                            severity="warning",
                            rule_id="component_pcb_clearance",
                            message=f"Component '{area.component_id}' extends beyond the current PCB support area",
                            source_component=area.component_id,
                            details=finding.details,
                        )
                    )

        for finding in self._validate_pcb_stack(controller_data, pcb_reference):
            report.add(finding)

        self._validate_pairwise_spacing(component_areas, cfg["min_component_spacing_mm"], "component_spacing", "Component spacing", report)
        self._validate_pairwise_spacing(keepout_areas, cfg["min_keepout_spacing_mm"], "keepout_spacing", "Keepout spacing", report)
        self._validate_pairwise_spacing(cutout_areas, cfg["min_cutout_spacing_mm"], "cutout_spacing", "Cutout spacing", report)

        for area in component_areas:
            for mounting_hole in controller_data.get("mounting_holes", []):
                normalized_hole = self._normalize_mounting_hole(mounting_hole)
                finding = validate_mounting_hole_overlap(area, normalized_hole, cfg["mounting_hole_clearance_mm"])
                if finding is not None:
                    report.add(finding)

        self._validate_ergonomics(component_areas, cfg["ergonomic"], report)
        return report

    def _validate_pairwise_spacing(
        self,
        areas: list[ComponentArea],
        min_spacing_mm: float,
        rule_id: str,
        label: str,
        report: ConstraintReport,
    ) -> None:
        for index, first in enumerate(areas):
            for second in areas[index + 1 :]:
                if first.component_id == second.component_id:
                    continue
                finding = validate_spacing(first, second, min_spacing_mm, rule_id, label)
                if finding is not None:
                    report.add(finding)

    def _validate_ergonomics(
        self,
        areas: list[ComponentArea],
        ergonomic_cfg: dict[str, Any],
        report: ConstraintReport,
    ) -> None:
        tall_types = set(ergonomic_cfg.get("tall_control_types", []))
        for index, first in enumerate(areas):
            for second in areas[index + 1 :]:
                finding = ergonomic_proximity_warning(
                    first,
                    second,
                    ergonomic_cfg["min_control_spacing_mm"],
                )
                if finding is not None:
                    report.add(finding)

                if {first.component_type, second.component_type} == {"fader", "button"}:
                    finding = ergonomic_type_warning(
                        first,
                        second,
                        "ergonomic_fader_button_proximity",
                        (
                            f"Fader '{first.component_id}' and button '{second.component_id}' are too close "
                            "for comfortable operation"
                        ),
                        ergonomic_cfg["fader_button_spacing_mm"],
                    )
                    if finding is not None:
                        report.add(finding)

                if (
                    (first.component_type == "display" and second.component_type in tall_types)
                    or (second.component_type == "display" and first.component_type in tall_types)
                ):
                    finding = ergonomic_type_warning(
                        first,
                        second,
                        "ergonomic_display_clearance",
                        (
                            f"Display '{first.component_id if first.component_type == 'display' else second.component_id}' "
                            "is too close to a tall control"
                        ),
                        ergonomic_cfg["display_tall_control_spacing_mm"],
                    )
                    if finding is not None:
                        report.add(finding)

    def _area_from_feature(self, feature: dict[str, Any], component_lookup: list[dict[str, Any]]) -> ComponentArea:
        component_type = next(
            item["type"]
            for item in component_lookup
            if item["id"] == feature["component_id"]
        )
        return ComponentArea(
            component_id=feature["component_id"],
            component_type=component_type,
            x=float(feature["x"]),
            y=float(feature["y"]),
            shape=str(feature["shape"]),
            rotation=float(feature.get("rotation", 0.0) or 0.0),
            width=_optional_float(feature.get("width")),
            height=_optional_float(feature.get("height")),
            diameter=_optional_float(feature.get("diameter")),
            depth=_optional_float(feature.get("depth")),
        )

    def _area_from_shape(self, component_id: str, component_type: str, x: float, y: float, rotation: float, shape: Any) -> ComponentArea:
        return ComponentArea(
            component_id=component_id,
            component_type=component_type,
            x=float(x),
            y=float(y),
            shape=shape.shape,
            rotation=float(rotation or 0.0),
            width=shape.width,
            height=shape.height,
            diameter=shape.diameter,
            depth=shape.depth,
        )

    def _normalize_mounting_hole(self, hole: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(hole, dict):
            raise ValueError(f"Invalid mounting hole definition: {hole!r}")
        return {
            "id": hole.get("id", "mounting_hole"),
            "x": float(hole["x"]),
            "y": float(hole["y"]),
            "diameter": float(hole["diameter"]),
        }

    def _surface_from_mapping(self, payload: Any) -> Any | None:
        if not isinstance(payload, dict):
            return None
        shape = str(payload.get("shape") or "")
        if shape == "rectangle":
            return self.controller_builder.resolve_surface({"width": payload["width"], "depth": payload["height"], "surface": payload})
        if shape == "rounded_rect":
            return self.controller_builder.resolve_surface({"width": payload["width"], "depth": payload["height"], "surface": payload})
        return None

    def _validate_pcb_stack(self, controller_data: dict[str, Any], pcb_reference: dict[str, Any]) -> list[Any]:
        findings: list[ConstraintFinding] = []
        body_height = self.controller_builder.plan_body_build(controller_data).body_height
        pcb_z = float(pcb_reference.get("z", 0.0) or 0.0)
        pcb_top_z = float(pcb_reference.get("top_z", 0.0) or 0.0)
        if pcb_z < float(controller_data.get("bottom_thickness", 0.0) or 0.0):
            findings.append(
                ConstraintFinding(
                    severity="error",
                    rule_id="pcb_body_clearance",
                    message="PCB plane intersects the controller floor",
                    details={"pcb_z": round(pcb_z, 3), "bottom_thickness": float(controller_data.get("bottom_thickness", 0.0) or 0.0)},
                )
            )
        if pcb_top_z >= body_height:
            findings.append(
                ConstraintFinding(
                    severity="error",
                    rule_id="pcb_body_clearance",
                    message="PCB stack is too tall for the controller body cavity",
                    details={"pcb_top_z": round(pcb_top_z, 3), "body_height": round(body_height, 3)},
                )
            )
        return findings

    def _as_dict(self, value: dict[str, Any] | Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if hasattr(value, "__dict__"):
            return deepcopy(vars(value))
        raise TypeError(f"Unsupported controller representation: {type(value)!r}")


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
