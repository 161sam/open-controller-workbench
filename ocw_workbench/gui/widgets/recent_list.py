from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import FallbackButton, FallbackCombo, current_text, load_qt, set_combo_items


class RecentListWidget:
    def __init__(self) -> None:
        self._lookup: dict[str, dict[str, str]] = {}
        self.parts = _build_widget()
        self.widget = self.parts["widget"]

    def set_entries(self, entries: list[dict[str, str]]) -> None:
        labels = [entry["label"] for entry in entries]
        self._lookup = {entry["label"]: entry for entry in entries}
        set_combo_items(self.parts["combo"], labels)

    def selected(self) -> dict[str, str] | None:
        return self._lookup.get(current_text(self.parts["combo"]))


def _build_widget() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "combo": FallbackCombo(),
            "apply_button": FallbackButton("Load Recent"),
        }

    widget = qtwidgets.QGroupBox("Recent")
    layout = qtwidgets.QVBoxLayout(widget)
    combo = qtwidgets.QComboBox()
    apply_button = qtwidgets.QPushButton("Load Recent")
    layout.addWidget(combo)
    layout.addWidget(apply_button)
    return {"widget": widget, "combo": combo, "apply_button": apply_button}
