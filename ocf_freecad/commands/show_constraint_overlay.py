from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class ShowConstraintOverlayCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Constraint Overlay",
            "ToolTip": "Toggle constraint warnings and errors in the overlay",
        }

    def Activated(self):
        import FreeCAD as App

        from ocf_freecad.workbench import ensure_workbench_ui

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        ensure_workbench_ui(doc, focus="constraints").toggle_constraint_overlay()
