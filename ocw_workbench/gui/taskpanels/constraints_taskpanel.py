from __future__ import annotations

from typing import Any

from ocw_workbench.services.controller_service import ControllerService


class ConstraintsTaskPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.form = _build_constraints_form()

    def validate(self) -> dict[str, Any]:
        report = self.controller_service.validate_layout(self.doc)
        _set_text(self.form["results"], _format_report(report))
        return report

    def accept(self) -> bool:
        self.validate()
        return True


def _build_constraints_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {"results": _FallbackText()}

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    results = QtWidgets.QPlainTextEdit()
    results.setReadOnly(True)
    layout.addWidget(results)
    return {"widget": widget, "results": results}


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Errors: {report['summary']['error_count']}",
        f"Warnings: {report['summary']['warning_count']}",
        "",
    ]
    for item in report["errors"]:
        lines.append(f"[ERROR] {item['rule_id']}: {item['message']}")
    for item in report["warnings"]:
        lines.append(f"[WARN] {item['rule_id']}: {item['message']}")
    return "\n".join(lines)


def _set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
    else:
        widget.text = value


class _FallbackText:
    def __init__(self) -> None:
        self.text = ""
