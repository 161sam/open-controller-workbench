from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import FallbackLabel, load_qt, set_label_text

STATUS_COLORS = {
    "enabled": "#2e7d32",
    "disabled": "#6b7280",
    "error": "#c62828",
    "incompatible": "#c57b00",
}


class PluginStatusBadgeWidget:
    def __init__(self) -> None:
        self.parts = _build_widget()
        self.widget = self.parts["widget"]

    def set_status(self, status: str, label: str | None = None) -> None:
        set_label_text(self.parts["label"], label or status.replace("_", " ").title())
        if hasattr(self.parts["label"], "setStyleSheet"):
            color = STATUS_COLORS.get(status, "#374151")
            self.parts["label"].setStyleSheet(
                f"background: {color}; color: white; border-radius: 4px; padding: 2px 6px; font-weight: 600;"
            )


def _build_widget() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        label = FallbackLabel("Unknown")
        return {"widget": label, "label": label}

    label = qtwidgets.QLabel("Unknown")
    return {"widget": label, "label": label}
