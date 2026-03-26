from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class AddComponentCommand(BaseCommand):
    ICON_NAME = "add_component"

    def GetResources(self):
        return self.resources(
            "Add Component",
            "Add a component from the library to the current controller.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="components")
            log_to_console("Add Component command focused the Components panel.")
        except Exception as exc:
            show_error("Add Component", exc)
