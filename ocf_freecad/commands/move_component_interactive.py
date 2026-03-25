from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class MoveComponentInteractiveCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Move Component",
            "ToolTip": "Arm move mode for the selected component",
        }

    def Activated(self):
        import FreeCAD as App

        from ocf_freecad.workbench import ensure_workbench_ui

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        ensure_workbench_ui(doc, focus="components").arm_move_for_selection()
