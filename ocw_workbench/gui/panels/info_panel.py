from __future__ import annotations

from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.gui.panels._common import (
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    build_panel_container,
    configure_combo_box,
    create_form_section_widget,
    create_hint_label,
    create_section_widget,
    create_text_panel,
    current_text,
    load_qt,
    set_button_role,
    set_combo_items,
    set_label_text,
    set_size_policy,
    set_text,
    set_tooltip,
    set_value,
    wrap_layout_in_widget,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocw_workbench.gui.ui_semantics import (
    STATUS_PLACEMENT_CANCELLED,
    context_badge,
    placement_status_text,
    workflow_badge,
    workflow_step_text,
)
from ocw_workbench.services.controller_service import ControllerService


class InfoPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        on_updated: Any | None = None,
        on_status: Any | None = None,
        on_suggested_addition_requested: Any | None = None,
        on_suggested_addition_cancelled: Any | None = None,
        on_drag_requested: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.on_updated = on_updated
        self.on_status = on_status
        self.on_suggested_addition_requested = on_suggested_addition_requested
        self.on_suggested_addition_cancelled = on_suggested_addition_cancelled
        self.on_drag_requested = on_drag_requested
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._layout_intelligence: dict[str, Any] = {}
        self._apply_visual_treatment()
        self._configure_tooltips()
        self._connect_events()
        self.refresh()

    def refresh(self) -> str:
        state = self.controller_service.get_state(self.doc)
        context = self.controller_service.get_ui_context(self.doc)
        layout_intelligence = context.get("layout_intelligence", {})
        self._layout_intelligence = layout_intelligence if isinstance(layout_intelligence, dict) else {}
        workflow_card = layout_intelligence.get("workflow_card", {}) if isinstance(layout_intelligence, dict) else {}
        suggested_additions = (
            layout_intelligence.get("suggested_additions", [])
            if isinstance(layout_intelligence, dict)
            else []
        )
        controller = state["controller"]
        surface = controller.get("surface") or {}
        shape_name = str(surface.get("shape") or "rectangle")
        preview = load_preview_state(self.doc)
        snapshot = self._context_snapshot(state, context, workflow_card, preview)
        set_label_text(self.form["template"], context["template_id"] or "-")
        set_label_text(self.form["variant"], context["variant_id"] or "-")
        selected_ids = context.get("selected_ids", [])
        primary_selection = context["selection"] or "-"
        selection_label = primary_selection if len(selected_ids) <= 1 else f"{primary_selection} (+{len(selected_ids) - 1})"
        set_label_text(self.form["selection"], selection_label)
        set_label_text(self.form["selection_count"], str(context.get("selection_count", len(selected_ids))))
        set_label_text(self.form["component_count"], str(context["component_count"]))
        set_label_text(self.form["context_badge"], snapshot["badge"])
        set_label_text(self.form["context_title"], snapshot["title"])
        set_label_text(self.form["context_subtitle"], snapshot["subtitle"])
        set_label_text(self.form["context_meta"], snapshot["meta"])
        set_value(self.form["width"], float(controller.get("width", 0.0)))
        set_value(self.form["depth"], float(controller.get("depth", 0.0)))
        set_value(self.form["height"], float(controller.get("height", 0.0)))
        set_value(self.form["wall_thickness"], float(controller.get("wall_thickness", 3.0)))
        set_value(self.form["bottom_thickness"], float(controller.get("bottom_thickness", 3.0)))
        set_value(self.form["top_thickness"], float(controller.get("top_thickness", 3.0)))
        set_value(self.form["lid_inset"], float(controller.get("lid_inset", 1.5)))
        set_value(self.form["inner_clearance"], float(controller.get("inner_clearance", 0.35)))
        set_combo_items(self.form["surface_shape"], ["rectangle", "rounded_rect"])
        if hasattr(self.form["surface_shape"], "setCurrentIndex"):
            self.form["surface_shape"].setCurrentIndex(0 if shape_name == "rectangle" else 1)
        set_value(self.form["corner_radius"], float(surface.get("corner_radius", 0.0) or 0.0))
        summary_text = "\n".join(snapshot["summary_lines"])
        set_text(self.form["info"], summary_text)
        self.render_workflow_card(workflow_card)
        self._set_visible(self.form["geometry_section"], snapshot["show_geometry"])
        self._set_visible(self.form["info"], bool(summary_text.strip()))
        apply_status_message(
            self.form["status"],
            self._workflow_status_text(preview),
            level="info",
        )
        self._set_visible(self.form["status"], bool(snapshot["show_status"]))
        self._sync_surface_fields()
        return summary_text

    def apply_controller_updates(self) -> dict[str, Any]:
        updates = {
            "width": widget_value(self.form["width"]),
            "depth": widget_value(self.form["depth"]),
            "height": widget_value(self.form["height"]),
            "wall_thickness": widget_value(self.form["wall_thickness"]),
            "bottom_thickness": widget_value(self.form["bottom_thickness"]),
            "top_thickness": widget_value(self.form["top_thickness"]),
            "lid_inset": widget_value(self.form["lid_inset"]),
            "inner_clearance": widget_value(self.form["inner_clearance"]),
            "surface_shape": current_text(self.form["surface_shape"]),
            "corner_radius": widget_value(self.form["corner_radius"]),
        }
        state = self.controller_service.update_controller(self.doc, updates)
        self.refresh()
        self._publish_status("Controller geometry updated. Re-run validation if clearances changed.", level="success")
        if self.on_updated is not None:
            self.on_updated(state)
        return state

    def handle_apply_clicked(self) -> None:
        try:
            self.apply_controller_updates()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update controller settings", exc), level="error")

    def handle_surface_changed(self, *_args: Any) -> None:
        self._sync_surface_fields()

    def accept(self) -> bool:
        self.apply_controller_updates()
        return True

    def apply_suggested_addition(self, addition_id: str) -> dict[str, Any]:
        current_layout = self.controller_service.get_ui_context(self.doc).get("layout_intelligence", {})
        addition = next(
            (
                item
                for item in current_layout.get("suggested_additions", [])
                if isinstance(item, dict) and str(item.get("id") or "") == addition_id
            ),
            None,
        )
        state = self.controller_service.apply_suggested_addition(self.doc, addition_id)
        self.refresh()
        label = str(addition.get("label") or addition_id.replace("_", " ").title()) if isinstance(addition, dict) else addition_id
        status_message = str(addition.get("status_message") or "") if isinstance(addition, dict) else ""
        self._publish_status(status_message or f"Applied suggested addition '{label}'.", level="success")
        if self.on_updated is not None:
            self.on_updated(state)
        return state

    def handle_apply_suggested_addition(self, addition_id: str) -> None:
        try:
            if callable(self.on_suggested_addition_requested):
                started = bool(self.on_suggested_addition_requested(addition_id))
                if started:
                    self.refresh()
                    self._publish_status(placement_status_text({"mode": "suggested_addition"}), level="info")
                    return
            self.apply_suggested_addition(addition_id)
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not apply suggested addition", exc), level="error")

    def handle_cancel_suggested_addition(self) -> None:
        try:
            if callable(self.on_suggested_addition_cancelled):
                self.on_suggested_addition_cancelled()
                self.refresh()
                self._publish_status(STATUS_PLACEMENT_CANCELLED, level="info")
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not cancel guided placement", exc), level="error")

    def handle_drag_requested(self) -> None:
        try:
            if callable(self.on_drag_requested):
                started = bool(self.on_drag_requested())
                if started:
                    self.refresh()
                    self._publish_status("Drag selection in view", level="info")
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not start direct move", exc), level="error")

    def _sync_surface_fields(self) -> None:
        shape_name = current_text(self.form["surface_shape"]) or "rectangle"
        corner_enabled = shape_name == "rounded_rect"
        if hasattr(self.form["corner_radius"], "setEnabled"):
            self.form["corner_radius"].setEnabled(corner_enabled)

    def _publish_status(self, message: str, level: str = "info") -> None:
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message, level)

    def _workflow_status_text(self, preview: Any) -> str:
        return placement_status_text(preview)

    def _context_snapshot(
        self,
        state: dict[str, Any],
        context: dict[str, Any],
        workflow_card: dict[str, Any],
        preview: Any,
    ) -> dict[str, Any]:
        template_name = str(
            self._layout_intelligence.get("template_name")
            or workflow_card.get("template_title")
            or context.get("template_id")
            or "No template"
        )
        component_count = int(context.get("component_count", 0))
        selection_count = int(context.get("selection_count", 0))
        selected_ids = [str(item) for item in context.get("selected_ids", []) if isinstance(item, str) and item]
        placement_active = isinstance(preview, dict) and str(preview.get("mode") or "") == "suggested_addition"
        primary_action = workflow_card.get("primary_action") if isinstance(workflow_card, dict) else None
        next_label = str(primary_action.get("label") or "") if isinstance(primary_action, dict) else ""
        lines = [f"Active template: {template_name}"]
        lines.append(f"Components: {component_count}")
        badge = context_badge(placement_active=placement_active, selection_count=selection_count)
        title = template_name
        subtitle = f"{component_count} components on surface"
        if placement_active:
            placement_label = str(preview.get("label") or preview.get("addition_id") or "Placement")
            title = placement_label
            subtitle = self._placement_context_subtitle(state, preview)
            lines.append(f"Targeting: {placement_label}")
        elif selection_count > 0:
            title = selected_ids[0]
            if selection_count > 1:
                title = f"{title} (+{selection_count - 1})"
            subtitle = self._selected_context_subtitle(state, selected_ids)
            lines.append(f"Selected: {', '.join(selected_ids)}")
        if next_label and not placement_active:
            lines.append(f"Next: {next_label}")
        meta_parts = [f"{component_count} parts"]
        if selection_count > 0:
            meta_parts.append(f"{selection_count} selected")
        elif next_label:
            meta_parts.append(f"Next: {next_label}")
        if context.get("variant_id"):
            meta_parts.append(str(context["variant_id"]))
        show_geometry = not placement_active and selection_count == 0
        show_status = placement_active
        return {
            "badge": badge,
            "title": title,
            "subtitle": subtitle,
            "meta": " | ".join(meta_parts),
            "summary_lines": lines,
            "show_geometry": show_geometry,
            "show_status": show_status,
        }

    def _selected_context_subtitle(self, state: dict[str, Any], selected_ids: list[str]) -> str:
        if not selected_ids:
            return "No active selection"
        component_map = {
            str(component.get("id") or ""): component
            for component in state.get("components", [])
            if isinstance(component, dict)
        }
        primary = component_map.get(selected_ids[0], {})
        component_type = str(primary.get("type") or "component").replace("_", " ")
        zone_id = str(primary.get("zone_id") or "").strip()
        if len(selected_ids) > 1:
            return f"{component_type.title()} and {len(selected_ids) - 1} more"
        if zone_id:
            return f"{component_type.title()} in {zone_id}"
        return component_type.title()

    def _placement_context_subtitle(self, state: dict[str, Any], preview: dict[str, Any]) -> str:
        placement_feedback = preview.get("placement_feedback") if isinstance(preview.get("placement_feedback"), dict) else {}
        context_ids = [
            str(item)
            for item in placement_feedback.get("context_component_ids", [])
            if isinstance(item, str) and item
        ]
        if not context_ids:
            return "Move over target area"
        component_map = {
            str(component.get("id") or ""): component
            for component in state.get("components", [])
            if isinstance(component, dict)
        }
        first = component_map.get(context_ids[0], {})
        role = str(first.get("group_role") or first.get("type") or "component").replace("_", " ")
        if len(context_ids) == 1:
            return f"Above {role}"
        return f"Above {len(context_ids)} {role}"

    def _set_visible(self, widget: Any, visible: bool) -> None:
        if hasattr(widget, "setVisible"):
            widget.setVisible(bool(visible))
            return
        widget.visible = bool(visible)

    def _apply_visual_treatment(self) -> None:
        widget = self.widget
        if hasattr(widget, "setObjectName"):
            widget.setObjectName("OCWInfoPanelRoot")
        if hasattr(widget, "setStyleSheet"):
            widget.setStyleSheet(_info_panel_stylesheet())

    def _connect_events(self) -> None:
        if hasattr(self.form["surface_shape"], "currentIndexChanged"):
            self.form["surface_shape"].currentIndexChanged.connect(self.handle_surface_changed)
        if hasattr(self.form["apply_button"], "clicked"):
            self.form["apply_button"].clicked.connect(self.handle_apply_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["width"], "Overall controller width in millimeters.")
        set_tooltip(self.form["depth"], "Overall controller depth in millimeters.")
        set_tooltip(self.form["height"], "Overall controller height in millimeters.")
        set_tooltip(self.form["wall_thickness"], "Enclosure wall thickness.")
        set_tooltip(self.form["bottom_thickness"], "Bottom panel thickness.")
        set_tooltip(self.form["top_thickness"], "Top plate thickness.")
        set_tooltip(self.form["lid_inset"], "Inset depth for the lid or top plate.")
        set_tooltip(self.form["inner_clearance"], "Clearance between the shell and inner cavity.")
        set_tooltip(self.form["surface_shape"], "Top surface shape.")
        set_tooltip(self.form["corner_radius"], "Corner radius for rounded rectangles.")
        set_tooltip(self.form["apply_button"], "Apply geometry changes and rebuild the model.")

    def render_workflow_card(self, workflow_card: dict[str, Any]) -> None:
        layout_intelligence = self._layout_intelligence if isinstance(self._layout_intelligence, dict) else {}
        additions = layout_intelligence.get("suggested_additions", []) if isinstance(layout_intelligence, dict) else []
        primary_action = workflow_card.get("primary_action") if isinstance(workflow_card, dict) else None
        steps = workflow_card.get("steps", []) if isinstance(workflow_card, dict) else []
        preview = load_preview_state(self.doc)
        context = self.controller_service.get_ui_context(self.doc)
        selection_count = int(context.get("selection_count", 0))
        placement_active = isinstance(preview, dict) and str(preview.get("mode") or "") == "suggested_addition"
        active_addition_id = str(preview.get("addition_id") or "") if placement_active else ""
        short_description = str(workflow_card.get("short_description") or layout_intelligence.get("next_step") or "")
        progress_text = str(workflow_card.get("progress_text") or "")
        action_hint = str(
            workflow_card.get("next_step_hint")
            or (primary_action.get("description") if isinstance(primary_action, dict) else "")
            or short_description
            or "No suggested workflow step available yet."
        )
        if placement_active:
            action_hint = self._workflow_status_text(preview)
        selection_action = selection_count > 0 and not placement_active and not isinstance(primary_action, dict)
        selection_action_label = "Move selection" if selection_action and selection_count == 1 else ""
        title = (
            str(primary_action.get("label") or "Workflow")
            if isinstance(primary_action, dict) and str(primary_action.get("label") or "").strip()
            else "Workflow"
        )
        if placement_active:
            title = "Guided placement"
        elif selection_action:
            title = "Selection"
            action_hint = (
                "Move in view, then duplicate, rotate, or mirror"
                if selection_count == 1
                else "Align, distribute, duplicate, or transform the selection"
            )
        short_hint = self._compact_workflow_hint(short_description, action_hint)
        badge = workflow_badge(
            placement_active=placement_active,
            has_primary_action=bool(selection_action_label) or isinstance(primary_action, dict),
            completed_steps=int(workflow_card.get("completed_steps", 0) or 0),
            total_steps=int(workflow_card.get("total_steps", len(steps)) or len(steps)),
        )
        set_label_text(self.form["workflow_card_badge"], badge)
        set_label_text(self.form["workflow_card_title"], title)
        set_label_text(self.form["workflow_card_hint"], short_hint or "No next step")
        total_steps = int(workflow_card.get("total_steps", len(steps)) or len(steps))
        completed_steps = int(workflow_card.get("completed_steps", 0) or 0)
        progress_label = f"{completed_steps}/{total_steps} done" if total_steps > 0 else "No steps"
        if progress_text and total_steps <= 0:
            progress_label = progress_text
        set_label_text(self.form["workflow_card_progress_summary"], progress_label)
        set_label_text(self.form["workflow_card_action_hint"], action_hint)
        self.form["workflow_progress_items"] = []
        self.form["next_step_buttons"] = []
        visible_steps = [] if selection_action else self._visible_workflow_steps(steps, placement_active=placement_active)
        primary_button = self.form["primary_action_button"]
        cancel_button = self.form["workflow_card_cancel_button"]
        apply_button = self.form["apply_button"]
        visible = bool(primary_action or steps or additions)
        if selection_action:
            visible = True
        _qtcore, _qtgui, qtwidgets = load_qt()
        if qtwidgets is None:
            if selection_action_label:
                primary_button.text = selection_action_label
                set_tooltip(primary_button, "Start direct drag for the current selection.")
                primary_button.enabled = True
                primary_button.clicked = FallbackButton().clicked
                primary_button.clicked.connect(lambda _checked=None: self.handle_drag_requested())
                primary_button.visible = True
            elif isinstance(primary_action, dict):
                primary_button.text = "Placement active" if placement_active else str(primary_action.get("label") or "Primary Action")
                set_tooltip(primary_button, str(primary_action.get("tooltip") or primary_action.get("description") or "Apply this workflow step."))
                primary_button.enabled = not placement_active
                if not placement_active:
                    primary_button.clicked = FallbackButton().clicked
                    primary_button.clicked.connect(
                        lambda _checked=None, addition_id=str(primary_action.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                    )
                primary_button.visible = True
            else:
                primary_button.visible = False
            cancel_button.text = "Cancel placement"
            cancel_button.visible = placement_active
            cancel_button.enabled = placement_active
            apply_button.visible = not placement_active
            if placement_active:
                cancel_button.clicked = FallbackButton().clicked
                cancel_button.clicked.connect(lambda _checked=None: self.handle_cancel_suggested_addition())
            for step in visible_steps:
                if not isinstance(step, dict):
                    continue
                label = FallbackLabel(workflow_step_text(step))
                self.form["workflow_progress_items"].append(label)
            self.form["workflow_card_section"].visible = visible
            self.form["quick_actions_section"].visible = bool(primary_button.visible or cancel_button.visible or apply_button.visible)
            return

        self._clear_action_layout(self.form.get("workflow_progress_layout"))
        if selection_action_label:
            primary_label = selection_action_label
            primary_tooltip = "Start direct drag for the current selection."
            primary_button.setText(primary_label)
            set_tooltip(primary_button, primary_tooltip)
            if hasattr(primary_button, "clicked"):
                try:
                    primary_button.clicked.disconnect()
                except Exception:
                    pass
                primary_button.clicked.connect(lambda _checked=False: self.handle_drag_requested())
            if hasattr(primary_button, "setEnabled"):
                primary_button.setEnabled(True)
            primary_button.setVisible(True)
        elif isinstance(primary_action, dict):
            primary_label = "Placement active" if placement_active else str(primary_action.get("label") or "Primary Action")
            primary_tooltip = str(primary_action.get("tooltip") or primary_action.get("description") or primary_label)
            primary_button.setText(primary_label)
            set_tooltip(primary_button, primary_tooltip)
            if hasattr(primary_button, "clicked"):
                try:
                    primary_button.clicked.disconnect()
                except Exception:
                    pass
                if not placement_active:
                    primary_button.clicked.connect(
                        lambda _checked=False, addition_id=str(primary_action.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                    )
            if hasattr(primary_button, "setEnabled"):
                primary_button.setEnabled(not placement_active)
            primary_button.setVisible(True)
        else:
            primary_button.setVisible(False)
        apply_button.setVisible(not placement_active)
        if hasattr(cancel_button, "setText"):
            cancel_button.setText("Cancel placement")
        if hasattr(cancel_button, "setVisible"):
            cancel_button.setVisible(placement_active)
        if hasattr(cancel_button, "setEnabled"):
            cancel_button.setEnabled(placement_active)
        if hasattr(cancel_button, "clicked"):
            try:
                cancel_button.clicked.disconnect()
            except Exception:
                pass
            cancel_button.clicked.connect(lambda _checked=False: self.handle_cancel_suggested_addition())
        for step in visible_steps:
            if not isinstance(step, dict):
                continue
            step_copy = dict(step)
            if placement_active and active_addition_id and str(step_copy.get("id") or "") == active_addition_id:
                step_copy["status"] = "current"
            label = create_hint_label(qtwidgets, workflow_step_text(step_copy))
            if hasattr(label, "setObjectName"):
                label.setObjectName(_workflow_step_object_name(str(step_copy.get("status") or "open")))
            self.form["workflow_progress_layout"].addWidget(label)
            self.form["workflow_progress_items"].append(label)
        if hasattr(self.form["workflow_card_section"], "setVisible"):
            self.form["workflow_card_section"].setVisible(visible)
        self._set_visible(
            self.form["quick_actions_section"],
            bool(primary_button.isVisible() if hasattr(primary_button, "isVisible") else primary_button.visible)
            or bool(cancel_button.isVisible() if hasattr(cancel_button, "isVisible") else cancel_button.visible)
            or bool(apply_button.isVisible() if hasattr(apply_button, "isVisible") else apply_button.visible),
        )

    def _visible_workflow_steps(self, steps: list[Any], *, placement_active: bool) -> list[dict[str, Any]]:
        normalized = [dict(step) for step in steps if isinstance(step, dict)]
        if placement_active:
            current = [step for step in normalized if str(step.get("status") or "") == "current"]
            return current[:1]
        if len(normalized) <= 2:
            return normalized
        current = next((step for step in normalized if str(step.get("status") or "") == "current"), normalized[0])
        visible = [current]
        next_open = next(
            (
                step
                for step in normalized
                if step is not current and str(step.get("status") or "") == "open"
            ),
            None,
        )
        if next_open is not None:
            visible.append(next_open)
        elif len(normalized) > 1:
            visible.append(normalized[1] if normalized[1] is not current else normalized[-1])
        return visible[:2]

    def _compact_workflow_hint(self, short_description: str, action_hint: str) -> str:
        for candidate in (action_hint, short_description):
            text = str(candidate or "").strip()
            if not text:
                continue
            sentence = text.split(".")[0].strip()
            return sentence or text
        return ""

    def _clear_action_layout(self, layout: Any) -> None:
        if layout is None or not hasattr(layout, "count") or not hasattr(layout, "takeAt"):
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if hasattr(item, "widget") else None
            if widget is not None and hasattr(widget, "deleteLater"):
                widget.deleteLater()


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "template": FallbackLabel("-"),
            "variant": FallbackLabel("-"),
            "selection": FallbackLabel("-"),
            "selection_count": FallbackLabel("0"),
            "component_count": FallbackLabel("0"),
            "context_section": FallbackLabel(),
            "context_badge": FallbackLabel("Template"),
            "context_title": FallbackLabel("No template"),
            "context_subtitle": FallbackLabel("No active context"),
            "context_meta": FallbackLabel("0 parts"),
            "geometry_section": FallbackLabel(),
            "quick_actions_section": FallbackLabel(),
            "width": FallbackValue(160.0),
            "depth": FallbackValue(100.0),
            "height": FallbackValue(30.0),
            "wall_thickness": FallbackValue(3.0),
            "bottom_thickness": FallbackValue(3.0),
            "top_thickness": FallbackValue(3.0),
            "lid_inset": FallbackValue(1.5),
            "inner_clearance": FallbackValue(0.35),
            "surface_shape": FallbackCombo(["rectangle", "rounded_rect"]),
            "corner_radius": FallbackValue(0.0),
            "apply_button": FallbackButton("Apply Geometry"),
            "info": FallbackText(),
            "workflow_card_section": FallbackLabel(),
            "workflow_card_badge": FallbackLabel("Next"),
            "workflow_card_title": FallbackLabel("Workflow"),
            "workflow_card_hint": FallbackLabel("No next step"),
            "workflow_card_progress_summary": FallbackLabel("No steps"),
            "workflow_card_action_hint": FallbackLabel("Ready"),
            "primary_action_button": FallbackButton("Primary Action"),
            "workflow_card_cancel_button": FallbackButton("Cancel"),
            "workflow_progress_items": [],
            "next_step_buttons": [],
            "status": FallbackLabel(),
        }

    content, layout = build_panel_container(qtwidgets)
    context_section, meta_layout = create_form_section_widget(
        qtwidgets,
        "Context",
        spacing=6,
        margins=(0, 6, 0, 4),
    )
    if hasattr(context_section, "setObjectName"):
        context_section.setObjectName("OCWInspectorContextSection")
    template = qtwidgets.QLabel("-")
    variant = qtwidgets.QLabel("-")
    selection = qtwidgets.QLabel("-")
    selection_count = qtwidgets.QLabel("0")
    component_count = qtwidgets.QLabel("0")
    context_badge = qtwidgets.QLabel("Template")
    context_title = qtwidgets.QLabel("No template")
    context_subtitle = create_hint_label(qtwidgets, "No active context")
    context_meta = create_hint_label(qtwidgets, "0 parts")
    if hasattr(template, "setObjectName"):
        template.setObjectName("OCWInspectorKeyValue")
    if hasattr(variant, "setObjectName"):
        variant.setObjectName("OCWInspectorKeyValue")
    if hasattr(selection, "setObjectName"):
        selection.setObjectName("OCWInspectorKeyValue")
    if hasattr(selection_count, "setObjectName"):
        selection_count.setObjectName("OCWInspectorKeyValue")
    if hasattr(component_count, "setObjectName"):
        component_count.setObjectName("OCWInspectorKeyValue")
    if hasattr(context_badge, "setObjectName"):
        context_badge.setObjectName("OCWSemanticBadge")
    if hasattr(context_title, "setObjectName"):
        context_title.setObjectName("OCWInspectorContextTitle")
    if hasattr(context_subtitle, "setObjectName"):
        context_subtitle.setObjectName("OCWInspectorContextSubtitle")
    if hasattr(context_meta, "setObjectName"):
        context_meta.setObjectName("OCWInspectorContextMeta")
    meta_layout.addRow("Template", template)
    meta_layout.addRow("Variant", variant)
    meta_layout.addRow("Selected", selection)
    meta_layout.addRow("Selection", selection_count)
    meta_layout.addRow("Components", component_count)
    meta_layout.addRow("Focus", context_badge)
    meta_layout.addRow("", context_title)
    meta_layout.addRow("", context_subtitle)
    meta_layout.addRow("", context_meta)

    geometry_section, settings_layout = create_form_section_widget(
        qtwidgets,
        "Geometry",
        spacing=6,
        margins=(0, 4, 0, 4),
    )
    if hasattr(geometry_section, "setObjectName"):
        geometry_section.setObjectName("OCWInspectorGeometrySection")
    width = qtwidgets.QDoubleSpinBox()
    depth = qtwidgets.QDoubleSpinBox()
    height = qtwidgets.QDoubleSpinBox()
    wall_thickness = qtwidgets.QDoubleSpinBox()
    bottom_thickness = qtwidgets.QDoubleSpinBox()
    top_thickness = qtwidgets.QDoubleSpinBox()
    lid_inset = qtwidgets.QDoubleSpinBox()
    inner_clearance = qtwidgets.QDoubleSpinBox()
    corner_radius = qtwidgets.QDoubleSpinBox()
    for spinbox in (
        width,
        depth,
        height,
        wall_thickness,
        bottom_thickness,
        top_thickness,
        lid_inset,
        inner_clearance,
        corner_radius,
    ):
        spinbox.setRange(0.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    surface_shape = qtwidgets.QComboBox()
    configure_combo_box(surface_shape)
    surface_shape.addItems(["rectangle", "rounded_rect"])
    apply_button = set_button_role(qtwidgets.QPushButton("Apply Geometry"), "secondary")
    if hasattr(apply_button, "setObjectName"):
        apply_button.setObjectName("OCWInspectorApplyButton")
    settings_layout.addRow("Width (mm)", width)
    settings_layout.addRow("Depth (mm)", depth)
    settings_layout.addRow("Height (mm)", height)
    settings_layout.addRow("Wall (mm)", wall_thickness)
    settings_layout.addRow("Bottom (mm)", bottom_thickness)
    settings_layout.addRow("Top plate (mm)", top_thickness)
    settings_layout.addRow("Lid inset (mm)", lid_inset)
    settings_layout.addRow("Inner clearance (mm)", inner_clearance)
    settings_layout.addRow("Surface", surface_shape)
    settings_layout.addRow("Corner radius (mm)", corner_radius)

    info = create_text_panel(qtwidgets, max_height=64)
    if hasattr(info, "setObjectName"):
        info.setObjectName("OCWInspectorSummary")
    workflow_card_section, workflow_card_layout = create_section_widget(
        qtwidgets,
        "Workflow",
        spacing=6,
        margins=(0, 4, 0, 4),
    )
    if hasattr(workflow_card_section, "setObjectName"):
        workflow_card_section.setObjectName("OCWInspectorWorkflowSection")
    workflow_card_badge = qtwidgets.QLabel("Next")
    workflow_card_title = qtwidgets.QLabel("Workflow")
    if hasattr(workflow_card_badge, "setObjectName"):
        workflow_card_badge.setObjectName("OCWSemanticBadge")
    if hasattr(workflow_card_title, "font"):
        title_font = workflow_card_title.font()
        if hasattr(title_font, "setBold"):
            title_font.setBold(True)
            workflow_card_title.setFont(title_font)
    if hasattr(workflow_card_title, "setObjectName"):
        workflow_card_title.setObjectName("OCWInspectorWorkflowTitle")
    workflow_card_hint = create_hint_label(qtwidgets, "No next step")
    workflow_card_progress_summary = create_hint_label(qtwidgets, "No steps")
    workflow_card_action_hint = create_hint_label(qtwidgets, "Ready")
    if hasattr(workflow_card_hint, "setObjectName"):
        workflow_card_hint.setObjectName("OCWInspectorWorkflowHint")
    if hasattr(workflow_card_progress_summary, "setObjectName"):
        workflow_card_progress_summary.setObjectName("OCWInspectorWorkflowProgress")
    if hasattr(workflow_card_action_hint, "setObjectName"):
        workflow_card_action_hint.setObjectName("OCWInspectorWorkflowStatus")
    primary_action_button = set_button_role(qtwidgets.QPushButton("Primary Action"), "primary")
    if hasattr(primary_action_button, "setObjectName"):
        primary_action_button.setObjectName("OCWInspectorPrimaryAction")
    workflow_card_cancel_button = set_button_role(qtwidgets.QPushButton("Cancel placement"), "ghost")
    if hasattr(workflow_card_cancel_button, "setObjectName"):
        workflow_card_cancel_button.setObjectName("OCWInspectorCancelAction")
    workflow_card_cancel_button.setVisible(False)
    header_layout = qtwidgets.QVBoxLayout()
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(3)
    header_layout.addWidget(workflow_card_badge)
    header_layout.addWidget(workflow_card_title)
    header_layout.addWidget(workflow_card_hint)
    workflow_card_layout.addWidget(wrap_layout_in_widget(qtwidgets, header_layout))

    progress_layout = qtwidgets.QVBoxLayout()
    progress_layout.setContentsMargins(0, 0, 0, 0)
    progress_layout.setSpacing(3)
    progress_layout.addWidget(workflow_card_progress_summary)
    progress_host = qtwidgets.QWidget()
    if hasattr(progress_host, "setObjectName"):
        progress_host.setObjectName("OCWInspectorWorkflowSteps")
    workflow_progress_layout = qtwidgets.QVBoxLayout(progress_host)
    workflow_progress_layout.setContentsMargins(0, 0, 0, 0)
    workflow_progress_layout.setSpacing(3)
    progress_layout.addWidget(progress_host)
    workflow_card_layout.addWidget(wrap_layout_in_widget(qtwidgets, progress_layout))

    hint_layout = qtwidgets.QVBoxLayout()
    hint_layout.setContentsMargins(0, 0, 0, 0)
    hint_layout.setSpacing(3)
    hint_layout.addWidget(workflow_card_action_hint)
    workflow_card_layout.addWidget(wrap_layout_in_widget(qtwidgets, hint_layout))

    quick_actions_section, quick_actions_layout = create_section_widget(
        qtwidgets,
        "Quick Actions",
        spacing=4,
        margins=(0, 4, 0, 2),
    )
    if hasattr(quick_actions_section, "setObjectName"):
        quick_actions_section.setObjectName("OCWInspectorActionsSection")
    action_layout = qtwidgets.QVBoxLayout()
    action_layout.setContentsMargins(0, 0, 0, 0)
    action_layout.setSpacing(5)
    action_layout.addWidget(primary_action_button)
    action_layout.addWidget(workflow_card_cancel_button)
    action_layout.addWidget(apply_button)
    quick_actions_layout.addWidget(wrap_layout_in_widget(qtwidgets, action_layout))

    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    if hasattr(status, "setObjectName"):
        status.setObjectName("OCWInspectorStatus")
    layout.addWidget(context_section)
    layout.addWidget(workflow_card_section)
    layout.addWidget(quick_actions_section)
    layout.addWidget(geometry_section)
    layout.addWidget(info)
    layout.addWidget(status)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "template": template,
        "variant": variant,
        "selection": selection,
        "selection_count": selection_count,
        "component_count": component_count,
        "context_section": context_section,
        "context_badge": context_badge,
        "context_title": context_title,
        "context_subtitle": context_subtitle,
        "context_meta": context_meta,
        "geometry_section": geometry_section,
        "quick_actions_section": quick_actions_section,
        "width": width,
        "depth": depth,
        "height": height,
        "wall_thickness": wall_thickness,
        "bottom_thickness": bottom_thickness,
        "top_thickness": top_thickness,
        "lid_inset": lid_inset,
        "inner_clearance": inner_clearance,
        "surface_shape": surface_shape,
        "corner_radius": corner_radius,
        "apply_button": apply_button,
        "info": info,
        "workflow_card_section": workflow_card_section,
        "workflow_card_badge": workflow_card_badge,
        "workflow_card_title": workflow_card_title,
        "workflow_card_hint": workflow_card_hint,
        "workflow_card_progress_summary": workflow_card_progress_summary,
        "workflow_card_action_hint": workflow_card_action_hint,
        "primary_action_button": primary_action_button,
        "workflow_card_cancel_button": workflow_card_cancel_button,
        "workflow_progress_layout": workflow_progress_layout,
        "workflow_progress_items": [],
        "next_step_buttons": [],
        "status": status,
    }
def _workflow_step_object_name(status: str) -> str:
    if status == "completed":
        return "OCWWorkflowStepDone"
    if status == "current":
        return "OCWWorkflowStepActive"
    return "OCWWorkflowStepNext"


def _info_panel_stylesheet() -> str:
    return """
QWidget#OCWInfoPanelRoot {
    background: transparent;
}
QLabel#OCWSemanticBadge {
    color: #9eb1c7;
    background: #162130;
    border: 1px solid #243244;
    border-radius: 9px;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 7px;
}
QFrame#OCWInspectorContextSection,
QFrame#OCWInspectorWorkflowSection,
QFrame#OCWInspectorActionsSection,
QFrame#OCWInspectorGeometrySection {
    background: transparent;
    border: none;
}
QFrame#OCWInspectorContextSection QFrame#OCWDividerLine {
    background: #243244;
}
QFrame#OCWInspectorContextSection QLabel#OCWSectionHeaderTitle,
QFrame#OCWInspectorWorkflowSection QLabel#OCWSectionHeaderTitle,
QFrame#OCWInspectorActionsSection QLabel#OCWSectionHeaderTitle,
QFrame#OCWInspectorGeometrySection QLabel#OCWSectionHeaderTitle {
    color: #73869d;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QLabel#OCWInspectorContextTitle {
    color: #f3f7fb;
    font-size: 15px;
    font-weight: 700;
    padding-top: 1px;
}
QLabel#OCWInspectorContextSubtitle {
    color: #c5d2df;
    font-size: 11px;
    font-weight: 500;
}
QLabel#OCWInspectorContextMeta {
    color: #76889d;
    font-size: 10px;
    padding-top: 1px;
}
QLabel#OCWInspectorKeyValue {
    color: #b4c2d0;
    font-size: 11px;
}
QFrame#OCWInspectorWorkflowSection QFrame#OCWDividerLine,
QFrame#OCWInspectorActionsSection QFrame#OCWDividerLine,
QFrame#OCWInspectorGeometrySection QFrame#OCWDividerLine {
    background: #1c2634;
}
QLabel#OCWInspectorWorkflowTitle {
    color: #eef4fb;
    font-size: 13px;
    font-weight: 700;
}
QLabel#OCWInspectorWorkflowHint {
    color: #b9c7d5;
    font-size: 11px;
}
QLabel#OCWInspectorWorkflowProgress {
    color: #7c8ea4;
    font-size: 10px;
    font-weight: 600;
}
QWidget#OCWInspectorWorkflowSteps QLabel#OCWHelperText {
    color: #94a5b8;
    font-size: 10px;
}
QWidget#OCWInspectorWorkflowSteps QLabel#OCWWorkflowStepDone {
    color: #7ea27e;
    font-size: 10px;
    font-weight: 600;
}
QWidget#OCWInspectorWorkflowSteps QLabel#OCWWorkflowStepActive {
    color: #dbe7f5;
    font-size: 10px;
    font-weight: 700;
}
QWidget#OCWInspectorWorkflowSteps QLabel#OCWWorkflowStepNext {
    color: #94a5b8;
    font-size: 10px;
    font-weight: 600;
}
QLabel#OCWInspectorWorkflowStatus {
    color: #8ea1b7;
    font-size: 10px;
}
QPlainTextEdit#OCWInspectorSummary {
    background: transparent;
    border: none;
    color: #7c8ea4;
    padding: 0;
}
QPushButton#OCWInspectorPrimaryAction {
    min-height: 34px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#OCWInspectorApplyButton {
    min-height: 28px;
    border-radius: 7px;
    background: #131c2a;
    border: 1px solid #263246;
    color: #b6c4d3;
}
QPushButton#OCWInspectorApplyButton:hover {
    background: #192334;
    border-color: #324258;
}
QPushButton#OCWInspectorCancelAction {
    min-height: 26px;
    border-radius: 7px;
    color: #97a9bc;
}
QLabel#OCWInspectorStatus {
    margin-top: 2px;
}
"""
