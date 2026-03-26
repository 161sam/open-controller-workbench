from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class ShowConstraintOverlayCommand(BaseCommand):
    ICON_NAME = "constraint_overlay"

    def GetResources(self):
        return self.resources(
            "Constraint Checks",
            "Show or hide validation warnings and spacing checks in the overlay.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

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
