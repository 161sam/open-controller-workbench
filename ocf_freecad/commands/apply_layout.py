from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class ApplyLayoutCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Apply Auto Layout",
            "ToolTip": "Open the layout panel and apply auto layout",
        }

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocf_freecad.gui.panels.layout_panel import LayoutPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(LayoutPanel(doc))
