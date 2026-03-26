from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.command_views import show_plugin_manager_dialog
from ocf_freecad.gui.runtime import show_error


class OpenPluginManagerCommand(BaseCommand):
    ICON_NAME = "plugin_manager"

    def GetResources(self):
        return self.resources(
            "Open Plugin Manager",
            "Inspect plugin status, metadata and local enable or disable state",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="plugins")
            show_plugin_manager_dialog()
        except Exception as exc:
            show_error("Plugin Manager", exc)
