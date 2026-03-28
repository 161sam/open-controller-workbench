from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand


class AutoLayoutCommand(BaseCommand):
    ICON_NAME = "apply_layout"

    def GetResources(self):
        return self.resources("Auto Place", "Open the Auto Place task panel.")

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocw_workbench.gui.taskpanels.layout_taskpanel import LayoutTaskPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(LayoutTaskPanel(doc))
