from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import logging
from typing import Any

from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.gui.interaction.priority import dominant_interaction_layer, handles_visible
from ocw_workbench.gui.interaction.inline_edit_state import load_inline_edit_state
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.gui.overlay.colors import overlay_style
from ocw_workbench.gui.overlay.labels import component_label, issue_label, zone_label
from ocw_workbench.gui.overlay.shapes import circle_item, line_item, rect_item, slot_item, text_item
from ocw_workbench.gui.ui_semantics import STATUS_CLICK_TO_PLACE, STATUS_INVALID_TARGET, STATUS_MOVE_TARGET
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
        preview = load_preview_state(doc) or {}
        placement_feedback = (
            preview.get("placement_feedback")
            if isinstance(preview.get("placement_feedback"), dict)
            else {}
        )
        placement_active = str(preview.get("mode") or "") == "suggested_addition"
        placement_context_ids = {
            str(item)
            for item in placement_feedback.get("context_component_ids", [])
            if isinstance(item, str) and item.strip()
        }
        validation = context.get("validation")
        if not isinstance(validation, dict):
            validation = self.constraint_service.validate(controller_data, components)

        selected_component_id = context.get("selection")
        selected_component_ids = set(context.get("selected_ids", []))
        move_component_id = settings.get("move_component_id")
        hovered_component_id = settings.get("hovered_component_id")
        findings_by_component = self._group_findings(validation)
        inline_state = load_inline_edit_state(doc) or {}
        selection_count = len(selected_component_ids)
        items: list[dict[str, Any]] = []
        items.append(
            rect_item(
                item_id="surface",
                x=surface.width / 2.0,
                y=surface.height / 2.0,
                width=surface.width,
                height=surface.height,
                style=overlay_style("surface_active" if placement_active else "surface"),
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
            selected_role: str | None = None
            hovered = component["id"] == hovered_component_id and component["id"] != selected_component_id
            manipulated = component["id"] == move_component_id
            if component["id"] == selected_component_id:
                selected_role = "primary"
            elif component["id"] in selected_component_ids:
                selected_role = "secondary"
            context_relevant = component["id"] in placement_context_ids
            item_kind = "component"
            if manipulated:
                item_kind = "component_manipulated"
            elif selected_role == "primary" and context_relevant:
                item_kind = "component_selected_context"
            elif selected_role == "secondary" and context_relevant:
                item_kind = "component_selected_secondary_context"
            elif selected_role == "primary":
                item_kind = "component_selected"
            elif selected_role == "secondary":
                item_kind = "component_selected_secondary"
            elif hovered:
                item_kind = "component_hover"
            elif context_relevant:
                item_kind = "component_context"
            if severity == "error":
                if manipulated:
                    item_kind = "component_manipulated_error"
                elif hovered:
                    item_kind = "component_hover_error"
                elif selected_role == "primary" and context_relevant:
                    item_kind = "component_selected_context"
                elif selected_role == "secondary" and context_relevant:
                    item_kind = "component_selected_secondary_context"
                elif selected_role in {"primary", "secondary"}:
                    item_kind = "component_selected" if selected_role == "primary" else "component_selected_secondary"
                elif context_relevant:
                    item_kind = "component_context_error"
                else:
                    item_kind = "component_error"
            elif severity == "warning":
                if manipulated:
                    item_kind = "component_manipulated_warning"
                elif selected_role == "primary" and context_relevant:
                    item_kind = "component_selected_context"
                elif selected_role == "secondary" and context_relevant:
                    item_kind = "component_selected_secondary_context"
                elif selected_role == "primary":
                    item_kind = "component_selected"
                elif selected_role == "secondary":
                    item_kind = "component_selected_secondary"
                elif hovered:
                    item_kind = "component_hover_warning"
                elif context_relevant:
                    item_kind = "component_context_warning"
                else:
                    item_kind = "component_warning"
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
                    label=component_label(
                        component,
                        severity=severity,
                        selected_role=selected_role,
                        hovered=hovered,
                        context_relevant=context_relevant,
                        manipulated=manipulated,
                    ),
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

        if placement_active:
            items.extend(self._placement_target_items(context, placement_feedback))
            items.extend(self._placement_context_items(resolved_components, preview, placement_context_ids))
        preview_items = self._preview_items(doc)
        items.extend(preview_items)
        inline_items = self._inline_edit_items(doc, resolved_components, inline_state=inline_state, selection_count=selection_count, ui_settings=settings)
        items.extend(inline_items)

        return {
            "enabled": True,
            "surface": surface.to_dict(),
            "controller_height": float(controller_data.get("height", 0.0)),
            "items": items,
            "validation": validation,
            "summary": {
                "item_count": len(items),
                "component_count": len(resolved_components),
                "selected_count": len(selected_component_ids),
                "zone_count": len(controller_data.get("layout_zones", [])),
                "finding_count": validation["summary"]["total_count"],
                "interaction_layer": dominant_interaction_layer(
                    selection_count=selection_count,
                    ui_settings=settings,
                    inline_state=inline_state,
                ),
                "hovered_component_id": hovered_component_id,
                "handles_visible": bool(inline_items),
                "preview_active": bool(preview_items),
                "placement_active": placement_active,
                "placement_invalid": bool(placement_feedback.get("invalid_target")) if placement_active else False,
                "snap_active": any(
                    str(item.get("id") or "").startswith("preview_snap_")
                    for item in preview_items
                ),
            },
        }

    def _preview_items(self, doc: Any) -> list[dict[str, Any]]:
        preview = load_preview_state(doc)
        if preview is None:
            return []
        preview_components = preview.get("components")
        if isinstance(preview_components, list):
            return self._preview_group_items(doc, preview, preview_components)
        mode = str(preview.get("mode") or "place")
        validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        severity = validation.get("severity") if isinstance(validation.get("severity"), str) else None
        preview_component, template_id, label = self._preview_component_payload(doc, preview, mode)
        resolved = self.controller_builder.resolve_components([preview_component])[0]
        keepouts = self.controller_builder.build_keepouts([preview_component])
        cutouts = self.controller_builder.build_cutout_primitives([preview_component])
        items: list[dict[str, Any]] = []
        shape = resolved["resolved_mechanical"].keepout_top
        items.append(
            self._shape_item(
                prefix="preview_component",
                item_id=template_id,
                x=float(preview_component["x"]),
                y=float(preview_component["y"]),
                rotation=float(preview_component["rotation"]),
                shape=shape.to_dict(),
                style=overlay_style(self._preview_style_kind("component_preview", severity)),
                label=self._preview_label_text(label, preview, validation),
                source_component_id=str(preview_component.get("id") or template_id),
                severity=severity,
            )
        )
        for feature in keepouts:
            if feature.get("feature") != "keepout_top":
                continue
            items.append(
                self._shape_item(
                    prefix="preview_keepout",
                    item_id=template_id,
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style(self._preview_style_kind("keepout_preview", severity)),
                    source_component_id=str(preview_component.get("id") or template_id),
                    severity=severity,
                )
            )
        for feature in cutouts:
            items.append(
                self._shape_item(
                    prefix="preview_cutout",
                    item_id=template_id,
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style(self._preview_style_kind("cutout_preview", severity)),
                    source_component_id=str(preview_component.get("id") or template_id),
                    severity=severity,
                )
            )
        items.append(
            text_item(
                item_id=f"preview_label:{template_id}",
                x=float(preview_component["x"]),
                y=float(preview_component["y"]),
                text=self._preview_label_text(label, preview, validation),
                style=overlay_style(self._preview_style_kind("preview_label", severity)),
                source_component_id=str(preview_component.get("id") or template_id),
                severity=severity,
            )
        )
        items.extend(self._preview_snap_items(preview, template_id))
        return items

    def _preview_group_items(self, doc: Any, preview: dict[str, Any], preview_components: list[dict[str, Any]]) -> list[dict[str, Any]]:
        validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        severity = validation.get("severity") if isinstance(validation.get("severity"), str) else None
        label = str(preview.get("label") or preview.get("addition_id") or "Suggested addition")
        resolved_components = self.controller_builder.resolve_components([dict(item) for item in preview_components if isinstance(item, dict)])
        keepouts = self.controller_builder.build_keepouts(preview_components)
        cutouts = self.controller_builder.build_cutout_primitives(preview_components)
        items: list[dict[str, Any]] = []
        frame = self._component_group_bounds(resolved_components)
        if frame is not None:
            items.append(
                rect_item(
                    item_id=f"preview_group_frame:{preview.get('addition_id') or label}",
                    x=float(frame["x"]),
                    y=float(frame["y"]),
                    width=float(frame["width"]),
                    height=float(frame["height"]),
                    style=overlay_style("preview_group_frame"),
                )
            )
        for component in resolved_components:
            shape = component["resolved_mechanical"].keepout_top
            component_id = str(component.get("id") or "__preview__")
            items.append(
                self._shape_item(
                    prefix="preview_component",
                    item_id=component_id,
                    x=float(component["x"]),
                    y=float(component["y"]),
                    rotation=float(component.get("rotation", 0.0) or 0.0),
                    shape=shape.to_dict(),
                    style=overlay_style(self._preview_style_kind("component_preview", severity)),
                    label=component_label(component),
                    source_component_id=component_id,
                    severity=severity,
                )
            )
        for feature in keepouts:
            if feature.get("feature") != "keepout_top":
                continue
            component_id = str(feature.get("component_id") or "__preview__")
            items.append(
                self._shape_item(
                    prefix="preview_keepout",
                    item_id=component_id,
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style(self._preview_style_kind("keepout_preview", severity)),
                    source_component_id=component_id,
                    severity=severity,
                )
            )
        for feature in cutouts:
            component_id = str(feature.get("component_id") or "__preview__")
            items.append(
                self._shape_item(
                    prefix="preview_cutout",
                    item_id=component_id,
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    rotation=float(feature.get("rotation", 0.0) or 0.0),
                    shape=feature,
                    style=overlay_style(self._preview_style_kind("cutout_preview", severity)),
                    source_component_id=component_id,
                    severity=severity,
                )
            )
        items.append(
            text_item(
                item_id=f"preview_label:{preview.get('addition_id') or label}",
                x=float(preview.get("x", 0.0) or 0.0),
                y=float(preview.get("y", 0.0) or 0.0),
                text=self._preview_label_text(label, preview, validation),
                style=overlay_style(self._preview_style_kind("preview_label", severity)),
            )
        )
        return items

    def _placement_target_items(self, context: dict[str, Any], placement_feedback: dict[str, Any]) -> list[dict[str, Any]]:
        bounds = placement_feedback.get("target_bounds") if isinstance(placement_feedback.get("target_bounds"), dict) else None
        if bounds is None:
            return []
        zone_id = str(placement_feedback.get("target_zone_id") or "target")
        style_kind = "placement_zone_idle"
        if bool(placement_feedback.get("active_zone_id")):
            style_kind = "placement_zone_active"
        elif bool(placement_feedback.get("invalid_target")) and bool(placement_feedback.get("hover_zone_id")):
            style_kind = "placement_zone_invalid"
        elif bool(placement_feedback.get("hover_zone_id")):
            style_kind = "placement_zone_hover"
        label = self._placement_zone_label(context, zone_id)
        return [
            rect_item(
                item_id=f"placement_zone:{zone_id}",
                x=float(bounds.get("x", 0.0) or 0.0),
                y=float(bounds.get("y", 0.0) or 0.0),
                width=float(bounds.get("width", 0.0) or 0.0),
                height=float(bounds.get("height", 0.0) or 0.0),
                style=overlay_style(style_kind),
                label=label,
            )
        ]

    def _placement_context_items(
        self,
        resolved_components: list[dict[str, Any]],
        preview: dict[str, Any],
        placement_context_ids: set[str],
    ) -> list[dict[str, Any]]:
        if not placement_context_ids:
            return []
        matched = [component for component in resolved_components if component["id"] in placement_context_ids]
        if not matched:
            return []
        bounds = self._component_group_bounds(matched)
        if bounds is None:
            return []
        preview_x = float(preview.get("x", bounds["x"]) or bounds["x"])
        preview_y = float(preview.get("y", bounds["y"]) or bounds["y"])
        return [
            line_item(
                item_id="placement_context_link",
                start_x=preview_x,
                start_y=preview_y,
                end_x=float(bounds["x"]),
                end_y=float(bounds["y"]),
                style=overlay_style("placement_context_link"),
            ),
            rect_item(
                item_id="placement_context_group",
                x=float(bounds["x"]),
                y=float(bounds["y"]),
                width=float(bounds["width"]),
                height=float(bounds["height"]),
                style=overlay_style("placement_context_group"),
                source_ids=[component["id"] for component in matched],
            ),
        ]

    def _inline_edit_items(
        self,
        doc: Any,
        resolved_components: list[dict[str, Any]],
        *,
        inline_state: dict[str, Any],
        selection_count: int,
        ui_settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        context = self.controller_service.get_ui_context(doc)
        if not handles_visible(selection_count=selection_count, ui_settings=ui_settings):
            return []
        selected_component_id = context.get("selection")
        if not isinstance(selected_component_id, str):
            return []
        component = next((item for item in resolved_components if item["id"] == selected_component_id), None)
        if component is None:
            return []
        hovered_handle_id = inline_state.get("hovered_handle_id")
        active_handle_id = inline_state.get("active_handle_id")
        items: list[dict[str, Any]] = []
        width, height = self._resolved_component_size(component)
        rotation = float(component.get("rotation", 0.0) or 0.0)
        x = float(component["x"])
        y = float(component["y"])
        items.append(
            self._inline_handle_circle(
                handle_id=f"move:{selected_component_id}",
                component_id=selected_component_id,
                x=x,
                y=y,
                diameter=3.2,
                hovered_handle_id=hovered_handle_id,
                active_handle_id=active_handle_id,
                kind="move",
            )
        )
        rotate_x, rotate_y = self._rotate_point(0.0, (height / 2.0) + 6.0, rotation_deg=rotation, origin=(x, y))
        items.append(
            self._inline_handle_circle(
                handle_id=f"rotate:{selected_component_id}",
                component_id=selected_component_id,
                x=rotate_x,
                y=rotate_y,
                diameter=3.0,
                hovered_handle_id=hovered_handle_id,
                active_handle_id=active_handle_id,
                kind="rotate",
            )
        )
        parameter = self._inline_parameter_handle(component, width=width, height=height, rotation=rotation)
        if parameter is not None:
            handle_x, handle_y = self._rotate_point(
                float(parameter["local_x"]),
                float(parameter["local_y"]),
                rotation_deg=rotation,
                origin=(x, y),
            )
            items.append(
                self._inline_handle_circle(
                    handle_id=f"{parameter['parameter']}:{selected_component_id}",
                    component_id=selected_component_id,
                    x=handle_x,
                    y=handle_y,
                    diameter=3.0,
                    hovered_handle_id=hovered_handle_id,
                    active_handle_id=active_handle_id,
                    kind="parameter",
                )
            )
        items.extend(
            self._inline_action_items(
                component_id=selected_component_id,
                x=x,
                y=y,
                width=width,
                height=height,
                rotation=rotation,
                hovered_handle_id=hovered_handle_id,
            )
        )
        return items

    def _preview_component_payload(self, doc: Any, preview: dict[str, Any], mode: str) -> tuple[dict[str, Any], str, str]:
        if mode == "move":
            component_id = str(preview["component_id"])
            component = self.controller_service.get_component(doc, component_id)
            library_ref = str(component.get("library_ref") or component_id)
            library_component = self.controller_service.library_service.get(library_ref)
            return (
                {
                    "id": component_id,
                    "type": str(component.get("type") or library_component.get("category") or "component"),
                    "library_ref": library_ref,
                    "x": float(preview["x"]),
                    "y": float(preview["y"]),
                    "rotation": float(preview.get("rotation", component.get("rotation", 0.0)) or 0.0),
                },
                component_id,
                f"Move {library_component.get('ui', {}).get('label') or component_id}",
            )
        template_id = str(preview["template_id"])
        component = self.controller_service.library_service.get(template_id)
        return (
            {
                "id": "__preview__",
                "type": str(component.get("category") or "component"),
                "library_ref": template_id,
                "x": float(preview["x"]),
                "y": float(preview["y"]),
                "rotation": float(preview.get("rotation", 0.0) or 0.0),
            },
            template_id,
            f"Place {component.get('ui', {}).get('label') or template_id}",
        )

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

    def _preview_style_kind(self, base_kind: str, severity: str | None) -> str:
        if severity == "error":
            return f"{base_kind}_error"
        if severity == "warning":
            return f"{base_kind}_warning"
        return base_kind

    def _preview_label_text(self, label: str, preview: dict[str, Any], validation: dict[str, Any]) -> str:
        x = float(preview.get("x", 0.0) or 0.0)
        y = float(preview.get("y", 0.0) or 0.0)
        mode = str(preview.get("mode") or "place")
        placement_feedback = (
            preview.get("placement_feedback")
            if isinstance(preview.get("placement_feedback"), dict)
            else {}
        )
        base = f"{label} @ {x:.1f}, {y:.1f} mm"
        if bool(preview.get("snap_enabled")) and float(preview.get("grid_mm") or 0.0) > 0.0:
            base = f"{base} | Snap {float(preview['grid_mm']):.1f} mm"
        snap = preview.get("snap") if isinstance(preview.get("snap"), dict) else None
        if snap is not None:
            snap_type = str(snap.get("type") or "none")
            if snap_type == "point":
                base = f"{base} | Point snap"
            elif snap_type == "edge":
                base = f"{base} | Edge snap"
        axis_lock = preview.get("axis_lock") if isinstance(preview.get("axis_lock"), dict) else None
        if axis_lock is not None and axis_lock.get("active"):
            axis = str(axis_lock.get("axis") or "?").upper()
            base = f"{base} | Axis {axis} lock"
        status = validation.get("status")
        if isinstance(status, str) and status and status != "Valid placement":
            return f"{base} | {status}"
        if mode == "suggested_addition":
            if bool(placement_feedback.get("active_zone_id")):
                return f"{base} | {STATUS_CLICK_TO_PLACE}"
            if bool(placement_feedback.get("invalid_target")) and bool(placement_feedback.get("hover_zone_id")):
                return f"{base} | {STATUS_INVALID_TARGET}"
            return f"{base} | {STATUS_MOVE_TARGET}"
        if mode == "move":
            return f"{base} | Release to commit"
        return f"{base} | {STATUS_CLICK_TO_PLACE}"

    def _placement_zone_label(self, context: dict[str, Any], zone_id: str) -> str:
        layout_intelligence = context.get("layout_intelligence", {}) if isinstance(context, dict) else {}
        for zone in layout_intelligence.get("layout_zones", []) if isinstance(layout_intelligence, dict) else []:
            if not isinstance(zone, dict):
                continue
            if str(zone.get("id") or "") != zone_id:
                continue
            return str(zone.get("label") or zone_label(zone))
        return zone_id

    def _component_group_bounds(self, resolved_components: list[dict[str, Any]]) -> dict[str, float] | None:
        if not resolved_components:
            return None
        min_x = None
        max_x = None
        min_y = None
        max_y = None
        for component in resolved_components:
            width, height = self._resolved_component_size(component)
            left = float(component["x"]) - (width / 2.0)
            right = float(component["x"]) + (width / 2.0)
            top = float(component["y"]) - (height / 2.0)
            bottom = float(component["y"]) + (height / 2.0)
            min_x = left if min_x is None else min(min_x, left)
            max_x = right if max_x is None else max(max_x, right)
            min_y = top if min_y is None else min(min_y, top)
            max_y = bottom if max_y is None else max(max_y, bottom)
        if min_x is None or max_x is None or min_y is None or max_y is None:
            return None
        padding = 4.0
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding
        return {
            "x": (min_x + max_x) / 2.0,
            "y": (min_y + max_y) / 2.0,
            "width": max_x - min_x,
            "height": max_y - min_y,
        }

    def _resolved_component_size(self, component: dict[str, Any]) -> tuple[float, float]:
        shape = component["resolved_mechanical"].keepout_top.to_dict()
        if shape.get("shape") == "circle":
            diameter = float(shape.get("diameter", 0.0) or 0.0)
            return diameter, diameter
        return float(shape.get("width", 0.0) or 0.0), float(shape.get("height", 0.0) or 0.0)

    def _inline_handle_circle(
        self,
        *,
        handle_id: str,
        component_id: str,
        x: float,
        y: float,
        diameter: float,
        hovered_handle_id: str | None,
        active_handle_id: str | None,
        kind: str,
    ) -> dict[str, Any]:
        item_id = f"inline_handle:{handle_id}"
        style_kind = "inline_handle"
        if kind == "rotate":
            style_kind = "inline_handle_rotate"
        elif kind == "parameter":
            style_kind = "inline_handle_parameter"
        if hovered_handle_id == item_id:
            style_kind = "inline_handle_hover"
            diameter += 0.4
        if active_handle_id == item_id:
            style_kind = "inline_handle_active"
            diameter += 0.8
        return circle_item(
            item_id=item_id,
            x=x,
            y=y,
            diameter=diameter,
            style=overlay_style(style_kind),
            source_component_id=component_id,
            source_ids=[component_id],
        )

    def _inline_action_items(
        self,
        *,
        component_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float,
        hovered_handle_id: str | None,
    ) -> list[dict[str, Any]]:
        anchor_x, anchor_y = self._rotate_point(
            (width / 2.0) + 8.0,
            -((height / 2.0) + 8.0),
            rotation_deg=rotation,
            origin=(x, y),
        )
        specs = (
            {
                "action_id": "duplicate",
                "command_id": "OCW_DuplicateOnce",
                "label": "D",
                "title": "Duplicate",
                "offset_y": 0.0,
                "primary": True,
            },
            {
                "action_id": "rotate_cw_90",
                "command_id": "OCW_RotateCW90",
                "label": "R",
                "title": "Rotate +90",
                "offset_y": 5.2,
                "primary": False,
            },
            {
                "action_id": "mirror_horizontal",
                "command_id": "OCW_MirrorHorizontal",
                "label": "M",
                "title": "Mirror",
                "offset_y": 10.4,
                "primary": False,
            },
        )
        items: list[dict[str, Any]] = []
        for spec in specs:
            item_id = f"inline_action:{spec['action_id']}:{component_id}"
            style_kind = "inline_action_primary" if spec["primary"] else "inline_action"
            diameter = 3.6 if spec["primary"] else 3.2
            if hovered_handle_id == item_id:
                style_kind = "inline_action_hover"
                diameter += 0.5
            action_y = anchor_y + float(spec["offset_y"])
            items.append(
                circle_item(
                    item_id=item_id,
                    x=anchor_x,
                    y=action_y,
                    diameter=diameter,
                    style=overlay_style(style_kind),
                    label=str(spec["title"]),
                    source_component_id=component_id,
                    source_ids=[component_id],
                )
            )
            items.append(
                text_item(
                    item_id=f"{item_id}:label",
                    x=anchor_x - 0.7,
                    y=action_y - 0.9,
                    text=str(spec["label"]),
                    style=overlay_style("inline_action_label"),
                    source_component_id=component_id,
                    source_ids=[component_id],
                )
            )
            items[-2]["action_id"] = str(spec["action_id"])
            items[-2]["command_id"] = str(spec["command_id"])
        return items

    def _inline_parameter_handle(
        self,
        component: dict[str, Any],
        *,
        width: float,
        height: float,
        rotation: float,
    ) -> dict[str, Any] | None:
        library_ref = str(component.get("library_ref") or "")
        if not library_ref:
            return None
        library_component = self.controller_service.library_service.get(library_ref)
        category = str(component.get("type") or library_component.get("category") or "component")
        if category != "button":
            return None
        properties = component.get("properties") if isinstance(component.get("properties"), dict) else {}
        panel = library_component.get("mechanical", {}).get("panel", {}) if isinstance(library_component.get("mechanical"), dict) else {}
        opening = panel.get("recommended_cap_opening_mm", {}) if isinstance(panel, dict) else {}
        cap_width = float(properties.get("cap_width", opening.get("width", width * 0.7)) or (width * 0.7))
        return {
            "parameter": "cap_width",
            "value": cap_width,
            "local_x": max(cap_width / 2.0, 2.0) + 2.5,
            "local_y": 0.0,
            "rotation": rotation,
        }

    def _rotate_point(
        self,
        local_x: float,
        local_y: float,
        *,
        rotation_deg: float,
        origin: tuple[float, float],
    ) -> tuple[float, float]:
        import math

        angle = math.radians(float(rotation_deg))
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x = float(origin[0]) + (float(local_x) * cos_a) - (float(local_y) * sin_a)
        y = float(origin[1]) + (float(local_x) * sin_a) + (float(local_y) * cos_a)
        return x, y

    def _preview_snap_items(self, preview: dict[str, Any], item_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        snap = preview.get("snap") if isinstance(preview.get("snap"), dict) else None
        if snap is not None:
            snap_x = float(snap.get("x", preview.get("x", 0.0)) or 0.0)
            snap_y = float(snap.get("y", preview.get("y", 0.0)) or 0.0)
            snap_type = str(snap.get("type") or "none")
            marker_style = overlay_style("snap_point_marker" if snap_type == "point" else "snap_edge_marker")
            guide_style = overlay_style("snap_guide")
            items.append(
                circle_item(
                    item_id=f"preview_snap_marker:{item_id}",
                    x=snap_x,
                    y=snap_y,
                    diameter=2.4,
                    style=marker_style,
                )
            )
            preview_x = float(preview.get("x", 0.0) or 0.0)
            preview_y = float(preview.get("y", 0.0) or 0.0)
            if abs(preview_x - snap_x) > 1e-6 or abs(preview_y - snap_y) > 1e-6:
                items.append(
                    line_item(
                        item_id=f"preview_snap_guide:{item_id}",
                        start_x=preview_x,
                        start_y=preview_y,
                        end_x=snap_x,
                        end_y=snap_y,
                        style=guide_style,
                    )
                )
        axis_lock = preview.get("axis_lock") if isinstance(preview.get("axis_lock"), dict) else None
        if axis_lock is not None and axis_lock.get("active"):
            axis = str(axis_lock.get("axis") or "")
            anchor_x = float(axis_lock.get("anchor_x", preview.get("x", 0.0)) or 0.0)
            anchor_y = float(axis_lock.get("anchor_y", preview.get("y", 0.0)) or 0.0)
            preview_x = float(preview.get("x", 0.0) or 0.0)
            preview_y = float(preview.get("y", 0.0) or 0.0)
            if axis == "x":
                items.append(
                    line_item(
                        item_id=f"preview_axis_lock:{item_id}",
                        start_x=anchor_x,
                        start_y=anchor_y,
                        end_x=preview_x,
                        end_y=anchor_y,
                        style=overlay_style("axis_lock"),
                    )
                )
            elif axis == "y":
                items.append(
                    line_item(
                        item_id=f"preview_axis_lock:{item_id}",
                        start_x=anchor_x,
                        start_y=anchor_y,
                        end_x=anchor_x,
                        end_y=preview_y,
                        style=overlay_style("axis_lock"),
                    )
                )
        return items

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
