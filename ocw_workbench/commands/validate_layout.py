from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand


class ValidateLayoutCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Validate Layout",
            "ToolTip": "Show constraint validation results",
        }

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocw_workbench.gui.taskpanels.constraints_taskpanel import ConstraintsTaskPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(ConstraintsTaskPanel(doc))
