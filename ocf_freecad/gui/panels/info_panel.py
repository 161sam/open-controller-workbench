from __future__ import annotations

from typing import Any

from ocf_freecad.services.controller_service import ControllerService


class InfoPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.form = _build_form()
        self.refresh()

    def refresh(self) -> str:
        context = self.controller_service.get_ui_context(self.doc)
        lines = [
            f"Template: {context['template_id'] or '-'}",
            f"Variant: {context['variant_id'] or '-'}",
            f"Selected: {context['selection'] or '-'}",
            f"Components: {context['component_count']}",
        ]
        if context["component_types"]:
            type_summary = ", ".join(
                f"{component_type} x{count}" for component_type, count in sorted(context["component_types"].items())
            )
            lines.append(f"Types: {type_summary}")
        layout = context.get("layout") or {}
        if layout:
            lines.append(f"Layout: {layout.get('strategy', '-')}")
        validation = context.get("validation")
        if isinstance(validation, dict):
            summary = validation.get("summary", {})
            lines.append(
                f"Validation: {summary.get('error_count', 0)} errors / {summary.get('warning_count', 0)} warnings"
            )
        overrides = context.get("overrides") or {}
        if overrides:
            lines.append(f"Overrides: {', '.join(sorted(overrides.keys()))}")
        text = "\n".join(lines)
        _set_text(self.form["info"], text)
        return text

    def accept(self) -> bool:
        self.refresh()
        return True


def _build_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {"info": _FallbackText()}

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    info = QtWidgets.QPlainTextEdit()
    info.setReadOnly(True)
    layout.addWidget(info)
    return {"widget": widget, "info": info}


def _set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
    else:
        widget.text = value


class _FallbackText:
    def __init__(self) -> None:
        self.text = ""
