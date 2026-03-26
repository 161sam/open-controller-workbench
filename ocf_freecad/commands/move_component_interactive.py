from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class MoveComponentInteractiveCommand(BaseCommand):
    ICON_NAME = "move_component"

    def GetResources(self):
        return self.resources(
            "Move Component",
            "Arm move mode for the currently selected component.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="components")
            settings = panel.arm_move_for_selection()
            show_info("Move Component", f"Move mode armed for '{settings['move_component_id']}'.")
        except Exception as exc:
            show_error("Move Component", exc)
