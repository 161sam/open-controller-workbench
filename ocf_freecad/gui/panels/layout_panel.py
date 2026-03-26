from __future__ import annotations

from typing import Any

from ocf_freecad.gui.panels._common import (
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    current_text,
    load_qt,
    set_label_text,
    set_text,
    widget_value,
)
from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.interaction_service import InteractionService


class LayoutPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        interaction_service: InteractionService | None = None,
        on_applied: Any | None = None,
        on_overlay_changed: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.on_applied = on_applied
        self.on_overlay_changed = on_overlay_changed
        self.on_status = on_status
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        context = self.controller_service.get_ui_context(self.doc)
        settings = self.interaction_service.get_settings(self.doc)
        set_text(
            self.form["overlay_status"],
            "\n".join(
                [
                    f"Overlay: {'on' if settings['overlay_enabled'] else 'off'}",
                    f"Constraint Overlay: {'on' if settings['show_constraints'] else 'off'}",
                    f"Measurements: {'on' if settings['measurements_enabled'] else 'off'}",
                    f"Conflict Lines: {'on' if settings['conflict_lines_enabled'] else 'off'}",
                    f"Labels: {'on' if settings['constraint_labels_enabled'] else 'off'}",
                    f"Snap: {'on' if settings['snap_enabled'] else 'off'}",
                    f"Grid: {settings['grid_mm']} mm",
                ]
            ),
        )
        self.form["grid_mm"].setValue(float(settings["grid_mm"]))
        layout = context.get("layout") or {}
        if not layout:
            set_text(self.form["summary"], "No layout has been applied yet.")
            set_label_text(self.form["status"], "Run Auto Layout after adding or moving components.")
            return
        summary = layout.get("result_summary", {})
        config = layout.get("config", {})
        set_text(
            self.form["summary"],
            "\n".join(
                [
                    f"Strategy: {layout.get('strategy', '-')}",
                    f"Placed: {summary.get('placed_count', 0)}",
                    f"Unplaced: {summary.get('unplaced_count', 0)}",
                    f"Warnings: {summary.get('warning_count', 0)}",
                    f"Grid: {config.get('grid_mm', config.get('grid_size_mm', 1.0))} mm",
                ]
            ),
        )

    def apply_auto_layout(self) -> dict[str, Any]:
        preset = current_text(self.form["preset"]) or "grid"
        strategy = preset if preset in {"grid", "row", "column"} else "grid"
        self.interaction_service.set_grid(self.doc, widget_value(self.form["grid_mm"]))
        config = {
            "grid_mm": widget_value(self.form["grid_mm"]),
            "spacing_mm": widget_value(self.form["spacing_mm"]),
            "padding_mm": widget_value(self.form["padding_mm"]),
        }
        result = self.controller_service.auto_layout(self.doc, strategy=strategy, config=config)
        set_label_text(self.form["status"], f"Applied {strategy} layout.")
        set_text(
            self.form["summary"],
            "\n".join(
                [
                    f"Placed: {len(result['placed_components'])}",
                    f"Unplaced: {len(result['unplaced_component_ids'])}",
                    f"Warnings: {len(result['warnings'])}",
                ]
            ),
        )
        if self.on_status is not None:
            self.on_status(f"Applied {strategy} layout.")
        if self.on_applied is not None:
            self.on_applied(result)
        return result

    def toggle_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_overlay(self.doc)
        self.refresh()
        self._publish_status(f"Overlay {'enabled' if settings['overlay_enabled'] else 'disabled'}.")
        return settings

    def toggle_constraint_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_overlay(self.doc)
        self.refresh()
        self._publish_status(
            f"Constraint overlay {'enabled' if settings['show_constraints'] else 'disabled'}."
        )
        return settings

    def toggle_snap(self) -> dict[str, Any]:
        settings = self.interaction_service.get_settings(self.doc)
        updated = self.interaction_service.update_settings(
            self.doc,
            {"snap_enabled": not settings["snap_enabled"], "grid_mm": widget_value(self.form["grid_mm"])},
        )
        self.refresh()
        self._publish_status(f"Snap {'enabled' if updated['snap_enabled'] else 'disabled'}.")
        return updated

    def toggle_measurements(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_measurements(self.doc)
        self.refresh()
        self._publish_status(
            f"Measurements {'enabled' if settings['measurements_enabled'] else 'disabled'}."
        )
        return settings

    def toggle_conflict_lines(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_conflict_lines(self.doc)
        self.refresh()
        self._publish_status(
            f"Conflict lines {'enabled' if settings['conflict_lines_enabled'] else 'disabled'}."
        )
        return settings

    def toggle_constraint_labels(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_labels(self.doc)
        self.refresh()
        self._publish_status(
            f"Constraint labels {'enabled' if settings['constraint_labels_enabled'] else 'disabled'}."
        )
        return settings

    def handle_apply_clicked(self) -> None:
        try:
            self.apply_auto_layout()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_overlay_clicked(self) -> None:
        try:
            self.toggle_overlay()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_constraint_overlay_clicked(self) -> None:
        try:
            self.toggle_constraint_overlay()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_snap_clicked(self) -> None:
        try:
            self.toggle_snap()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_measurements_clicked(self) -> None:
        try:
            self.toggle_measurements()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_conflict_lines_clicked(self) -> None:
        try:
            self.toggle_conflict_lines()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_constraint_labels_clicked(self) -> None:
        try:
            self.toggle_constraint_labels()
        except Exception as exc:
            self._publish_status(str(exc))

    def accept(self) -> bool:
        self.apply_auto_layout()
        return True

    def _connect_events(self) -> None:
        for key in ("apply_button", "rerun_button"):
            button = self.form[key]
            if hasattr(button, "clicked"):
                button.clicked.connect(self.handle_apply_clicked)
        if hasattr(self.form["overlay_button"], "clicked"):
            self.form["overlay_button"].clicked.connect(self.handle_overlay_clicked)
        if hasattr(self.form["constraint_overlay_button"], "clicked"):
            self.form["constraint_overlay_button"].clicked.connect(self.handle_constraint_overlay_clicked)
        if hasattr(self.form["snap_button"], "clicked"):
            self.form["snap_button"].clicked.connect(self.handle_snap_clicked)
        if hasattr(self.form["measurements_button"], "clicked"):
            self.form["measurements_button"].clicked.connect(self.handle_measurements_clicked)
        if hasattr(self.form["conflict_lines_button"], "clicked"):
            self.form["conflict_lines_button"].clicked.connect(self.handle_conflict_lines_clicked)
        if hasattr(self.form["constraint_labels_button"], "clicked"):
            self.form["constraint_labels_button"].clicked.connect(self.handle_constraint_labels_clicked)

    def _publish_status(self, message: str) -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message)
        if self.on_overlay_changed is not None:
            self.on_overlay_changed()


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "preset": FallbackCombo(["grid", "row", "column"]),
            "grid_mm": FallbackValue(1.0),
            "spacing_mm": FallbackValue(24.0),
            "padding_mm": FallbackValue(8.0),
            "apply_button": FallbackButton("Apply Auto Layout"),
            "rerun_button": FallbackButton("Run Again"),
            "overlay_button": FallbackButton("Toggle Overlay"),
            "constraint_overlay_button": FallbackButton("Constraint Overlay"),
            "snap_button": FallbackButton("Snap"),
            "measurements_button": FallbackButton("Measurements"),
            "conflict_lines_button": FallbackButton("Conflict Lines"),
            "constraint_labels_button": FallbackButton("Constraint Labels"),
            "summary": FallbackText(),
            "overlay_status": FallbackText(),
            "status": FallbackLabel(),
        }

    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    intro = qtwidgets.QLabel("Arrange components, control the grid, and inspect the overlay.")
    intro.setWordWrap(True)
    form = qtwidgets.QFormLayout()
    preset = qtwidgets.QComboBox()
    preset.addItems(["grid", "row", "column"])
    grid_mm = qtwidgets.QDoubleSpinBox()
    spacing_mm = qtwidgets.QDoubleSpinBox()
    padding_mm = qtwidgets.QDoubleSpinBox()
    for spinbox in (grid_mm, spacing_mm, padding_mm):
        spinbox.setRange(0.0, 1000.0)
        spinbox.setDecimals(2)
    grid_mm.setValue(1.0)
    spacing_mm.setValue(24.0)
    padding_mm.setValue(8.0)
    apply_button = qtwidgets.QPushButton("Apply Auto Layout")
    rerun_button = qtwidgets.QPushButton("Run Again")
    overlay_button = qtwidgets.QPushButton("Toggle Overlay")
    constraint_overlay_button = qtwidgets.QPushButton("Constraint Overlay")
    snap_button = qtwidgets.QPushButton("Snap")
    measurements_button = qtwidgets.QPushButton("Measurements")
    conflict_lines_button = qtwidgets.QPushButton("Conflict Lines")
    constraint_labels_button = qtwidgets.QPushButton("Constraint Labels")
    button_row = qtwidgets.QHBoxLayout()
    button_row.addWidget(apply_button)
    button_row.addWidget(rerun_button)
    button_row.addWidget(overlay_button)
    button_row.addWidget(constraint_overlay_button)
    button_row.addWidget(snap_button)
    button_row.addWidget(measurements_button)
    button_row.addWidget(conflict_lines_button)
    button_row.addWidget(constraint_labels_button)
    summary = qtwidgets.QPlainTextEdit()
    summary.setReadOnly(True)
    overlay_status = qtwidgets.QPlainTextEdit()
    overlay_status.setReadOnly(True)
    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    form.addRow("Preset", preset)
    form.addRow("Grid (mm)", grid_mm)
    form.addRow("Spacing (mm)", spacing_mm)
    form.addRow("Padding (mm)", padding_mm)
    layout.addWidget(intro)
    layout.addLayout(form)
    layout.addLayout(button_row)
    layout.addWidget(overlay_status)
    layout.addWidget(summary)
    layout.addWidget(status)
    return {
        "widget": widget,
        "preset": preset,
        "grid_mm": grid_mm,
        "spacing_mm": spacing_mm,
        "padding_mm": padding_mm,
        "apply_button": apply_button,
        "rerun_button": rerun_button,
        "overlay_button": overlay_button,
        "constraint_overlay_button": constraint_overlay_button,
        "snap_button": snap_button,
        "measurements_button": measurements_button,
        "conflict_lines_button": conflict_lines_button,
        "constraint_labels_button": constraint_labels_button,
        "overlay_status": overlay_status,
        "summary": summary,
        "status": status,
    }
