from __future__ import annotations

from ocf_freecad.commands.base import BaseCommand
from ocf_freecad.gui.runtime import show_error, show_info


class ToggleConstraintLabelsCommand(BaseCommand):
    ICON_NAME = "constraint_labels"

    def GetResources(self):
        return self.resources(
            "Constraint Labels",
            "Show or hide text labels for validation feedback.",
        )

    def Activated(self):
        try:
            import FreeCAD as App

            from ocf_freecad.workbench import ensure_workbench_ui

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            panel = ensure_workbench_ui(doc, focus="layout")
            settings = panel.toggle_constraint_labels()
            show_info(
                "Constraint Labels",
                f"Constraint labels {'enabled' if settings['constraint_labels_enabled'] else 'disabled'}.",
            )
        except Exception as exc:
            show_error("Toggle Constraint Labels", exc)
