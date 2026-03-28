from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand


class MoveComponentCommand(BaseCommand):
    ICON_NAME = "move_component"

    def GetResources(self):
        return self.resources("Move Component", "Open the move task panel.")

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocw_workbench.gui.taskpanels.layout_taskpanel import LayoutTaskPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(LayoutTaskPanel(doc))
