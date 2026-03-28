from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, format_layout_message, format_toggle_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
    build_panel_container,
    configure_combo_box,
    create_button_row_layout,
    create_form_layout,
    create_form_section_widget,
    create_section_widget,
    create_status_label,
    create_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    current_text,
    load_qt,
    set_label_text,
    set_button_role,
    set_current_text,
    set_tooltip,
    set_value,
    set_size_policy,
    set_text,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


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
        self._configure_tooltips()
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
                    f"Issue Overlay: {'on' if settings['show_constraints'] else 'off'}",
                    f"Measurements: {'on' if settings['measurements_enabled'] else 'off'}",
                    f"Conflict Lines: {'on' if settings['conflict_lines_enabled'] else 'off'}",
                    f"Labels: {'on' if settings['constraint_labels_enabled'] else 'off'}",
                    f"Snap: {'on' if settings['snap_enabled'] else 'off'}",
                    f"Grid: {settings['grid_mm']} mm",
                ]
            ),
        )
        layout = context.get("layout") or {}
        self._sync_form_defaults(layout=layout, settings=settings)
        if not layout:
            set_text(self.form["summary"], "No layout has been applied yet.")
            apply_status_message(
                self.form["status"],
                "Use Auto Place after creating a controller or when the layout needs a reset.",
                level="info",
            )
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
        context = self.controller_service.get_ui_context(self.doc)
        layout = context.get("layout") or {}
        active_config = layout.get("config", {}) if isinstance(layout.get("config"), dict) else {}
        preset = current_text(self.form["preset"]) or layout.get("strategy") or "grid"
        strategy = preset if preset in {"grid", "row", "column", "zone"} else "grid"
        grid_value = widget_value(self.form["grid_mm"])
        spacing_value = widget_value(self.form["spacing_mm"])
        padding_value = widget_value(self.form["padding_mm"])
        self.interaction_service.set_grid(self.doc, grid_value)
        config = deepcopy(active_config)
        config.update(
            {
                "grid_mm": grid_value,
                "spacing_mm": spacing_value,
                "spacing_x_mm": spacing_value,
                "spacing_y_mm": spacing_value,
                "padding_mm": padding_value,
            }
        )
        result = self.controller_service.auto_layout(self.doc, strategy=strategy, config=config)
        status_message, status_level = format_layout_message(result, strategy)
        apply_status_message(self.form["status"], status_message, level=status_level)
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
            self.on_status(status_message)
        if self.on_applied is not None:
            self.on_applied(result)
        return result

    def toggle_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_overlay(self.doc)
        self.refresh()
        self._publish_status(
            format_toggle_message(
                "Overlay",
                settings["overlay_enabled"],
                "Shows layout guides without changing the model.",
            ),
            level="info",
        )
        return settings

    def toggle_constraint_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_overlay(self.doc)
        self.refresh()
        self._publish_status(
            format_toggle_message(
                "Issue overlay",
                settings["show_constraints"],
                "Shows spacing and edge issues in the view.",
            ),
            level="info",
        )
        return settings

    def toggle_snap(self) -> dict[str, Any]:
        settings = self.interaction_service.get_settings(self.doc)
        updated = self.interaction_service.update_settings(
            self.doc,
            {"snap_enabled": not settings["snap_enabled"], "grid_mm": widget_value(self.form["grid_mm"])},
        )
        self.refresh()
        self._publish_status(
            format_toggle_message("Snap to grid", updated["snap_enabled"], "New moves use the current grid."),
            level="info",
        )
        return updated

    def toggle_measurements(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_measurements(self.doc)
        self.refresh()
        self._publish_status(
            format_toggle_message("Measurement guides", settings["measurements_enabled"], "Use them to check spacing."),
            level="info",
        )
        return settings

    def toggle_conflict_lines(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_conflict_lines(self.doc)
        self.refresh()
        self._publish_status(
            format_toggle_message("Conflict lines", settings["conflict_lines_enabled"], "Use them to spot conflicts."),
            level="info",
        )
        return settings

    def toggle_constraint_labels(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_labels(self.doc)
        self.refresh()
        self._publish_status(
            format_toggle_message("Issue labels", settings["constraint_labels_enabled"], "Shows issue names in the view."),
            level="info",
        )
        return settings

    def handle_apply_clicked(self) -> None:
        try:
            self.apply_auto_layout()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not apply layout", exc), level="error")

    def handle_overlay_clicked(self) -> None:
        try:
            self.toggle_overlay()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update overlay visibility", exc), level="error")

    def handle_constraint_overlay_clicked(self) -> None:
        try:
            self.toggle_constraint_overlay()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update constraint checks", exc), level="error")

    def handle_snap_clicked(self) -> None:
        try:
            self.toggle_snap()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update snap mode", exc), level="error")

    def handle_measurements_clicked(self) -> None:
        try:
            self.toggle_measurements()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update measurement guides", exc), level="error")

    def handle_conflict_lines_clicked(self) -> None:
        try:
            self.toggle_conflict_lines()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update conflict lines", exc), level="error")

    def handle_constraint_labels_clicked(self) -> None:
        try:
            self.toggle_constraint_labels()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update issue labels", exc), level="error")

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

    def _publish_status(self, message: str, level: str = "info") -> None:
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message)
        if self.on_overlay_changed is not None:
            self.on_overlay_changed()

    def _sync_form_defaults(self, layout: dict[str, Any], settings: dict[str, Any]) -> None:
        config = layout.get("config", {}) if isinstance(layout.get("config"), dict) else {}
        strategy = layout.get("strategy") if isinstance(layout.get("strategy"), str) else None
        set_current_text(self.form["preset"], strategy or "grid")
        set_value(self.form["grid_mm"], float(config.get("grid_mm", settings["grid_mm"])))
        set_value(
            self.form["spacing_mm"],
            float(config.get("spacing_mm", config.get("spacing_x_mm", config.get("spacing_y_mm", 24.0)))),
        )
        set_value(self.form["padding_mm"], float(config.get("padding_mm", 8.0)))

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["preset"], "Choose the placement strategy used by Auto Place.")
        set_tooltip(self.form["grid_mm"], "Base grid used for snapping and placement rounding.")
        set_tooltip(self.form["spacing_mm"], "Center-to-center spacing target for grid, row or column placement.")
        set_tooltip(self.form["padding_mm"], "Padding kept free near the controller edge or placement zone border.")
        set_tooltip(self.form["apply_button"], "Apply the current placement strategy to all components now.")
        set_tooltip(self.form["rerun_button"], "Run Auto Place again with the current settings.")
        set_tooltip(self.form["overlay_button"], "Show or hide helper graphics such as outlines and cutout previews.")
        set_tooltip(self.form["constraint_overlay_button"], "Show or hide validation highlights for spacing and edge checks.")
        set_tooltip(self.form["snap_button"], "Toggle whether new moves align to the current grid value.")
        set_tooltip(self.form["measurements_button"], "Show or hide measurement guides in the overlay.")
        set_tooltip(self.form["conflict_lines_button"], "Show or hide helper lines that connect conflicting components.")
        set_tooltip(self.form["constraint_labels_button"], "Show or hide text labels for issues directly in the view.")


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "preset": FallbackCombo(["grid", "row", "column", "zone"]),
            "grid_mm": FallbackValue(1.0),
            "spacing_mm": FallbackValue(24.0),
            "padding_mm": FallbackValue(8.0),
            "apply_button": FallbackButton("Auto Place"),
            "rerun_button": FallbackButton("Re-run Placement"),
            "overlay_button": FallbackButton("Overlay Visibility"),
            "constraint_overlay_button": FallbackButton("Issues"),
            "snap_button": FallbackButton("Snap"),
            "measurements_button": FallbackButton("Guides"),
            "conflict_lines_button": FallbackButton("Conflict Lines"),
            "constraint_labels_button": FallbackButton("Issue Labels"),
            "summary": FallbackText(),
            "overlay_status": FallbackText(),
            "status": FallbackLabel(),
        }

    content, layout = build_panel_container(qtwidgets)
    intro = create_status_label(qtwidgets, "Run Auto Place, then review helpers and feedback.")
    form = create_form_layout(qtwidgets, spacing=4)
    preset = qtwidgets.QComboBox()
    preset.addItems(["grid", "row", "column", "zone"])
    configure_combo_box(preset)
    grid_mm = qtwidgets.QDoubleSpinBox()
    spacing_mm = qtwidgets.QDoubleSpinBox()
    padding_mm = qtwidgets.QDoubleSpinBox()
    for spinbox in (grid_mm, spacing_mm, padding_mm):
        spinbox.setRange(0.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    grid_mm.setValue(1.0)
    spacing_mm.setValue(24.0)
    padding_mm.setValue(8.0)
    apply_button = set_button_role(qtwidgets.QPushButton("Auto Place"), "primary")
    rerun_button = set_button_role(qtwidgets.QPushButton("Re-run Placement"), "secondary")
    overlay_button = set_button_role(qtwidgets.QPushButton("Overlay Visibility"), "ghost")
    constraint_overlay_button = set_button_role(qtwidgets.QPushButton("Issues"), "ghost")
    snap_button = set_button_role(qtwidgets.QPushButton("Snap"), "ghost")
    measurements_button = set_button_role(qtwidgets.QPushButton("Guides"), "ghost")
    conflict_lines_button = set_button_role(qtwidgets.QPushButton("Conflict Lines"), "ghost")
    constraint_labels_button = set_button_role(qtwidgets.QPushButton("Issue Labels"), "ghost")
    set_tooltip(preset, "Choose the placement strategy used by Auto Place.")
    set_tooltip(grid_mm, "Grid size for snapping and placement.")
    set_tooltip(spacing_mm, "Target spacing between component centers.")
    set_tooltip(padding_mm, "Clearance at the controller edge.")
    set_tooltip(apply_button, "Place all components with the current settings.")
    set_tooltip(rerun_button, "Run Auto Place again with the current settings.")
    set_tooltip(overlay_button, "Show or hide helper graphics such as outlines and cutout previews.")
    set_tooltip(constraint_overlay_button, "Show or hide validation issues in the view.")
    set_tooltip(snap_button, "Turn snap to grid on or off.")
    set_tooltip(measurements_button, "Show or hide measurement guides.")
    set_tooltip(conflict_lines_button, "Show or hide conflict lines.")
    set_tooltip(constraint_labels_button, "Show or hide issue labels.")
    primary_actions = create_button_row_layout(qtwidgets, apply_button, rerun_button, spacing=6)
    button_row = qtwidgets.QGridLayout()
    button_row.setContentsMargins(0, 0, 0, 0)
    button_row.setHorizontalSpacing(8)
    button_row.setVerticalSpacing(6)
    actions = [
        overlay_button,
        constraint_overlay_button,
        snap_button,
        measurements_button,
        conflict_lines_button,
        constraint_labels_button,
    ]
    for index, button in enumerate(actions):
        row, column = divmod(index, 2)
        button_row.addWidget(button, row, column)
    summary = create_text_panel(qtwidgets, max_height=72)
    overlay_status = create_text_panel(qtwidgets, max_height=72)
    status = create_status_label(qtwidgets)
    settings_box, settings_layout = create_form_section_widget(qtwidgets, "Placement Settings", spacing=4)
    settings_layout.addRow("Preset", preset)
    settings_layout.addRow("Grid (mm)", grid_mm)
    settings_layout.addRow("Spacing (mm)", spacing_mm)
    settings_layout.addRow("Padding (mm)", padding_mm)
    overlay_box, overlay_layout = create_section_widget(qtwidgets, "View Helpers", spacing=6)
    overlay_layout.addLayout(button_row)
    diagnostics_box, diagnostics_layout = create_section_widget(qtwidgets, "Feedback", spacing=6)
    diagnostics_row = qtwidgets.QHBoxLayout()
    diagnostics_row.setSpacing(6)
    diagnostics_row.addWidget(overlay_status, 1)
    diagnostics_row.addWidget(summary, 1)
    diagnostics_layout.addLayout(diagnostics_row)
    layout.addWidget(intro)
    layout.addWidget(settings_box)
    layout.addLayout(primary_actions)
    layout.addWidget(overlay_box)
    layout.addWidget(diagnostics_box)
    layout.addWidget(status)
    layout.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
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
