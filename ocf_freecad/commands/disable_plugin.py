from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class DisablePluginCommand(BaseCommand):
    ICON_NAME = "plugin_disable"

    def GetResources(self):
        return self.resources("Disable Selected Plugin", "Disable the selected plugin in the plugin manager")

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            result = ensure_workbench_ui(doc, focus="plugins").disable_selected_plugin()
            show_info("Disable Plugin", f"Disabled plugin '{result['id']}'.")
        except Exception as exc:
            show_error("Disable Plugin", exc)
