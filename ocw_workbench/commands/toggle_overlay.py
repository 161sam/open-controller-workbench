from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class ToggleOverlayCommand(BaseCommand):
    ICON_NAME = "toggle_overlay"

    def GetResources(self):
        return self.resources(
            "Overlay Visibility",
            "Show or hide helper graphics such as component outlines, cutout previews and keepouts.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

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
