from __future__ import annotations

from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, format_validation_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
    build_panel_container,
    create_button_row_layout,
    create_form_layout,
    create_compact_header_widget,
    create_hint_label,
    create_inline_status_widget,
    create_section_widget,
    create_status_label,
    create_text_panel,
    FallbackButton,
    FallbackLabel,
    FallbackText,
    load_qt,
    set_enabled,
    set_button_role,
    set_label_text,
    set_size_policy,
    set_text,
    set_tooltip,
    wrap_widget_in_scroll_area,
)
from ocw_workbench.services.controller_service import ControllerService


class ConstraintsPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        on_selection_changed: Any | None = None,
        on_validated: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.on_selection_changed = on_selection_changed
        self.on_validated = on_validated
        self.on_status = on_status
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._configure_tooltips()
        self._messages: list[dict[str, Any]] = []
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        context = self.controller_service.get_ui_context(self.doc)
        validation = context.get("validation")
        component_count = int(context.get("component_count", 0))
        self._set_validation_scope(component_count)
        if isinstance(validation, dict):
            self._render_report(validation)
        else:
            self._messages = []
            self._set_summary_counts(errors=0, warnings=0)
            self._set_review_state("Not run", "info")
            self._set_result_overview("Run Validate Layout to check spacing, edge distance, and placement issues.")
            self._set_widget_visible(self.form["success_box"], False)
            self._set_widget_visible(self.form["list_box"], False)
            self._set_widget_visible(self.form["detail_box"], False)
            self._set_widget_visible(self.form["empty_state_box"], True)
            self._clear_results()
            self._clear_detail()
            self._set_next_step_message("Run Validate after layout or component edits.")
            apply_status_message(self.form["status"], "No validation results yet.", level="info")

    def validate(self) -> dict[str, Any]:
        report = self.controller_service.validate_layout(self.doc)
        self._render_report(report)
        message, level = format_validation_message(report)
        self._publish_status(message, level=level)
        if self.on_validated is not None:
            self.on_validated(report)
        return report

    def select_issue_component(self, index: int) -> str | None:
        if index < 0 or index >= len(self._messages):
            return None
        component_id = self._messages[index].get("source_component")
        if component_id:
            self.controller_service.select_component(self.doc, component_id)
            if self.on_selection_changed is not None:
                self.on_selection_changed(component_id)
            self._publish_status(f"Selected component '{component_id}' from validation report.")
        return component_id

    def handle_result_selection_changed(self) -> None:
        issue_index = self._selected_issue_index()
        if issue_index is None:
            self._clear_detail("Select an issue to inspect details and focus its component.")
            set_enabled(self.form["focus_button"], False)
            return
        item = self._messages[issue_index]
        self._render_issue_detail(item)
        set_enabled(self.form["focus_button"], bool(item.get("source_component")))

    def handle_result_activated(self, *_args: Any) -> None:
        self.handle_focus_clicked()

    def handle_focus_clicked(self) -> None:
        issue_index = self._selected_issue_index()
        if issue_index is None:
            return
        self.select_issue_component(issue_index)

    def handle_validate_clicked(self) -> None:
        try:
            self.validate()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not validate the controller", exc), level="error")

    def accept(self) -> bool:
        self.validate()
        return True

    def _render_report(self, report: dict[str, Any]) -> None:
        summary = report["summary"]
        self._messages = list(report["errors"]) + list(report["warnings"])
        has_issues = bool(self._messages)
        self._set_summary_counts(
            errors=int(summary.get("error_count", 0)),
            warnings=int(summary.get("warning_count", 0)),
        )
        self._set_result_overview(_result_overview_text(summary))
        self._set_widget_visible(self.form["empty_state_box"], False)
        self._set_widget_visible(self.form["success_box"], not has_issues)
        self._set_widget_visible(self.form["list_box"], has_issues)
        self._set_widget_visible(self.form["detail_box"], has_issues)
        self._populate_results(report)
        message, level = format_validation_message(report)
        apply_status_message(self.form["status"], message, level=level)
        if self._messages:
            self._render_issue_detail(self._messages[0])
            self.handle_result_selection_changed()
        else:
            set_label_text(self.form["success_title"], "Layout valid - ready for export")
            set_label_text(self.form["success_message"], "No blocking issues or warnings were found. Continue with Plugins or export workflows.")
            self._clear_detail("Validation passed. No issues to review.")
            set_enabled(self.form["focus_button"], False)

    def _publish_status(self, message: str, level: str = "info") -> None:
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        button = self.form["validate_button"]
        if hasattr(button, "clicked"):
            button.clicked.connect(self.handle_validate_clicked)
        results = self.form.get("results")
        if hasattr(results, "itemSelectionChanged"):
            results.itemSelectionChanged.connect(self.handle_result_selection_changed)
        item_activated = getattr(results, "itemActivated", None)
        if hasattr(item_activated, "connect"):
            item_activated.connect(self.handle_result_activated)
        focus_button = self.form.get("focus_button")
        if hasattr(focus_button, "clicked"):
            focus_button.clicked.connect(self.handle_focus_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["validate_button"], "Run spacing, overlap and edge-distance checks for the current controller.")
        set_tooltip(self.form["focus_button"], "Select the component related to the currently highlighted issue.")

    def _set_summary_counts(self, *, errors: int, warnings: int) -> None:
        set_label_text(self.form["error_count"], str(errors))
        set_label_text(self.form["warning_count"], str(warnings))
        if errors > 0:
            state_text = "Needs fixes"
            state_level = "error"
        elif warnings > 0:
            state_text = "Warnings only"
            state_level = "warning"
        else:
            state_text = "Ready"
            state_level = "success"
        set_label_text(self.form["state_value"], state_text)
        if hasattr(self.form["state_value"], "setStyleSheet"):
            self.form["state_value"].setStyleSheet(_summary_value_style(state_level))
        self._set_review_state(_review_state_text(errors, warnings), state_level)
        self._set_next_step_message(_next_step_text(errors, warnings))

    def _set_result_overview(self, message: str) -> None:
        set_label_text(self.form["results_overview"], message)

    def _set_review_state(self, message: str, level: str) -> None:
        set_label_text(self.form["review_value"], message)
        if hasattr(self.form["review_value"], "setStyleSheet"):
            self.form["review_value"].setStyleSheet(_summary_value_style(level))

    def _set_validation_scope(self, component_count: int) -> None:
        label = "component" if component_count == 1 else "components"
        set_label_text(self.form["validation_scope"], f"Reviewing {component_count} {label} before Plugins.")

    def _set_next_step_message(self, message: str) -> None:
        set_label_text(self.form["next_step"], message)

    def _set_widget_visible(self, widget: Any, visible: bool) -> None:
        if hasattr(widget, "setVisible"):
            widget.setVisible(visible)
            return
        try:
            widget.visible = bool(visible)
        except Exception:
            return

    def _clear_results(self) -> None:
        results = self.form["results"]
        if hasattr(results, "clear"):
            results.clear()

    def _populate_results(self, report: dict[str, Any]) -> None:
        _qtcore, _qtgui, qtwidgets = load_qt()
        results = self.form["results"]
        if qtwidgets is None or not hasattr(qtwidgets, "QTreeWidgetItem"):
            lines: list[str] = []
            errors = [_format_message("ERROR", item) for item in report.get("errors", [])]
            warnings = [_format_message("WARN", item) for item in report.get("warnings", [])]
            if errors:
                lines.extend(["Errors:", *errors])
            if warnings:
                if lines:
                    lines.append("")
                lines.extend(["Warnings:", *warnings])
            set_text(results, "\n".join(lines) if lines else "No issues found.")
            return
        results.clear()
        groups = (
            ("Errors", "errors", report.get("errors", []), "error"),
            ("Warnings", "warnings", report.get("warnings", []), "warning"),
        )
        message_index = 0
        for title, _key, items, level in groups:
            parent = qtwidgets.QTreeWidgetItem([title, str(len(items)), "", ""])
            if hasattr(parent, "setData") and _qtcore is not None:
                parent.setData(0, _qtcore.Qt.UserRole, None)
            results.addTopLevelItem(parent)
            brush = _brush_for_level(level)
            if brush is not None and hasattr(parent, "setForeground"):
                for column in range(4):
                    parent.setForeground(column, brush)
            for item in items:
                severity_text = _severity_label(level)
                component_text = str(item.get("source_component") or "Global")
                rule_text = _rule_label(item)
                summary_text = str(item.get("message") or item.get("description") or "Issue")
                row = qtwidgets.QTreeWidgetItem(
                    [
                        severity_text,
                        component_text,
                        rule_text,
                        summary_text,
                    ]
                )
                if hasattr(row, "setData") and _qtcore is not None:
                    row.setData(0, _qtcore.Qt.UserRole, message_index)
                    row.setData(0, _qtcore.Qt.UserRole + 1, dict(item))
                if brush is not None and hasattr(row, "setForeground"):
                    row.setForeground(0, brush)
                background_brush = _background_brush_for_level(level)
                if background_brush is not None and hasattr(row, "setBackground"):
                    row.setBackground(0, background_brush)
                parent.addChild(row)
                message_index += 1
            if hasattr(parent, "setExpanded"):
                parent.setExpanded(True)
        if hasattr(results, "expandAll"):
            results.expandAll()
        if hasattr(results, "resizeColumnToContents"):
            results.resizeColumnToContents(0)
            results.resizeColumnToContents(1)
            results.resizeColumnToContents(2)
        first_issue = None
        for top_index in range(results.topLevelItemCount() if hasattr(results, "topLevelItemCount") else 0):
            parent = results.topLevelItem(top_index)
            if parent is not None and hasattr(parent, "childCount") and parent.childCount() > 0:
                first_issue = parent.child(0)
                break
        if first_issue is not None and hasattr(results, "setCurrentItem"):
            results.setCurrentItem(first_issue)

    def _selected_issue_index(self) -> int | None:
        _qtcore, _qtgui, _qtwidgets = load_qt()
        results = self.form["results"]
        if _qtcore is None or not hasattr(results, "currentItem"):
            return None
        current = results.currentItem()
        if current is None or not hasattr(current, "data"):
            return None
        value = current.data(0, _qtcore.Qt.UserRole)
        return value if isinstance(value, int) else None

    def _render_issue_detail(self, item: dict[str, Any]) -> None:
        severity = str(item.get("severity") or "info")
        set_label_text(self.form["detail_severity"], _severity_label(severity))
        if hasattr(self.form["detail_severity"], "setStyleSheet"):
            self.form["detail_severity"].setStyleSheet(_detail_badge_style(severity))
        set_label_text(self.form["detail_component"], str(item.get("source_component") or "Global"))
        set_label_text(self.form["detail_rule"], _rule_label(item))
        set_label_text(self.form["detail_message"], str(item.get("message") or "Issue"))
        set_text(self.form["detail_description"], str(item.get("description") or item.get("message") or ""))
        set_label_text(
            self.form["detail_hint"],
            "Double-click or use Focus to select the related component."
            if item.get("source_component")
            else "This finding is not tied to a single component yet.",
        )

    def _clear_detail(self, message: str = "No issue selected.") -> None:
        set_label_text(self.form["detail_severity"], "No issue")
        if hasattr(self.form["detail_severity"], "setStyleSheet"):
            self.form["detail_severity"].setStyleSheet(_detail_badge_style("info"))
        set_label_text(self.form["detail_component"], "-")
        set_label_text(self.form["detail_rule"], "-")
        set_label_text(self.form["detail_message"], message)
        set_text(self.form["detail_description"], message)
        set_label_text(self.form["detail_hint"], "Run validation and select a finding to inspect it.")


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "validate_button": FallbackButton("Validate Layout"),
            "validation_scope": FallbackLabel("Reviewing 0 components before Plugins."),
            "error_count": FallbackLabel("0"),
            "warning_count": FallbackLabel("0"),
            "state_value": FallbackLabel("Ready"),
            "review_value": FallbackLabel("Not run"),
            "results_overview": FallbackLabel(),
            "success_box": FallbackLabel(),
            "success_title": FallbackLabel("Layout valid - ready for export"),
            "success_message": FallbackLabel(),
            "empty_state_box": FallbackLabel(),
            "list_box": FallbackLabel(),
            "detail_box": FallbackLabel(),
            "results": FallbackText(),
            "next_step": FallbackLabel("Run Validate after layout or component edits."),
            "detail_severity": FallbackLabel("No issue"),
            "detail_component": FallbackLabel("-"),
            "detail_rule": FallbackLabel("-"),
            "detail_message": FallbackLabel("No issue selected."),
            "detail_description": FallbackText(),
            "detail_hint": FallbackLabel("Run validation and select a finding to inspect it."),
            "focus_button": FallbackButton("Focus In Components"),
            "status": FallbackLabel(),
        }

    content, layout = build_panel_container(qtwidgets)
    intro = create_status_label(qtwidgets, "Step 4 of 5. Validate before Plugins or export work.")
    validate_button = set_button_role(qtwidgets.QPushButton("Validate Layout"), "primary")
    set_tooltip(validate_button, "Run spacing, overlap and edge-distance checks for the current controller.")
    focus_button = set_button_role(qtwidgets.QPushButton("Focus In Components"), "secondary")
    set_enabled(focus_button, False)
    actions = create_button_row_layout(qtwidgets, validate_button, focus_button, spacing=6)
    validation_scope = create_hint_label(qtwidgets, "Reviewing 0 components before Plugins.")

    summary_row = qtwidgets.QHBoxLayout()
    summary_row.setSpacing(6)
    error_count = _summary_card(qtwidgets, "Errors", "0", "error")
    warning_count = _summary_card(qtwidgets, "Warnings", "0", "warning")
    state_value = _summary_card(qtwidgets, "State", "Ready", "success")
    review_value = _summary_card(qtwidgets, "Review", "Not run", "info")
    summary_row.addWidget(error_count["card"], 1)
    summary_row.addWidget(warning_count["card"], 1)
    summary_row.addWidget(state_value["card"], 1)
    summary_row.addWidget(review_value["card"], 1)

    results_overview = create_status_label(qtwidgets, "Run validation to populate the issue list.")
    next_step = create_hint_label(qtwidgets, "Run Validate after layout or component edits.")
    success_box, success_layout = create_section_widget(qtwidgets, "Validation Result", spacing=6)
    success_title = qtwidgets.QLabel("Layout valid - ready for export")
    if hasattr(success_title, "setStyleSheet"):
        success_title.setStyleSheet("color: #8dd4b4; font-size: 15px; font-weight: 700;")
    success_message = create_status_label(qtwidgets, "No issues found.")
    success_layout.addWidget(success_title)
    success_layout.addWidget(success_message)

    results = qtwidgets.QTreeWidget()
    results.setColumnCount(4)
    results.setHeaderLabels(["State", "Component", "Rule", "Summary"])
    if hasattr(results, "setRootIsDecorated"):
        results.setRootIsDecorated(True)
    if hasattr(results, "setAlternatingRowColors"):
        results.setAlternatingRowColors(True)
    if hasattr(results, "setUniformRowHeights"):
        results.setUniformRowHeights(True)
    if hasattr(results, "setItemsExpandable"):
        results.setItemsExpandable(True)
    if hasattr(results, "setAllColumnsShowFocus"):
        results.setAllColumnsShowFocus(True)
    if hasattr(results, "setSelectionBehavior") and hasattr(qtwidgets, "QAbstractItemView"):
        results.setSelectionBehavior(qtwidgets.QAbstractItemView.SelectRows)
    if hasattr(results, "setMinimumHeight"):
        results.setMinimumHeight(180)
    if hasattr(results, "setStyleSheet"):
        results.setStyleSheet(
            "QTreeWidget { background: #0f172a; color: #e5e7eb; border: 1px solid #334155; border-radius: 8px; }"
            "QTreeWidget::item { padding: 4px 2px; }"
            "QTreeWidget::item:selected { background: #172554; color: #eff6ff; }"
            "QHeaderView::section { background: #111827; color: #94a3b8; border: none; border-bottom: 1px solid #334155; padding: 4px 6px; }"
        )
    set_size_policy(results, horizontal="expanding", vertical="expanding")

    list_box, list_layout = create_section_widget(qtwidgets, "Issues To Resolve", spacing=6)
    list_hint = create_hint_label(qtwidgets, "Errors block release. Select a row, then focus the affected component.")
    list_layout.addWidget(list_hint)
    list_layout.addWidget(results, 1)
    empty_state_box, empty_state_layout = create_section_widget(qtwidgets, "Validation Result", spacing=6)
    empty_state_message = create_hint_label(qtwidgets, "No validation data yet. Run Validate Layout to see blocking issues, warnings, and export readiness.")
    empty_state_layout.addWidget(empty_state_message)

    detail_box, detail_layout = create_section_widget(qtwidgets, "Selected Finding", spacing=6)
    detail_severity = qtwidgets.QLabel("No issue")
    detail_severity.setStyleSheet(_detail_badge_style("info"))
    detail_component = qtwidgets.QLabel("-")
    detail_component.setStyleSheet("color: #e5e7eb; font-weight: 600;")
    detail_header = create_compact_header_widget(
        qtwidgets,
        detail_component,
        secondary=detail_severity,
        spacing=6,
        detail_spacing=2,
    )

    detail_meta = create_form_layout(qtwidgets, spacing=4)
    detail_rule = create_status_label(qtwidgets, "-")
    detail_message = create_status_label(qtwidgets, "No issue selected.")
    detail_description = create_text_panel(qtwidgets, max_height=84)
    if hasattr(detail_description, "setStyleSheet"):
        detail_description.setStyleSheet(
            "background: #0c1420; color: #d9e2ec; border: 1px solid #293446; border-radius: 6px; padding: 6px;"
        )
    detail_hint = create_hint_label(qtwidgets, "Run validation and select a finding to inspect it.")
    detail_meta.addRow("Rule", detail_rule)
    detail_meta.addRow("Message", detail_message)
    detail_layout.addWidget(detail_header)
    detail_layout.addLayout(detail_meta)
    detail_layout.addWidget(detail_description)
    detail_layout.addWidget(detail_hint)

    status = create_status_label(qtwidgets)
    layout.addWidget(intro)
    layout.addWidget(validation_scope)
    layout.addLayout(actions)
    layout.addLayout(summary_row)
    layout.addWidget(results_overview)
    layout.addWidget(next_step)
    layout.addWidget(success_box)
    layout.addWidget(empty_state_box)
    layout.addWidget(list_box, 1)
    layout.addWidget(detail_box)
    layout.addWidget(status)
    layout.addStretch(1)
    if hasattr(success_box, "setVisible"):
        success_box.setVisible(False)
    if hasattr(list_box, "setVisible"):
        list_box.setVisible(False)
    if hasattr(detail_box, "setVisible"):
        detail_box.setVisible(False)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "validate_button": validate_button,
        "focus_button": focus_button,
        "validation_scope": validation_scope,
        "error_count": error_count["value"],
        "warning_count": warning_count["value"],
        "state_value": state_value["value"],
        "review_value": review_value["value"],
        "results_overview": results_overview,
        "success_box": success_box,
        "success_title": success_title,
        "success_message": success_message,
        "empty_state_box": empty_state_box,
        "list_box": list_box,
        "detail_box": detail_box,
        "results": results,
        "next_step": next_step,
        "detail_severity": detail_severity,
        "detail_component": detail_component,
        "detail_rule": detail_rule,
        "detail_message": detail_message,
        "detail_description": detail_description,
        "detail_hint": detail_hint,
        "status": status,
    }


def _format_message(severity: str, item: dict[str, Any]) -> str:
    component_id = item.get("source_component") or "-"
    description = item.get("description") or item["message"]
    return f"[{severity}] {component_id}: {item['message']} ({description})"


def _result_overview_text(summary: dict[str, Any]) -> str:
    errors = int(summary.get("error_count", 0))
    warnings = int(summary.get("warning_count", 0))
    total = int(summary.get("total_count", errors + warnings))
    if errors:
        return f"{total} findings. Fix blocking errors first."
    if warnings:
        return f"{total} findings. Review warnings next."
    return "No findings. The layout is currently clear."


def _review_state_text(errors: int, warnings: int) -> str:
    if errors > 0:
        return "Fix blockers"
    if warnings > 0:
        return "Review warnings"
    return "Ready for Plugins"


def _next_step_text(errors: int, warnings: int) -> str:
    if errors > 0:
        return "Return to Components, fix the blocking issues, then run Validate again."
    if warnings > 0:
        return "Warnings do not block release, but review them before moving on to Plugins."
    return "Validate is clear. Continue with Plugins or export-related workflows."


def _summary_card(qtwidgets: Any, title: str, value: str, level: str) -> dict[str, Any]:
    card = qtwidgets.QFrame()
    layout = qtwidgets.QVBoxLayout(card)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(2)
    title_label = qtwidgets.QLabel(title)
    title_label.setStyleSheet("color: #7f92a8; font-size: 10px; font-weight: 600;")
    value_label = qtwidgets.QLabel(value)
    value_label.setStyleSheet(_summary_value_style(level))
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    card.setStyleSheet("QFrame { background: #121b28; border: 1px solid #223043; border-radius: 6px; }")
    return {"card": card, "value": value_label}


def _summary_value_style(level: str) -> str:
    palette = {
        "success": "#8dd4b4",
        "warning": "#e8c66a",
        "error": "#f0a6a6",
        "info": "#d9e2ec",
    }
    foreground = palette.get(level, palette["info"])
    return (
        f"color: {foreground};"
        "font-size: 16px;"
        "font-weight: 700;"
        "background: transparent;"
        "padding: 0px;"
    )


def _brush_for_level(level: str) -> Any:
    _qtcore, qtgui, _qtwidgets = load_qt()
    if qtgui is None:
        return None
    color = {
        "error": "#fca5a5",
        "warning": "#fcd34d",
        "success": "#86efac",
    }.get(level, "#cbd5e1")
    return qtgui.QBrush(qtgui.QColor(color))


def _background_brush_for_level(level: str) -> Any:
    _qtcore, qtgui, _qtwidgets = load_qt()
    if qtgui is None:
        return None
    color = {
        "error": "#3b0d12",
        "warning": "#3f2a0b",
        "success": "#052e2b",
    }.get(level, "#111827")
    return qtgui.QBrush(qtgui.QColor(color))


def _severity_label(level: str) -> str:
    labels = {
        "error": "Blocking",
        "warning": "Warning",
        "success": "Clear",
        "info": "Info",
    }
    return labels.get(str(level).lower(), str(level).title())


def _rule_label(item: dict[str, Any]) -> str:
    raw = str(item.get("code") or item.get("rule_id") or "-")
    if raw == "-":
        return raw
    return raw.replace("_", " ").title()


def _detail_badge_style(level: str) -> str:
    palette = {
        "success": ("#8dd4b4", "#173327"),
        "warning": ("#e8c66a", "#3a2b11"),
        "error": ("#f0a6a6", "#3d171a"),
        "info": ("#d9e2ec", "#1a2433"),
    }
    foreground, background = palette.get(str(level).lower(), palette["info"])
    return (
        f"color: {foreground};"
        f"background: {background};"
        "border-radius: 7px;"
        "padding: 3px 8px;"
        "font-weight: 700;"
    )
