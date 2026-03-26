from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.command_views import show_add_component_dialog
from ocf_freecad.gui.runtime import show_error


class SelectComponentCommand(BaseCommand):
    ICON_NAME = "select_component"

    def GetResources(self):
        return self.resources("Components", "Open the components panel for selection and editing")

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            ensure_workbench_ui(doc, focus="components")
            show_add_component_dialog(doc)
        except Exception as exc:
            show_error("Components", exc)
