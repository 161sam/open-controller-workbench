from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class ValidateConstraintsCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Validate Constraints",
            "ToolTip": "Open the constraint feedback panel",
        }

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocf_freecad.gui.panels.constraints_panel import ConstraintsPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(ConstraintsPanel(doc))
