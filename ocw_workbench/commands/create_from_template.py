from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class CreateFromTemplateCommand(BaseCommand):
    ICON_NAME = "create_controller"

    def GetResources(self):
        return self.resources(
            "Create Controller",
            "Create a new controller from a template or variant.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="create")
            log_to_console("Create Controller command focused the Create panel.")
        except Exception as exc:
            show_error("Create Controller", exc)
