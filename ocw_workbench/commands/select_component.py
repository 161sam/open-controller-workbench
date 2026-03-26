from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class SelectComponentCommand(BaseCommand):
    ICON_NAME = "select_component"

    def GetResources(self):
        return self.resources(
            "Component Manager",
            "Review, edit, and reposition components in the current controller.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            ensure_workbench_ui(doc, focus="components")
            log_to_console("Component Manager command focused the Components panel.")
        except Exception as exc:
            show_error("Components", exc)
