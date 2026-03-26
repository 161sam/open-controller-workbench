from __future__ import annotations

from typing import Any

from ocf_freecad.gui.panels._common import (
    FallbackButton,
    FallbackLabel,
    FallbackText,
    load_qt,
    set_label_text,
    set_text,
)
from ocf_freecad.services.controller_service import ControllerService


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
        self._messages: list[dict[str, Any]] = []
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        context = self.controller_service.get_ui_context(self.doc)
        validation = context.get("validation")
        if isinstance(validation, dict):
            self._render_report(validation)
        else:
            set_text(self.form["results"], "Run validation to check spacing, edge distance, and placement issues.")
            set_label_text(self.form["status"], "No validation results yet.")

    def validate(self) -> dict[str, Any]:
        report = self.controller_service.validate_layout(self.doc)
        self._render_report(report)
        self._publish_status("Validation complete.")
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

    def handle_validate_clicked(self) -> None:
        try:
            self.validate()
        except Exception as exc:
            self._publish_status(str(exc))

    def accept(self) -> bool:
        self.validate()
        return True

    def _render_report(self, report: dict[str, Any]) -> None:
        summary = report["summary"]
        self._messages = list(report["errors"]) + list(report["warnings"])
        lines = [
            f"Errors: {summary['error_count']}",
            f"Warnings: {summary['warning_count']}",
            "",
        ]
        for item in report["errors"]:
            lines.append(_format_message("ERROR", item))
        for item in report["warnings"]:
            lines.append(_format_message("WARN", item))
        set_text(self.form["results"], "\n".join(lines))
        set_label_text(
            self.form["status"],
            f"{summary['error_count']} errors, {summary['warning_count']} warnings.",
        )

    def _publish_status(self, message: str) -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        button = self.form["validate_button"]
        if hasattr(button, "clicked"):
            button.clicked.connect(self.handle_validate_clicked)


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "validate_button": FallbackButton("Validate Layout"),
            "results": FallbackText(),
            "status": FallbackLabel(),
        }

    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    intro = qtwidgets.QLabel("Review spacing, edge distance, and placement issues before the next iteration.")
    intro.setWordWrap(True)
    validate_button = qtwidgets.QPushButton("Validate Layout")
    results = qtwidgets.QPlainTextEdit()
    results.setReadOnly(True)
    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    layout.addWidget(intro)
    layout.addWidget(validate_button)
    layout.addWidget(results)
    layout.addWidget(status)
    return {
        "widget": widget,
        "validate_button": validate_button,
        "results": results,
        "status": status,
    }


def _format_message(severity: str, item: dict[str, Any]) -> str:
    component_id = item.get("source_component") or "-"
    description = item.get("description") or item["message"]
    return f"[{severity}] {component_id}: {item['message']} ({description})"
