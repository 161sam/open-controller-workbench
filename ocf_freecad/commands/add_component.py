from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.command_views import show_add_component_dialog
from ocf_freecad.gui.runtime import show_error


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

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_workbench_ui(doc, focus="components")
            show_add_component_dialog(doc)
        except Exception as exc:
            show_error("Add Component", exc)
