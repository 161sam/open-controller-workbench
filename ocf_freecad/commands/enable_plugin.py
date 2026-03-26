from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class EnablePluginCommand(BaseCommand):
    ICON_NAME = "plugin_enable"

    def GetResources(self):
        return self.resources("Enable Selected Plugin", "Enable the selected plugin in the plugin manager")

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            result = ensure_workbench_ui(doc, focus="plugins").enable_selected_plugin()
            show_info("Enable Plugin", f"Enabled plugin '{result['id']}'.")
        except Exception as exc:
            show_error("Enable Plugin", exc)
