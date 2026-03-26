from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.command_views import show_create_controller_dialog
from ocf_freecad.gui.runtime import show_error


class CreateFromTemplateCommand(BaseCommand):
    ICON_NAME = "create_controller"

    def GetResources(self):
        return self.resources("Create Controller", "Open the template and variant create workflow")

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="create")
            show_create_controller_dialog(doc)
        except Exception as exc:
            show_error("Create Controller", exc)
