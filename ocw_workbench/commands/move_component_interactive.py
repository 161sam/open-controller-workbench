from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class MoveComponentInteractiveCommand(BaseCommand):
    ICON_NAME = "move_component"

    def GetResources(self):
        return self.resources(
            "Move Component",
            "Prepare 3D move mode for the selected component.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="components")
            settings = panel.arm_move_for_selection()
            show_info("Move Component", f"3D move ready for '{settings['move_component_id']}'.")
        except Exception as exc:
            show_error("Move Component", exc)
