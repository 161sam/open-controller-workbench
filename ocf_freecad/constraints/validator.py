from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.constraints.ergonomics import ergonomic_proximity_warning, ergonomic_type_warning
from ocf_freecad.constraints.models import ComponentArea
from ocf_freecad.constraints.report import ConstraintReport
from ocf_freecad.constraints.rules import (
    merge_constraint_config,
    validate_edge_distance,
    validate_inside_surface,
    validate_mounting_hole_overlap,
    validate_spacing,
)
from ocf_freecad.generator.controller_builder import ControllerBuilder


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

        component_areas = [
            self._area_from_shape(
                component_id=item["id"],
                component_type=item["type"],
                x=item["x"],
                y=item["y"],
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
            width=_optional_float(feature.get("width")),
            height=_optional_float(feature.get("height")),
            diameter=_optional_float(feature.get("diameter")),
            depth=_optional_float(feature.get("depth")),
        )

    def _area_from_shape(self, component_id: str, component_type: str, x: float, y: float, shape: Any) -> ComponentArea:
        return ComponentArea(
            component_id=component_id,
            component_type=component_type,
            x=float(x),
            y=float(y),
            shape=shape.shape,
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
