from __future__ import annotations

from typing import Any

from ocf_freecad.gui.panels._common import FallbackText, load_qt, set_text
from ocf_freecad.services.controller_service import ControllerService


class InfoPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.form = _build_form()
        self.widget = self.form["widget"]
        self.refresh()

    def refresh(self) -> str:
        context = self.controller_service.get_ui_context(self.doc)
        overrides = context.get("overrides") or {}
        override_lines = [f"{key}: {value}" for key, value in sorted(overrides.items())]
        ui = context.get("ui") or {}
        lines = [
            f"Template: {context['template_id'] or '-'}",
            f"Variant: {context['variant_id'] or '-'}",
            f"Selected: {context['selection'] or '-'}",
            f"Components: {context['component_count']}",
        ]
        component_types = context.get("component_types") or {}
        if component_types:
            lines.append(
                "Types: " + ", ".join(f"{component_type} x{count}" for component_type, count in sorted(component_types.items()))
            )
        layout = context.get("layout") or {}
        if layout:
            lines.append(f"Layout: {layout.get('strategy', '-')}")
        validation = context.get("validation")
        if isinstance(validation, dict):
            summary = validation.get("summary", {})
            lines.append(
                f"Validation: {summary.get('error_count', 0)} errors / {summary.get('warning_count', 0)} warnings"
            )
        if ui:
            lines.append(
                "Overlay: "
                f"{'on' if ui.get('overlay_enabled', True) else 'off'}, "
                f"constraints {'on' if ui.get('show_constraints', True) else 'off'}, "
                f"grid {ui.get('grid_mm', 1.0)} mm"
            )
            if ui.get("move_component_id"):
                lines.append(f"Move Mode: {ui['move_component_id']}")
        if override_lines:
            lines.append("")
            lines.append("Overrides:")
            lines.extend(override_lines)
        text = "\n".join(lines)
        set_text(self.form["info"], text)
        return text

    def accept(self) -> bool:
        self.refresh()
        return True


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {"widget": object(), "info": FallbackText()}

    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    info = qtwidgets.QPlainTextEdit()
    info.setReadOnly(True)
    layout.addWidget(info)
    return {"widget": widget, "info": info}
