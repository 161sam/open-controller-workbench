from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class SelectComponentCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Components",
            "ToolTip": "Open the components panel for selection and editing",
        }

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocf_freecad.gui.panels.components_panel import ComponentsPanel

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        Gui.Control.showDialog(ComponentsPanel(doc))
