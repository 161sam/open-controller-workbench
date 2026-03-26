from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import (
    configure_combo_box,
    configure_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    current_text,
    load_qt,
    set_combo_items,
    set_enabled,
    set_label_text,
    set_size_policy,
    set_text,
)
from ocw_workbench.gui.widgets.plugin_status_badge import PluginStatusBadgeWidget


class PluginListWidget:
    def __init__(self) -> None:
        self._lookup: dict[str, dict[str, Any]] = {}
        self._remote_lookup: dict[str, dict[str, Any]] = {}
        self.parts = _build_widget()
        self.widget = self.parts["widget"]

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        labels = [_entry_label(entry) for entry in entries]
        self._lookup = {label: entry for label, entry in zip(labels, entries)}
        set_combo_items(self.parts["plugin_combo"], labels)
        self.sync_selection_state()

    def selected(self) -> dict[str, Any] | None:
        return self._lookup.get(current_text(self.parts["plugin_combo"]))

    def selected_filter(self) -> str:
        return current_text(self.parts["filter_combo"]) or "all"

    def set_remote_entries(self, entries: list[dict[str, Any]]) -> None:
        labels = [_remote_entry_label(entry) for entry in entries]
        self._remote_lookup = {label: entry for label, entry in zip(labels, entries)}
        set_combo_items(self.parts["remote_plugin_combo"], labels)
        self.sync_remote_selection_state()

    def selected_remote(self) -> dict[str, Any] | None:
        return self._remote_lookup.get(current_text(self.parts["remote_plugin_combo"]))

    def sync_remote_selection_state(self) -> None:
        selected = self.selected_remote()
        if selected is None:
            set_label_text(self.parts["remote_summary"], "No remote plugin selected.")
            set_text(self.parts["remote_details"], "Load a remote registry to inspect available plugin packs.")
            set_enabled(self.parts["download_button"], False)
            return
        set_label_text(self.parts["remote_summary"], _remote_summary(selected))
        set_text(self.parts["remote_details"], _format_remote_details(selected))
        set_enabled(self.parts["download_button"], bool(selected.get("download_url")))

    def sync_selection_state(self) -> None:
        selected = self.selected()
        if selected is None:
            self.parts["status_badge"].set_status("disabled", "No Plugin")
            set_label_text(self.parts["summary"], "No plugin selected.")
            set_enabled(self.parts["enable_button"], False)
            set_enabled(self.parts["disable_button"], False)
            set_enabled(self.parts["export_button"], False)
            return
        self.parts["status_badge"].set_status(selected["status"], selected["status_label"])
        set_label_text(self.parts["summary"], _summary(selected))
        set_enabled(self.parts["enable_button"], not selected["enabled"])
        set_enabled(self.parts["disable_button"], selected["enabled"] and not selected.get("non_disableable", False))
        set_enabled(self.parts["export_button"], bool(selected.get("is_data_plugin")))


def _entry_label(entry: dict[str, Any]) -> str:
    marker = {
        "enabled": "[on]",
        "disabled": "[off]",
        "error": "[err]",
        "incompatible": "[api]",
    }.get(entry["status"], "[?]")
    return f"{marker} {entry['name']} ({entry['id']})"


def _summary(entry: dict[str, Any]) -> str:
    origin = "internal" if entry.get("is_internal") else "external"
    locked = "required" if entry.get("non_disableable") else "toggleable"
    return f"{entry['type']} | {origin} | {locked}"


def _remote_entry_label(entry: dict[str, Any]) -> str:
    name = str(entry.get("name") or entry["id"])
    return f"{name} ({entry['id']})"


def _remote_summary(entry: dict[str, Any]) -> str:
    plugin_type = str(entry.get("type") or "plugin_pack")
    version = str(entry.get("version") or "-")
    return f"{plugin_type} | v{version}"


def _format_remote_details(entry: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"ID: {entry['id']}",
            f"Name: {entry.get('name') or entry['id']}",
            f"Version: {entry.get('version') or '-'}",
            f"Type: {entry.get('type') or '-'}",
            f"Author: {entry.get('author') or '-'}",
            f"Description: {entry.get('description') or '-'}",
            f"Download: {entry.get('download_url') or '-'}",
        ]
    )


def _build_widget() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    badge = PluginStatusBadgeWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "filter_combo": FallbackCombo(["all", "enabled", "disabled", "errors"]),
            "plugin_combo": FallbackCombo(),
            "enable_button": FallbackButton("Enable"),
            "disable_button": FallbackButton("Disable"),
            "refresh_button": FallbackButton("Refresh"),
            "export_path": FallbackText(".plugin_packs"),
            "import_path": FallbackText(""),
            "export_button": FallbackButton("Export ZIP"),
            "import_button": FallbackButton("Import ZIP"),
            "summary": FallbackLabel(""),
            "status_badge": badge,
            "remote_url": FallbackText(""),
            "remote_refresh_button": FallbackButton("Load Registry"),
            "remote_plugin_combo": FallbackCombo(),
            "remote_summary": FallbackLabel("No remote plugin selected."),
            "remote_details": FallbackText("Load a remote registry to inspect available plugin packs."),
            "download_path": FallbackText(".plugin_downloads"),
            "download_button": FallbackButton("Download ZIP"),
        }

    widget = qtwidgets.QGroupBox("Plugin List")
    layout = qtwidgets.QVBoxLayout(widget)
    filter_combo = qtwidgets.QComboBox()
    filter_combo.addItems(["all", "enabled", "disabled", "errors"])
    plugin_combo = qtwidgets.QComboBox()
    enable_button = qtwidgets.QPushButton("Enable")
    disable_button = qtwidgets.QPushButton("Disable")
    refresh_button = qtwidgets.QPushButton("Refresh")
    export_path = qtwidgets.QLineEdit(".plugin_packs")
    import_path = qtwidgets.QLineEdit()
    export_button = qtwidgets.QPushButton("Export ZIP")
    import_button = qtwidgets.QPushButton("Import ZIP")
    summary = qtwidgets.QLabel("")
    summary.setWordWrap(True)
    remote_url = qtwidgets.QLineEdit()
    remote_refresh_button = qtwidgets.QPushButton("Load Registry")
    remote_plugin_combo = qtwidgets.QComboBox()
    remote_summary = qtwidgets.QLabel("No remote plugin selected.")
    remote_summary.setWordWrap(True)
    for combo in (filter_combo, plugin_combo, remote_plugin_combo):
        configure_combo_box(combo)
    remote_details = qtwidgets.QPlainTextEdit()
    configure_text_panel(remote_details, max_height=120)
    download_path = qtwidgets.QLineEdit(".plugin_downloads")
    download_button = qtwidgets.QPushButton("Download ZIP")
    for child in (filter_combo, plugin_combo, export_path, import_path, remote_url, remote_plugin_combo, download_path):
        set_size_policy(child, horizontal="expanding", vertical="preferred")
    row = qtwidgets.QHBoxLayout()
    row.addWidget(enable_button)
    row.addWidget(disable_button)
    row.addWidget(refresh_button)
    export_row = qtwidgets.QHBoxLayout()
    export_row.addWidget(qtwidgets.QLabel("Export"))
    export_row.addWidget(export_path, 1)
    export_row.addWidget(export_button)
    import_row = qtwidgets.QHBoxLayout()
    import_row.addWidget(qtwidgets.QLabel("Import"))
    import_row.addWidget(import_path, 1)
    import_row.addWidget(import_button)
    remote_url_row = qtwidgets.QHBoxLayout()
    remote_url_row.addWidget(qtwidgets.QLabel("Registry"))
    remote_url_row.addWidget(remote_url, 1)
    remote_url_row.addWidget(remote_refresh_button)
    remote_download_row = qtwidgets.QHBoxLayout()
    remote_download_row.addWidget(qtwidgets.QLabel("Download"))
    remote_download_row.addWidget(download_path, 1)
    remote_download_row.addWidget(download_button)
    layout.addWidget(filter_combo)
    layout.addWidget(plugin_combo)
    layout.addWidget(badge.widget)
    layout.addWidget(summary)
    layout.addLayout(row)
    layout.addLayout(export_row)
    layout.addLayout(import_row)
    layout.addSpacing(8)
    layout.addWidget(qtwidgets.QLabel("Remote Registry"))
    layout.addLayout(remote_url_row)
    layout.addWidget(remote_plugin_combo)
    layout.addWidget(remote_summary)
    layout.addWidget(remote_details)
    layout.addLayout(remote_download_row)
    return {
        "widget": widget,
        "filter_combo": filter_combo,
        "plugin_combo": plugin_combo,
        "enable_button": enable_button,
        "disable_button": disable_button,
        "refresh_button": refresh_button,
        "export_path": export_path,
        "import_path": import_path,
        "export_button": export_button,
        "import_button": import_button,
        "summary": summary,
        "status_badge": badge,
        "remote_url": remote_url,
        "remote_refresh_button": remote_refresh_button,
        "remote_plugin_combo": remote_plugin_combo,
        "remote_summary": remote_summary,
        "remote_details": remote_details,
        "download_path": download_path,
        "download_button": download_button,
    }
