from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class ToggleConflictLinesCommand(BaseCommand):
    ICON_NAME = "conflict_lines"

    def GetResources(self):
        return self.resources(
            "Conflict Lines",
            "Show or hide conflict connection lines in the overlay.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            settings = panel.toggle_conflict_lines()
            show_info(
                "Conflict Lines",
                f"Conflict lines {'enabled' if settings['conflict_lines_enabled'] else 'disabled'}.",
            )
        except Exception as exc:
            show_error("Toggle Conflict Lines", exc)
