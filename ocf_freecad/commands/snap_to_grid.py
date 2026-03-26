from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class SnapToGridCommand(BaseCommand):
    ICON_NAME = "snap_to_grid"

    def GetResources(self):
        return self.resources(
            "Snap To Grid",
            "Snap the selected component to the current grid.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="components")
            result = panel.snap_selection_to_grid()
            show_info("Snap To Grid", f"Snapped '{result['component_id']}' to grid.")
        except Exception as exc:
            show_error("Snap To Grid", exc)
