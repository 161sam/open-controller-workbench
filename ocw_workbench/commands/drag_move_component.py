from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class DragMoveComponentCommand(BaseCommand):
    ICON_NAME = "move_component"

    def GetResources(self):
        return self.resources(
            "Drag Move Component",
            "Drag a component to a new position in the 3D view.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui, start_component_drag_mode

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            ensure_workbench_ui(doc, focus="components")
            started = start_component_drag_mode(doc)
            if started:
                show_info("Drag Move Component", "Hover a component, drag to move it, and press ESC to cancel.")
        except Exception as exc:
            show_error("Drag Move Component", exc)
