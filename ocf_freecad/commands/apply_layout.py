from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ApplyLayoutCommand(BaseCommand):
    ICON_NAME = "apply_layout"

    def GetResources(self):
        return self.resources("Apply Auto Layout", "Open the layout panel and apply auto layout")

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            result = panel.layout_panel.apply_auto_layout()
            show_info(
                "Auto Layout",
                f"Placed {len(result['placed_components'])} components, {len(result['unplaced_component_ids'])} unplaced.",
            )
        except Exception as exc:
            show_error("Apply Auto Layout", exc)
