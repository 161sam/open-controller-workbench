from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class ToggleMeasurementsCommand(BaseCommand):
    ICON_NAME = "measurements"

    def GetResources(self):
        return self.resources(
            "Guides",
            "Show or hide measurement guides in the 3D view.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            settings = panel.toggle_measurements()
            show_info("Measurements", f"Measurements {'enabled' if settings['measurements_enabled'] else 'disabled'}.")
        except Exception as exc:
            show_error("Toggle Measurements", exc)
