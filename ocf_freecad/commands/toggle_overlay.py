from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand


class ToggleOverlayCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Toggle Overlay",
            "ToolTip": "Show or hide the visual controller overlay",
        }

    def Activated(self):
        import FreeCAD as App

        from ocf_freecad.workbench import ensure_workbench_ui

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document")
        ensure_workbench_ui(doc, focus="layout").toggle_overlay()
