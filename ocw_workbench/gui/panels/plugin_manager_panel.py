from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import load_qt, set_size_policy, set_text, text_value, wrap_widget_in_scroll_area
from ocw_workbench.gui.widgets.plugin_details import PluginDetailsWidget
from ocw_workbench.gui.widgets.plugin_list import PluginListWidget
from ocw_workbench.services.plugin_manager_service import PluginManagerService
from ocw_workbench.services.plugin_pack_service import PluginPackService
from ocw_workbench.services.plugin_registry_service import PluginRegistryService


class PluginManagerPanel:
    def __init__(
        self,
        plugin_manager_service: PluginManagerService | None = None,
        plugin_pack_service: PluginPackService | None = None,
        plugin_registry_service: PluginRegistryService | None = None,
        on_status: Any | None = None,
        on_plugins_changed: Any | None = None,
    ) -> None:
        self.plugin_manager_service = plugin_manager_service or PluginManagerService()
        self.plugin_pack_service = plugin_pack_service or PluginPackService(
            plugin_manager_service=self.plugin_manager_service
        )
        self.plugin_registry_service = plugin_registry_service or PluginRegistryService()
        self.on_status = on_status
        self.on_plugins_changed = on_plugins_changed
        self.form = _build_form()
        self.widget = self.form["widget"]
        cached_url = self.plugin_registry_service.last_registry_url()
        if cached_url:
            set_text(self.form["plugin_list"].parts["remote_url"], cached_url)
        self._connect_events()
        self.refresh()

    def refresh(self) -> list[dict[str, Any]]:
        entries = self.plugin_manager_service.list_plugins(filter_by=self.form["plugin_list"].selected_filter())
        self.form["plugin_list"].set_entries(entries)
        self.form["plugin_details"].set_plugin(self.form["plugin_list"].selected())
        self.load_cached_remote_registry()
        return entries

    def selected_plugin_id(self) -> str | None:
        selected = self.form["plugin_list"].selected()
        return None if selected is None else str(selected["id"])

    def enable_selected_plugin(self) -> dict[str, Any]:
        plugin_id = self.selected_plugin_id()
        if plugin_id is None:
            raise ValueError("No plugin selected")
        plugin = self.plugin_manager_service.set_enabled(plugin_id, True)
        self.refresh()
        self._publish_status(f"Enabled plugin '{plugin_id}'.")
        self._notify_plugins_changed()
        return plugin

    def disable_selected_plugin(self) -> dict[str, Any]:
        plugin_id = self.selected_plugin_id()
        if plugin_id is None:
            raise ValueError("No plugin selected")
        plugin = self.plugin_manager_service.set_enabled(plugin_id, False)
        self.refresh()
        self._publish_status(f"Disabled plugin '{plugin_id}'.")
        self._notify_plugins_changed()
        return plugin

    def reload_plugins(self) -> list[dict[str, Any]]:
        plugins = self.plugin_manager_service.reload_plugins()
        self.refresh()
        self._publish_status(f"Refreshed plugins ({len(plugins)} discovered).")
        self._notify_plugins_changed()
        return plugins

    def export_selected_plugin_pack(self) -> dict[str, Any]:
        plugin_id = self.selected_plugin_id()
        if plugin_id is None:
            raise ValueError("No plugin selected")
        output_path = text_value(self.form["plugin_list"].parts["export_path"]).strip()
        if not output_path:
            raise ValueError("Export path is required")
        result = self.plugin_pack_service.export_plugin_pack(plugin_id, output_path)
        self._publish_status(f"Exported plugin '{plugin_id}' to {result['zip_path']}.")
        return result

    def import_plugin_pack(self) -> dict[str, Any]:
        zip_path = text_value(self.form["plugin_list"].parts["import_path"]).strip()
        if not zip_path:
            raise ValueError("Import ZIP path is required")
        result = self.plugin_pack_service.import_plugin_pack(zip_path)
        self.refresh()
        self._publish_status(f"Imported plugin '{result['plugin_id']}'.")
        self._notify_plugins_changed()
        return result

    def load_cached_remote_registry(self) -> dict[str, Any]:
        url = text_value(self.form["plugin_list"].parts["remote_url"]).strip()
        result = self.plugin_registry_service.load_cached_registry(url)
        if result["url"] and result["url"] != url:
            set_text(self.form["plugin_list"].parts["remote_url"], result["url"])
        self.form["plugin_list"].set_remote_entries(result["entries"])
        return result

    def refresh_remote_registry(self) -> dict[str, Any]:
        url = text_value(self.form["plugin_list"].parts["remote_url"]).strip()
        result = self.plugin_registry_service.refresh_registry(url)
        self.form["plugin_list"].set_remote_entries(result["entries"])
        source = result["source"]
        suffix = f" ({source})" if source else ""
        self._publish_status(f"Loaded remote plugin registry from {result['url']}{suffix}.")
        return result

    def download_selected_remote_plugin(self) -> dict[str, Any]:
        selected = self.form["plugin_list"].selected_remote()
        if selected is None:
            raise ValueError("No remote plugin selected")
        url = text_value(self.form["plugin_list"].parts["remote_url"]).strip()
        output_path = text_value(self.form["plugin_list"].parts["download_path"]).strip()
        if not output_path:
            raise ValueError("Download path is required")
        result = self.plugin_registry_service.download_plugin(url, str(selected["id"]), output_path)
        self._publish_status(f"Downloaded remote plugin '{selected['id']}' to {result['output_path']}.")
        return result

    def handle_selection_changed(self, *_args: Any) -> None:
        self.form["plugin_list"].sync_selection_state()
        self.form["plugin_details"].set_plugin(self.form["plugin_list"].selected())

    def handle_filter_changed(self, *_args: Any) -> None:
        self.refresh()

    def handle_enable_clicked(self) -> None:
        try:
            self.enable_selected_plugin()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_disable_clicked(self) -> None:
        try:
            self.disable_selected_plugin()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_refresh_clicked(self) -> None:
        try:
            self.reload_plugins()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_export_clicked(self) -> None:
        try:
            self.export_selected_plugin_pack()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_import_clicked(self) -> None:
        try:
            self.import_plugin_pack()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_remote_selection_changed(self, *_args: Any) -> None:
        self.form["plugin_list"].sync_remote_selection_state()

    def handle_remote_refresh_clicked(self) -> None:
        try:
            self.refresh_remote_registry()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_download_clicked(self) -> None:
        try:
            self.download_selected_remote_plugin()
        except Exception as exc:
            self._publish_status(str(exc))

    def _connect_events(self) -> None:
        parts = self.form["plugin_list"].parts
        parts["plugin_combo"].currentIndexChanged.connect(self.handle_selection_changed)
        parts["filter_combo"].currentIndexChanged.connect(self.handle_filter_changed)
        parts["enable_button"].clicked.connect(self.handle_enable_clicked)
        parts["disable_button"].clicked.connect(self.handle_disable_clicked)
        parts["refresh_button"].clicked.connect(self.handle_refresh_clicked)
        parts["export_button"].clicked.connect(self.handle_export_clicked)
        parts["import_button"].clicked.connect(self.handle_import_clicked)
        parts["remote_plugin_combo"].currentIndexChanged.connect(self.handle_remote_selection_changed)
        parts["remote_refresh_button"].clicked.connect(self.handle_remote_refresh_clicked)
        parts["download_button"].clicked.connect(self.handle_download_clicked)

    def _publish_status(self, message: str) -> None:
        if self.on_status is not None:
            self.on_status(message)

    def _notify_plugins_changed(self) -> None:
        if self.on_plugins_changed is not None:
            self.on_plugins_changed()


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    plugin_list = PluginListWidget()
    plugin_details = PluginDetailsWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "plugin_list": plugin_list,
            "plugin_details": plugin_details,
        }

    content = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(content)
    set_size_policy(plugin_list.widget, horizontal="expanding", vertical="preferred")
    set_size_policy(plugin_details.widget, horizontal="expanding", vertical="preferred")
    layout.addWidget(plugin_list.widget)
    layout.addWidget(plugin_details.widget)
    layout.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "plugin_list": plugin_list,
        "plugin_details": plugin_details,
    }
