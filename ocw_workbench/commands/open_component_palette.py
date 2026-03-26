from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.gui.runtime import show_error


class OpenComponentPaletteCommand(BaseCommand):
    ICON_NAME = "component_palette"

    def GetResources(self):
        return self.resources(
            "Component Palette",
            "Open the component palette for icon-based component selection.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import ensure_component_palette_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            ensure_component_palette_ui(doc)
            log_to_console("Component Palette command opened the palette dock.")
        except Exception as exc:
            show_error("Component Palette", exc)
