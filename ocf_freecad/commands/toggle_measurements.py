from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ToggleMeasurementsCommand(BaseCommand):
    ICON_NAME = "measurements"

    def GetResources(self):
        return self.resources(
            "Measurements",
            "Show or hide measurement markers in the overlay.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            settings = panel.toggle_measurements()
            show_info("Measurements", f"Measurements {'enabled' if settings['measurements_enabled'] else 'disabled'}.")
        except Exception as exc:
            show_error("Toggle Measurements", exc)
