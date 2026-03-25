from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class SnapToGridCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Snap To Grid",
            "ToolTip": "Snap the selected component to the active grid",
        }

    def Activated(self):
        import FreeCAD as App

        from ocf_freecad.workbench import ensure_workbench_ui

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        ensure_workbench_ui(doc, focus="components").snap_selection_to_grid()
