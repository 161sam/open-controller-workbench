from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ReloadPluginsCommand(BaseCommand):
    ICON_NAME = "plugin_reload"

    def GetResources(self):
        return self.resources(
            "Refresh Plugins",
            "Rescan plugin packs and refresh their status.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument or App.newDocument("Controller")
            result = ensure_workbench_ui(doc, focus="plugins").reload_plugins()
            show_info("Refresh Plugins", f"Discovered {len(result)} plugins.")
        except Exception as exc:
            show_error("Refresh Plugins", exc)
