from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class OpenPluginManagerCommand(BaseCommand):
    ICON_NAME = "plugin_manager"

    def GetResources(self):
        return self.resources(
            "Plugin Manager",
            "View installed plugins and their current status.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="plugins")
            log_to_console("Plugin Manager command focused the Plugins panel.")
        except Exception as exc:
            show_error("Plugin Manager", exc)
