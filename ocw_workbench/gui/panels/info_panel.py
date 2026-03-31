from __future__ import annotations

from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
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
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocw_workbench.services.controller_service import ControllerService


class InfoPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        on_updated: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.on_updated = on_updated
        self.on_status = on_status
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._configure_tooltips()
        self._connect_events()
        self.refresh()

    def refresh(self) -> str:
        state = self.controller_service.get_state(self.doc)
        context = self.controller_service.get_ui_context(self.doc)
        layout_intelligence = context.get("layout_intelligence", {})
        workflow_card = layout_intelligence.get("workflow_card", {}) if isinstance(layout_intelligence, dict) else {}
        suggested_additions = (
            layout_intelligence.get("suggested_additions", [])
            if isinstance(layout_intelligence, dict)
            else []
        )
        controller = state["controller"]
        surface = controller.get("surface") or {}
        shape_name = str(surface.get("shape") or "rectangle")
        set_label_text(self.form["template"], context["template_id"] or "-")
        set_label_text(self.form["variant"], context["variant_id"] or "-")
        selected_ids = context.get("selected_ids", [])
        primary_selection = context["selection"] or "-"
        selection_label = primary_selection if len(selected_ids) <= 1 else f"{primary_selection} (+{len(selected_ids) - 1})"
        set_label_text(self.form["selection"], selection_label)
        set_label_text(self.form["selection_count"], str(context.get("selection_count", len(selected_ids))))
        set_label_text(self.form["component_count"], str(context["component_count"]))
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
        validation = context.get("validation")
        validation_text = "Validation not run."
        if isinstance(validation, dict):
            summary = validation.get("summary", {})
            validation_text = (
                f"Validation: {summary.get('error_count', 0)} errors, "
                f"{summary.get('warning_count', 0)} warnings."
            )
        layout = context.get("layout") or {}
        layout_text = "No layout recorded."
        if layout:
            layout_text = (
                f"Layout: {layout.get('strategy', '-')} "
                f"from {layout.get('source', 'manual')}."
            )
        primary_action = workflow_card.get("primary_action", {}) if isinstance(workflow_card, dict) else {}
        secondary_actions = workflow_card.get("secondary_actions", []) if isinstance(workflow_card, dict) else []
        summary_text = "\n".join(
            [
                f"Template: {context['template_id'] or '-'}",
                f"Variant: {context['variant_id'] or '-'}",
                f"Primary selected: {context['selection'] or '-'}",
                f"Selected count: {context.get('selection_count', len(selected_ids))}",
                f"Selected ids: {', '.join(selected_ids) if selected_ids else '-'}",
                f"Components: {context['component_count']}",
                layout_text,
                validation_text,
                f"Workflow: {workflow_card.get('template_title') or context['template_id'] or '-'}",
                f"Next step hint: {layout_intelligence.get('next_step') or '-'}",
                f"Primary action: {primary_action.get('label') or '-'}",
                f"Next steps: {', '.join(str(item.get('label') or '-') for item in secondary_actions) if secondary_actions else '-'}",
                f"Suggested additions: {', '.join(str(item.get('label') or '-') for item in suggested_additions) if suggested_additions else '-'}",
            ]
        )
        set_text(self.form["info"], summary_text)
        self._refresh_workflow_card(workflow_card, layout_intelligence)
        apply_status_message(
            self.form["status"],
            "Review controller geometry here, then place or refine components.",
            level="info",
        )
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
            self.apply_suggested_addition(addition_id)
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not apply suggested addition", exc), level="error")

    def _sync_surface_fields(self) -> None:
        shape_name = current_text(self.form["surface_shape"]) or "rectangle"
        corner_enabled = shape_name == "rounded_rect"
        if hasattr(self.form["corner_radius"], "setEnabled"):
            self.form["corner_radius"].setEnabled(corner_enabled)

    def _publish_status(self, message: str, level: str = "info") -> None:
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message, level)

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

    def _refresh_workflow_card(self, workflow_card: dict[str, Any], layout_intelligence: dict[str, Any]) -> None:
        additions = (
            layout_intelligence.get("suggested_additions", [])
            if isinstance(layout_intelligence, dict)
            else []
        )
        primary_action = workflow_card.get("primary_action") if isinstance(workflow_card, dict) else None
        secondary_actions = workflow_card.get("secondary_actions", []) if isinstance(workflow_card, dict) else []
        title = str(workflow_card.get("template_title") or "No template workflow available yet.")
        short_description = str(workflow_card.get("short_description") or layout_intelligence.get("next_step") or "")
        ideal_for = workflow_card.get("ideal_for", []) if isinstance(workflow_card, dict) else []
        ideal_for_text = ", ".join(str(item) for item in ideal_for if isinstance(item, str) and item.strip())
        set_label_text(self.form["workflow_card_title"], title)
        set_label_text(self.form["workflow_card_hint"], short_description or "No suggested workflow step available yet.")
        set_label_text(
            self.form["workflow_card_ideal_for"],
            f"Ideal for: {ideal_for_text}" if ideal_for_text else "Ideal for: -",
        )
        self.form["next_step_buttons"] = []
        primary_button = self.form["primary_action_button"]
        visible = bool(primary_action or secondary_actions or additions)
        qtcore, _qtgui, qtwidgets = load_qt()
        if qtwidgets is None:
            if isinstance(primary_action, dict):
                primary_button.text = str(primary_action.get("label") or "Primary Action")
                set_tooltip(primary_button, str(primary_action.get("tooltip") or primary_action.get("description") or "Apply this workflow step."))
                primary_button.clicked = FallbackButton().clicked
                primary_button.clicked.connect(
                    lambda _checked=None, addition_id=str(primary_action.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                )
                primary_button.visible = True
            else:
                primary_button.visible = False
            for addition in secondary_actions[:4]:
                if not isinstance(addition, dict):
                    continue
                button = FallbackButton(str(addition.get("short_label") or addition.get("label") or "Apply"))
                set_tooltip(button, str(addition.get("tooltip") or addition.get("description") or "Apply this next step."))
                button.clicked.connect(
                    lambda _checked=None, addition_id=str(addition.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                )
                self.form["next_step_buttons"].append(button)
            self.form["workflow_card_section"].visible = visible
            return

        self._clear_action_layout(self.form.get("next_step_buttons_layout"))
        if isinstance(primary_action, dict):
            primary_label = str(primary_action.get("label") or "Primary Action")
            primary_tooltip = str(primary_action.get("tooltip") or primary_action.get("description") or primary_label)
            primary_button.setText(primary_label)
            set_tooltip(primary_button, primary_tooltip)
            if hasattr(primary_button, "clicked"):
                try:
                    primary_button.clicked.disconnect()
                except Exception:
                    pass
                primary_button.clicked.connect(
                    lambda _checked=False, addition_id=str(primary_action.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                )
            primary_button.setVisible(True)
        else:
            primary_button.setVisible(False)
        for addition in secondary_actions[:4]:
            if not isinstance(addition, dict):
                continue
            label = str(addition.get("short_label") or addition.get("label") or "Apply")
            tooltip = str(addition.get("tooltip") or addition.get("description") or label)
            detail = str(addition.get("description") or "")
            button = set_button_role(qtwidgets.QPushButton(label), "secondary")
            set_tooltip(button, tooltip)
            if hasattr(button, "clicked"):
                button.clicked.connect(
                    lambda _checked=False, addition_id=str(addition.get("id") or ""): self.handle_apply_suggested_addition(addition_id)
                )
            if detail:
                button.setText(f"{label} - {detail}")
            self.form["next_step_buttons_layout"].addWidget(button)
            self.form["next_step_buttons"].append(button)
        if hasattr(self.form["workflow_card_section"], "setVisible"):
            self.form["workflow_card_section"].setVisible(visible)

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
            "workflow_card_title": FallbackLabel("No template workflow available yet."),
            "workflow_card_hint": FallbackLabel("No suggested workflow step available yet."),
            "workflow_card_ideal_for": FallbackLabel("Ideal for: -"),
            "primary_action_button": FallbackButton("Primary Action"),
            "next_step_buttons": [],
            "status": FallbackLabel(),
        }

    content, layout = build_panel_container(qtwidgets)
    meta_box, meta_layout = create_form_section_widget(qtwidgets, "Project")
    template = qtwidgets.QLabel("-")
    variant = qtwidgets.QLabel("-")
    selection = qtwidgets.QLabel("-")
    selection_count = qtwidgets.QLabel("0")
    component_count = qtwidgets.QLabel("0")
    meta_layout.addRow("Template", template)
    meta_layout.addRow("Variant", variant)
    meta_layout.addRow("Primary selected", selection)
    meta_layout.addRow("Selected count", selection_count)
    meta_layout.addRow("Components", component_count)

    settings_box, settings_layout = create_form_section_widget(qtwidgets, "Geometry")
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
    apply_button = set_button_role(qtwidgets.QPushButton("Apply Geometry"), "primary")
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
    settings_layout.addRow("", apply_button)

    info = create_text_panel(qtwidgets, max_height=110)
    workflow_card_section, workflow_card_layout = create_section_widget(qtwidgets, "Workflow Card")
    workflow_card_title = qtwidgets.QLabel("No template workflow available yet.")
    workflow_card_hint = create_hint_label(
        qtwidgets,
        "Suggested actions appear here when the active template has a clear next move.",
    )
    workflow_card_ideal_for = create_hint_label(qtwidgets, "Ideal for: -")
    primary_action_label = qtwidgets.QLabel("Primary Action")
    primary_action_button = set_button_role(qtwidgets.QPushButton("Primary Action"), "primary")
    secondary_actions_label = qtwidgets.QLabel("Next Steps")
    workflow_card_layout.addWidget(workflow_card_title)
    workflow_card_layout.addWidget(workflow_card_hint)
    workflow_card_layout.addWidget(workflow_card_ideal_for)
    workflow_card_layout.addWidget(primary_action_label)
    workflow_card_layout.addWidget(primary_action_button)
    workflow_card_layout.addWidget(secondary_actions_label)
    next_steps_buttons_host = qtwidgets.QWidget()
    next_steps_buttons_layout = qtwidgets.QVBoxLayout(next_steps_buttons_host)
    next_steps_buttons_layout.setContentsMargins(0, 0, 0, 0)
    next_steps_buttons_layout.setSpacing(6)
    workflow_card_layout.addWidget(next_steps_buttons_host)

    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    top_row = qtwidgets.QHBoxLayout()
    top_row.setSpacing(8)
    top_row.addWidget(meta_box, 1)
    top_row.addWidget(settings_box, 2)
    layout.addLayout(top_row)
    layout.addWidget(info)
    layout.addWidget(workflow_card_section)
    layout.addWidget(status)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "template": template,
        "variant": variant,
        "selection": selection,
        "selection_count": selection_count,
        "component_count": component_count,
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
        "workflow_card_title": workflow_card_title,
        "workflow_card_hint": workflow_card_hint,
        "workflow_card_ideal_for": workflow_card_ideal_for,
        "primary_action_button": primary_action_button,
        "next_step_buttons_layout": next_steps_buttons_layout,
        "next_step_buttons": [],
        "status": status,
    }
