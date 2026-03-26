from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import logging
from typing import Any

from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.gui.overlay.colors import overlay_style
from ocw_workbench.gui.overlay.labels import component_label, issue_label, zone_label
from ocw_workbench.gui.overlay.shapes import circle_item, rect_item, slot_item, text_item
from ocw_workbench.services.constraint_overlay_service import ConstraintOverlayService
from ocw_workbench.services.constraint_service import ConstraintService
from ocw_workbench.services.controller_service import ControllerService

LOGGER = logging.getLogger(__name__)


class OverlayService:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        constraint_service: ConstraintService | None = None,
        controller_builder: ControllerBuilder | None = None,
        constraint_overlay_service: ConstraintOverlayService | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.constraint_service = constraint_service or ConstraintService()
        self.controller_builder = controller_builder or ControllerBuilder(doc=None)
        self.constraint_overlay_service = constraint_overlay_service or ConstraintOverlayService()

    def build_overlay(self, doc: Any) -> dict[str, Any]:
        state = self.controller_service.get_state(doc)
        context = self.controller_service.get_ui_context(doc)
        settings = deepcopy(context.get("ui", {}))
        if not settings.get("overlay_enabled", True):
            return {"enabled": False, "items": [], "summary": {"item_count": 0}}

        controller_data = deepcopy(state["controller"])
        components = deepcopy(state["components"])
        surface = self.controller_builder.resolve_surface(controller_data)
        resolved_components = self.controller_builder.resolve_components(components)
        keepouts = self.controller_builder.build_keepouts(components)
        cutouts = self.controller_builder.build_cutout_primitives(components)
        validation = context.get("validation")
        if not isinstance(validation, dict):
            validation = self.constraint_service.validate(controller_data, components)

        selected_component_id = context.get("selection")
        move_component_id = settings.get("move_component_id")
        findings_by_component = self._group_findings(validation)
        items: list[dict[str, Any]] = []
        items.append(
            rect_item(
                item_id="surface",
                x=surface.width / 2.0,
                y=surface.height / 2.0,
                width=surface.width,
                height=surface.height,
                style=overlay_style("surface"),
                label="Surface",
            )
        )

        for zone in controller_data.get("layout_zones", []):
            if not isinstance(zone, dict):
                continue
            zone_id = str(zone.get("id", "zone"))
            items.append(
                rect_item(
                    item_id=f"zone:{zone_id}",
                    x=float(zone["x"]) + (float(zone["width"]) / 2.0),
                    y=float(zone["y"]) + (float(zone["height"]) / 2.0),
                    width=float(zone["width"]),
                    height=float(zone["height"]),
                    style=overlay_style("zone"),
                    label=zone_label(zone),
                )
            )

        for hole in controller_data.get("mounting_holes", []):
            if not isinstance(hole, dict):
                continue
            diameter = float(hole["diameter"])
            hole_id = str(hole.get("id", "mounting_hole"))
            items.append(
                circle_item(
                    item_id=f"mounting_hole:{hole_id}",
                    x=float(hole["x"]),
                    y=float(hole["y"]),
                    diameter=diameter,
                    style=overlay_style("mounting_hole"),
                    label=hole_id,
                )
            )

        for component in resolved_components:
            severity = self._component_severity(findings_by_component, component["id"])
            item_kind = "component_selected" if component["id"] == selected_component_id else "component"
            if severity == "error":
                item_kind = "component_error"
            elif severity == "warning":
                item_kind = "component_warning" if component["id"] != selected_component_id else "component_selected"
            shape = component["resolved_mechanical"].keepout_top
            items.append(
                self._shape_item(
                    prefix="component",
                    item_id=component["id"],
                    x=float(component["x"]),
                    y=float(component["y"]),
                    rotation=float(component.get("rotation", 0.0) or 0.0),
                    shape=shape.to_dict(),
                    style=overlay_style(item_kind),
                    label=component_label(component, severity=severity),
                    source_component_id=component["id"],
                    severity=severity,
                )
            )

        for feature in keepouts:
            items.append(
                self._shape_item(
                    prefix=feature["feature"],
                    item_id=feature["component_id"],
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style("keepout"),
                    source_component_id=feature["component_id"],
                )
            )

        for feature in cutouts:
            items.append(
                self._shape_item(
                    prefix="cutout",
                    item_id=feature["component_id"],
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style("cutout"),
                    source_component_id=feature["component_id"],
                )
            )

        if settings.get("show_constraints", True):
            if settings.get("constraint_labels_enabled", True):
                items.extend(self._constraint_items(resolved_components, findings_by_component))
            constraint_overlay = self.constraint_overlay_service.build(
                surface=surface.to_dict(),
                resolved_components=resolved_components,
                keepouts=keepouts,
                mounting_holes=controller_data.get("mounting_holes", []),
                validation=validation,
                settings=settings,
                selected_component_id=selected_component_id,
                move_component_id=move_component_id,
            )
            items.extend(constraint_overlay["items"])

        return {
            "enabled": True,
            "surface": surface.to_dict(),
            "controller_height": float(controller_data.get("height", 0.0)),
            "items": items,
            "validation": validation,
            "summary": {
                "item_count": len(items),
                "component_count": len(resolved_components),
                "zone_count": len(controller_data.get("layout_zones", [])),
                "finding_count": validation["summary"]["total_count"],
            },
        }

    def _constraint_items(
        self,
        resolved_components: list[dict[str, Any]],
        findings_by_component: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        component_lookup = {component["id"]: component for component in resolved_components}
        for component_id, findings in findings_by_component.items():
            component = component_lookup.get(component_id)
            if component is None:
                continue
            error_count = sum(1 for finding in findings if finding["severity"] == "error")
            warning_count = sum(1 for finding in findings if finding["severity"] != "error")
            if error_count == 0 and warning_count == 0:
                continue
            label = issue_label(component_id, error_count=error_count, warning_count=warning_count)
            items.append(
                text_item(
                    item_id=f"finding:{component_id}",
                    x=float(component["x"]),
                    y=float(component["y"]),
                    text=label,
                    style=overlay_style("finding_label"),
                    source_component_id=component_id,
                    severity="error" if error_count else "warning",
                )
            )
        return items

    def _component_severity(
        self,
        findings_by_component: dict[str, list[dict[str, Any]]],
        component_id: str,
    ) -> str | None:
        findings = findings_by_component.get(component_id, [])
        if any(finding["severity"] == "error" for finding in findings):
            return "error"
        if findings:
            return "warning"
        return None

    def _group_findings(self, validation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for finding in validation.get("errors", []) + validation.get("warnings", []):
            source = finding.get("source_component")
            affected = finding.get("affected_component")
            if isinstance(source, str):
                grouped[source].append(finding)
            if isinstance(affected, str) and not affected.startswith("mounting_hole"):
                grouped[affected].append(finding)
        return grouped

    def _shape_item(
        self,
        prefix: str,
        item_id: str,
        x: float,
        y: float,
        rotation: float,
        shape: dict[str, Any],
        style: dict[str, Any],
        label: str | None = None,
        source_component_id: str | None = None,
        severity: str | None = None,
    ) -> dict[str, Any]:
        shape_type = shape.get("shape")
        if shape_type == "circle":
            return circle_item(
                item_id=f"{prefix}:{item_id}",
                x=x,
                y=y,
                diameter=float(shape["diameter"]),
                style=style,
                label=label,
                source_component_id=source_component_id,
                severity=severity,
            )
        if shape_type == "slot":
            return slot_item(
                item_id=f"{prefix}:{item_id}",
                x=x,
                y=y,
                width=float(shape["width"]),
                height=float(shape["height"]),
                style=style,
                rotation=rotation,
                label=label,
                source_component_id=source_component_id,
                severity=severity,
            )
        if shape_type != "rect":
            LOGGER.warning(
                "Overlay fallback: unsupported rect rotation shape '%s' for component '%s'.",
                shape_type,
                source_component_id or item_id,
            )
        return rect_item(
            item_id=f"{prefix}:{item_id}",
            x=x,
            y=y,
            width=float(shape["width"]),
            height=float(shape["height"]),
            style=style,
            rotation=rotation,
            label=label,
            source_component_id=source_component_id,
            severity=severity,
        )
