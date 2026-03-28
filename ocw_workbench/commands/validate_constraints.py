from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class ValidateConstraintsCommand(BaseCommand):
    ICON_NAME = "validate_constraints"

    def GetResources(self):
        return self.resources(
            "Validate Layout",
            "Check spacing, edge distance, and placement rules.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="constraints")
            report = panel.constraints_panel.validate()
            panel.set_status(
                f"Validation finished: {report['summary']['error_count']} errors, {report['summary']['warning_count']} warnings."
            )
            log_to_console(
                f"Constraint validation finished with {report['summary']['error_count']} errors and "
                f"{report['summary']['warning_count']} warnings."
            )
        except Exception as exc:
            show_error("Validate Constraints", exc)
