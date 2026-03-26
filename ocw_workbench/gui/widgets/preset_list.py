from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import FallbackButton, FallbackCombo, FallbackText, current_text, load_qt, set_combo_items


class PresetListWidget:
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
            "name": FallbackText(),
            "load_button": FallbackButton("Load Preset"),
            "save_button": FallbackButton("Save Preset"),
        }

    widget = qtwidgets.QGroupBox("Presets")
    layout = qtwidgets.QFormLayout(widget)
    combo = qtwidgets.QComboBox()
    name = qtwidgets.QLineEdit()
    load_button = qtwidgets.QPushButton("Load Preset")
    save_button = qtwidgets.QPushButton("Save Preset")
    actions = qtwidgets.QHBoxLayout()
    actions.addWidget(load_button)
    actions.addWidget(save_button)
    layout.addRow("Saved", combo)
    layout.addRow("Name", name)
    layout.addRow("", actions)
    return {
        "widget": widget,
        "combo": combo,
        "name": name,
        "load_button": load_button,
        "save_button": save_button,
    }
