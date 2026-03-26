from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.command_views import show_constraint_report_dialog
from ocf_freecad.gui.runtime import show_error


class ValidateConstraintsCommand(BaseCommand):
    ICON_NAME = "validate_constraints"

    def GetResources(self):
        return self.resources(
            "Validate Layout",
            "Validate spacing, edge distance, and placement constraints.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            ensure_workbench_ui(doc, focus="constraints")
            show_constraint_report_dialog(doc)
        except Exception as exc:
            show_error("Validate Constraints", exc)
