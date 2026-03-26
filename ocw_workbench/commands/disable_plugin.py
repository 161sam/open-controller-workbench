from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class DisablePluginCommand(BaseCommand):
    ICON_NAME = "plugin_disable"

    def GetResources(self):
        return self.resources(
            "Disable Plugin",
            "Disable the selected plugin in the Plugin Manager.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            result = ensure_workbench_ui(doc, focus="plugins").disable_selected_plugin()
            show_info("Disable Plugin", f"Disabled plugin '{result['id']}'.")
        except Exception as exc:
            show_error("Disable Plugin", exc)
