from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ShowConstraintOverlayCommand(BaseCommand):
    ICON_NAME = "constraint_overlay"

    def GetResources(self):
        return self.resources(
            "Constraint Overlay",
            "Show or hide validation warnings and errors in the overlay.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="constraints")
            settings = panel.toggle_constraint_overlay()
            show_info(
                "Constraint Overlay",
                f"Constraint overlay {'enabled' if settings['show_constraints'] else 'disabled'}.",
            )
        except Exception as exc:
            show_error("Constraint Overlay", exc)
