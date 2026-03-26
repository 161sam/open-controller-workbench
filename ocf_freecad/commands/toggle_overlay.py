from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ToggleOverlayCommand(BaseCommand):
    ICON_NAME = "toggle_overlay"

    def GetResources(self):
        return self.resources(
            "Overlay",
            "Show or hide the controller overlay in the active view.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            settings = panel.toggle_overlay()
            show_info(
                "Overlay",
                f"Overlay {'enabled' if settings['overlay_enabled'] else 'disabled'}.",
                details=panel.form["overlay_status"].text()
                if hasattr(panel.form["overlay_status"], "text")
                else None,
            )
        except Exception as exc:
            show_error("Toggle Overlay", exc)
