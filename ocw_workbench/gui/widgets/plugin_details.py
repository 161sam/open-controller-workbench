from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import (
    FallbackLabel,
    FallbackText,
    configure_text_panel,
    load_qt,
    set_label_text,
    set_text,
)
from ocw_workbench.gui.widgets.plugin_status_badge import PluginStatusBadgeWidget


class PluginDetailsWidget:
    def __init__(self) -> None:
        self.parts = _build_widget()
        self.widget = self.parts["widget"]

    def set_plugin(self, plugin: dict[str, Any] | None) -> None:
        if plugin is None:
            set_label_text(self.parts["title"], "Plugin Details")
            self.parts["status_badge"].set_status("disabled", "No Selection")
            set_text(self.parts["details"], "Select a plugin to inspect its metadata and current load status.")
            return
        set_label_text(self.parts["title"], plugin["name"])
        self.parts["status_badge"].set_status(plugin["status"], plugin["status_label"])
        set_text(self.parts["details"], _format_details(plugin))


def _format_details(plugin: dict[str, Any]) -> str:
    entrypoints = plugin.get("entrypoints", {})
    return "\n".join(
        [
            f"ID: {plugin['id']}",
            f"Version: {plugin['version']}",
            f"API Version: {plugin['api_version']}",
            f"Type: {plugin['type']}",
            f"Author: {plugin.get('author') or '-'}",
            f"Description: {plugin.get('description') or '-'}",
            f"Capabilities: {', '.join(plugin.get('capabilities', [])) or '-'}",
            f"Dependencies: {', '.join(plugin.get('dependencies', [])) or '-'}",
            f"Internal: {'yes' if plugin.get('is_internal') else 'no'}",
            f"Required: {'yes' if plugin.get('non_disableable') else 'no'}",
            "Entrypoints:",
            *([f"- {name}: {value}" for name, value in entrypoints.items() if value not in {None, ''}] or ["-"]),
            "Warnings:",
            *([f"- {message}" for message in plugin.get("warnings", [])] or ["-"]),
            "Errors:",
            *([f"- {message}" for message in plugin.get("errors", [])] or ["-"]),
        ]
    )


def _build_widget() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    badge = PluginStatusBadgeWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "title": FallbackLabel("Plugin Details"),
            "status_badge": badge,
            "details": FallbackText(),
        }

    widget = qtwidgets.QGroupBox("Plugin Details")
    layout = qtwidgets.QVBoxLayout(widget)
    title = qtwidgets.QLabel("Plugin Details")
    details = qtwidgets.QPlainTextEdit()
    configure_text_panel(details, max_height=150)
    layout.addWidget(title)
    layout.addWidget(badge.widget)
    layout.addWidget(details)
    return {
        "widget": widget,
        "title": title,
        "status_badge": badge,
        "details": details,
    }
