from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class OpenPluginManagerCommand(BaseCommand):
    ICON_NAME = "plugin_manager"

    def GetResources(self):
        return self.resources(
            "Plugin Manager",
            "Open the Plugins step in the OCW dock.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import open_workbench_dock

            doc = App.ActiveDocument or App.newDocument("Controller")
            open_workbench_dock(doc, focus="plugins")
            log_to_console("Plugin Manager command focused the Plugins panel.")
        except Exception as exc:
            show_error("Plugin Manager", exc)
