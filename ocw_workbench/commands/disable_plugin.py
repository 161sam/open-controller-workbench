from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class DisablePluginCommand(BaseCommand):
    ICON_NAME = "plugin_disable"

    def GetResources(self):
        return self.resources(
            "Disable Plugin",
            "Disable the plugin currently selected in Plugin Manager.",
        )

    def IsActive(self):
        try:
            import FreeCAD as App
            from ocw_workbench.workbench import has_selected_plugin_in_open_manager

            return has_selected_plugin_in_open_manager(App.ActiveDocument)
        except Exception:
            return False

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import disable_selected_plugin_direct

            doc = App.ActiveDocument or App.newDocument("Controller")
            result = disable_selected_plugin_direct(doc)
            show_info("Disable Plugin", f"Disabled plugin '{result['id']}'.")
        except Exception as exc:
            show_error("Disable Plugin", exc)
