from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class CreateFromTemplateCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Create Controller",
            "ToolTip": "Open the template and variant create workflow",
        }

    def Activated(self):
        import FreeCAD as App
        import FreeCADGui as Gui

        from ocf_freecad.gui.panels.create_panel import CreatePanel

        doc = App.ActiveDocument or App.newDocument("Controller")
        Gui.Control.showDialog(CreatePanel(doc))
