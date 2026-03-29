from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class ApplyLayoutCommand(BaseCommand):
    ICON_NAME = "apply_layout"

    def GetResources(self):
        return self.resources(
            "Auto Place",
            "Place the current components with the active layout preset.",
        )

    def IsActive(self):
        return self._has_controller()

    def Activated(self):
        try:
            import FreeCAD as App
            from ocw_workbench.services.controller_service import ControllerService
            from ocw_workbench.services.interaction_service import InteractionService
            from ocw_workbench.workbench import _refresh_active_workbench_if_open

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")

            cs = ControllerService()
            context = cs.get_ui_context(doc)
            layout = context.get("layout") or {}
            stored_config = layout.get("config", {}) if isinstance(layout.get("config"), dict) else {}
            strategy = layout.get("strategy") or "grid"

            settings = InteractionService(cs).get_settings(doc)
            config = {
                "grid_mm": stored_config.get("grid_mm", settings.get("grid_mm", 5.0)),
                "spacing_mm": stored_config.get(
                    "spacing_mm",
                    stored_config.get("spacing_x_mm", stored_config.get("spacing_y_mm", 24.0)),
                ),
                "spacing_x_mm": stored_config.get("spacing_x_mm", stored_config.get("spacing_mm", 24.0)),
                "spacing_y_mm": stored_config.get("spacing_y_mm", stored_config.get("spacing_mm", 24.0)),
                "padding_mm": stored_config.get("padding_mm", 8.0),
            }
            result = cs.auto_layout(doc, strategy=strategy, config=config)
            _refresh_active_workbench_if_open(doc)
            show_info(
                "Auto Place",
                f"Placed {len(result['placed_components'])} components, {len(result['unplaced_component_ids'])} unplaced.",
            )
        except Exception as exc:
            show_error("Auto Place", exc)
