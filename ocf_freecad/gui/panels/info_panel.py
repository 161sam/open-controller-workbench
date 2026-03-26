from __future__ import annotations

from typing import Any

from ocf_freecad.gui.panels._common import (
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    configure_combo_box,
    configure_text_panel,
    current_text,
    load_qt,
    set_combo_items,
    set_label_text,
    set_size_policy,
    set_text,
    set_value,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocf_freecad.services.controller_service import ControllerService


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
        self._connect_events()
        self.refresh()

    def refresh(self) -> str:
        state = self.controller_service.get_state(self.doc)
        context = self.controller_service.get_ui_context(self.doc)
        controller = state["controller"]
        surface = controller.get("surface") or {}
        shape_name = str(surface.get("shape") or "rectangle")
        set_label_text(self.form["template"], context["template_id"] or "-")
        set_label_text(self.form["variant"], context["variant_id"] or "-")
        set_label_text(self.form["selection"], context["selection"] or "-")
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
        validation_text = "Validation has not been run yet."
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
        summary_text = "\n".join(
            [
                f"Template: {context['template_id'] or '-'}",
                f"Variant: {context['variant_id'] or '-'}",
                f"Selected: {context['selection'] or '-'}",
                f"Components: {context['component_count']}",
                layout_text,
                validation_text,
            ]
        )
        set_text(self.form["info"], summary_text)
        set_label_text(
            self.form["status"],
            "Review controller size and shell settings here, then place components in the Components tab.",
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
        self._publish_status("Updated controller geometry and refreshed the model.")
        if self.on_updated is not None:
            self.on_updated(state)
        return state

    def handle_apply_clicked(self) -> None:
        try:
            self.apply_controller_updates()
        except Exception as exc:
            self._publish_status(f"Could not update controller settings: {exc}")

    def handle_surface_changed(self, *_args: Any) -> None:
        self._sync_surface_fields()

    def accept(self) -> bool:
        self.apply_controller_updates()
        return True

    def _sync_surface_fields(self) -> None:
        shape_name = current_text(self.form["surface_shape"]) or "rectangle"
        corner_enabled = shape_name == "rounded_rect"
        if hasattr(self.form["corner_radius"], "setEnabled"):
            self.form["corner_radius"].setEnabled(corner_enabled)

    def _publish_status(self, message: str) -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        if hasattr(self.form["surface_shape"], "currentIndexChanged"):
            self.form["surface_shape"].currentIndexChanged.connect(self.handle_surface_changed)
        if hasattr(self.form["apply_button"], "clicked"):
            self.form["apply_button"].clicked.connect(self.handle_apply_clicked)


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "template": FallbackLabel("-"),
            "variant": FallbackLabel("-"),
            "selection": FallbackLabel("-"),
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
            "apply_button": FallbackButton("Apply Controller Settings"),
            "info": FallbackText(),
            "status": FallbackLabel(),
        }

    content = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(content)
    meta_box = qtwidgets.QGroupBox("Current Project")
    meta_layout = qtwidgets.QFormLayout(meta_box)
    template = qtwidgets.QLabel("-")
    variant = qtwidgets.QLabel("-")
    selection = qtwidgets.QLabel("-")
    component_count = qtwidgets.QLabel("0")
    meta_layout.addRow("Template", template)
    meta_layout.addRow("Variant", variant)
    meta_layout.addRow("Selected", selection)
    meta_layout.addRow("Components", component_count)

    settings_box = qtwidgets.QGroupBox("Controller Geometry")
    settings_layout = qtwidgets.QFormLayout(settings_box)
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
    apply_button = qtwidgets.QPushButton("Apply Controller Settings")
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

    info = qtwidgets.QPlainTextEdit()
    configure_text_panel(info, max_height=120)
    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    layout.addWidget(meta_box)
    layout.addWidget(settings_box)
    layout.addWidget(info)
    layout.addWidget(status)
    layout.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "template": template,
        "variant": variant,
        "selection": selection,
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
        "status": status,
    }
