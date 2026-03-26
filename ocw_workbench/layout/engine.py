from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.constraints.validator import ConstraintValidator
from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.layout.placement import Placement
from ocw_workbench.layout.snap import snap_point
from ocw_workbench.layout.strategies import generate_candidates
from ocw_workbench.layout.zone_layout import inject_zone, resolve_zone


TYPE_PRIORITY = {
    "display": 100,
    "fader": 90,
    "pad": 80,
    "encoder": 70,
    "rgb_button": 60,
    "button": 50,
}


class LayoutEngine:
    def __init__(
        self,
        controller_builder: ControllerBuilder | None = None,
        constraint_validator: ConstraintValidator | None = None,
    ) -> None:
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)
        self.constraint_validator = constraint_validator or ConstraintValidator(self.controller_builder)

    def place(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        strategy: str = "grid",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        controller_data = self._as_dict(controller)
        config_data = deepcopy(config) if config is not None else {}
        grid_mm = float(config_data.get("grid_mm", 1.0))
        blocking_mode = str(config_data.get("placement_blocking_mode", "all"))
        sorted_components = self._sort_components(components)
        placed_components: list[dict[str, Any]] = []
        placements: list[Placement] = []
        warnings: list[dict[str, Any]] = []
        zone_candidate_cache: dict[tuple[str, str], list[tuple[float, float]]] = {}
        zone_candidate_index: dict[tuple[str, str], int] = {}

        for component in sorted_components:
            component_data = self._as_dict(component)
            zone_id = component_data.get("zone_id") or config_data.get("zone_id")
            zone = resolve_zone(controller_data, zone_id)
            zone_controller = inject_zone(controller_data, zone)
            effective_strategy = self._resolve_strategy(strategy, zone_id, controller_data, config_data)
            cache_key = (effective_strategy, str(zone_id))
            if cache_key not in zone_candidate_cache:
                zone_candidate_cache[cache_key] = generate_candidates(effective_strategy, zone, config_data)
                zone_candidate_index[cache_key] = 0

            placed = False
            candidates = zone_candidate_cache[cache_key]
            start_index = zone_candidate_index[cache_key]

            for index in range(start_index, len(candidates)):
                raw_x, raw_y = candidates[index]
                snapped_x, snapped_y = snap_point(raw_x, raw_y, grid_mm)
                candidate_component = deepcopy(component_data)
                candidate_component["x"] = snapped_x
                candidate_component["y"] = snapped_y
                candidate_component["rotation"] = float(candidate_component.get("rotation", 0.0) or 0.0)
                report = self.constraint_validator.validate(zone_controller, placed_components + [candidate_component], config=config_data)
                if self._has_blocking_findings(report, candidate_component["id"], blocking_mode):
                    continue

                placed_components.append(candidate_component)
                placements.append(
                    Placement(
                        component_id=candidate_component["id"],
                        x=snapped_x,
                        y=snapped_y,
                        rotation=float(candidate_component.get("rotation", 0.0) or 0.0),
                        zone_id=zone_id,
                    )
                )
                zone_candidate_index[cache_key] = index + 1
                placed = True
                break

            if not placed:
                warnings.append(
                    {
                        "component_id": component_data["id"],
                        "code": "placement_failed",
                        "message": f"Unable to place component '{component_data['id']}' with strategy '{effective_strategy}'",
                    }
                )

        validation = self.constraint_validator.validate(controller_data, placed_components, config=config_data).to_dict()
        warnings.extend(validation["warnings"])
        return {
            "placements": [placement.to_dict() for placement in placements],
            "placed_components": placed_components,
            "unplaced_component_ids": [
                self._as_dict(component)["id"]
                for component in sorted_components
                if self._as_dict(component)["id"] not in {placement.component_id for placement in placements}
            ],
            "warnings": warnings,
            "validation": validation,
        }

    def _sort_components(self, components: list[dict[str, Any] | Any]) -> list[dict[str, Any]]:
        resolved = self.controller_builder.resolve_components(components)
        areas = {
            component["id"]: self._component_area(component)
            for component in resolved
        }
        type_lookup = {component["id"]: component["type"] for component in resolved}
        component_dicts = [self._as_dict(component) for component in components]
        return sorted(
            component_dicts,
            key=lambda item: (
                -TYPE_PRIORITY.get(type_lookup.get(item["id"], item.get("type", "")), 0),
                -areas.get(item["id"], 0.0),
                item["id"],
            ),
        )

    def _component_area(self, resolved_component: dict[str, Any]) -> float:
        keepout = resolved_component["resolved_mechanical"].keepout_top
        if keepout.shape == "circle":
            radius = (keepout.diameter or 0.0) / 2.0
            return 3.14159 * radius * radius
        return float(keepout.width or 0.0) * float(keepout.height or 0.0)

    def _resolve_strategy(
        self,
        default_strategy: str,
        zone_id: str | None,
        controller: dict[str, Any],
        config: dict[str, Any],
    ) -> str:
        if zone_id is not None:
            for zone in controller.get("layout_zones", []):
                if isinstance(zone, dict) and zone.get("id") == zone_id and isinstance(zone.get("strategy"), str):
                    return zone["strategy"]
        if default_strategy == "zone":
            return "grid"
        if isinstance(config.get("strategy"), str):
            return config["strategy"]
        return default_strategy

    def _has_blocking_findings(self, report: Any, component_id: str, blocking_mode: str) -> bool:
        blocking_rules = None
        if blocking_mode == "cutout_surface":
            blocking_rules = {
                "inside_surface_component",
                "inside_surface_keepout",
                "inside_surface_cutout",
                "edge_distance",
                "cutout_spacing",
                "mounting_hole_clearance",
            }
        for finding in report.errors:
            if blocking_rules is not None and finding.rule_id not in blocking_rules:
                continue
            if finding.source_component == component_id or finding.affected_component == component_id:
                return True
        return False

    def _as_dict(self, value: dict[str, Any] | Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if hasattr(value, "__dict__"):
            return deepcopy(vars(value))
        raise TypeError(f"Unsupported value representation: {type(value)!r}")
