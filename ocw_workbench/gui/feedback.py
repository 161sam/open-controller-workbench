from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import set_label_text

_STATUS_STYLES = {
    "info": "color: #e5e7eb; background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 6px 8px;",
    "success": "color: #d1fae5; background: #052e2b; border: 1px solid #0f766e; border-radius: 8px; padding: 6px 8px;",
    "warning": "color: #fef3c7; background: #3f2a0b; border: 1px solid #b45309; border-radius: 8px; padding: 6px 8px;",
    "error": "color: #fee2e2; background: #3b0d12; border: 1px solid #b91c1c; border-radius: 8px; padding: 6px 8px;",
}


def apply_status_message(widget: Any, message: str, level: str = "info") -> None:
    set_label_text(widget, message)
    style = _STATUS_STYLES.get(level, _STATUS_STYLES["info"])
    if hasattr(widget, "setStyleSheet"):
        widget.setStyleSheet(style)
    else:
        widget.level = level


def format_toggle_message(subject: str, enabled: bool, hint: str | None = None) -> str:
    state = "enabled" if enabled else "disabled"
    if hint:
        return f"{subject} {state}. {hint}"
    return f"{subject} {state}."


def format_layout_message(result: dict[str, Any], strategy: str) -> tuple[str, str]:
    placed = len(result.get("placed_components", []))
    unplaced = len(result.get("unplaced_component_ids", []))
    warnings = len(result.get("warnings", []))
    level = "success" if unplaced == 0 and warnings == 0 else "warning"
    message = (
        f"Auto Place finished with {strategy}: {placed} placed, "
        f"{unplaced} unplaced, {warnings} warnings. Review the Constraints tab next."
    )
    return (message, level)


def format_validation_message(report: dict[str, Any]) -> tuple[str, str]:
    summary = report.get("summary", {})
    errors = int(summary.get("error_count", 0))
    warnings = int(summary.get("warning_count", 0))
    if errors:
        return (f"Validation found {errors} errors and {warnings} warnings. Fix the highlighted components before export.", "error")
    if warnings:
        return (f"Validation finished with {warnings} warnings and no blocking errors.", "warning")
    return ("Validation passed with no errors or warnings.", "success")


def friendly_ui_error(prefix: str, exc: Exception, hint: str | None = None) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "no active freecad document" in lowered or "no active freecad document" in prefix.lower():
        return f"{prefix}. Open or create a FreeCAD document first."
    if "no component selected" in lowered:
        return f"{prefix}. Select a component first."
    if "no template selected" in lowered:
        return f"{prefix}. Choose a template first."
    if "part::" in lowered or "shape" in lowered or "cutout" in lowered or "boolean" in lowered:
        return f"{prefix}. The model geometry could not be updated. Check placement, rotation and controller dimensions."
    if "overlay" in lowered:
        return f"{prefix}. The visual overlay could not be refreshed. Try toggling the overlay again."
    if "validation" in lowered or "constraint" in lowered:
        return f"{prefix}. Validation data could not be refreshed. Re-run Validate after checking component placement."
    if hint:
        return f"{prefix}. {message} {hint}"
    return f"{prefix}. {message}"
