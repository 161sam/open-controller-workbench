from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.dragdrop import begin_drag, update_drag
from ocw_workbench.gui.interaction.snap import SnapConfig
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


class MoveTool:
    def __init__(
        self,
        interaction_service: InteractionService | None = None,
        controller_service: ControllerService | None = None,
    ) -> None:
        self.interaction_service = interaction_service or InteractionService()
        self.controller_service = controller_service or ControllerService()

    def arm(self, doc: Any, component_id: str | None = None) -> dict[str, Any]:
        return self.interaction_service.arm_move(doc, component_id=component_id)

    def move_to(self, doc: Any, target_x: float, target_y: float) -> dict[str, Any]:
        settings = self.interaction_service.get_settings(doc)
        component_id = settings.get("move_component_id") or self.controller_service.get_ui_context(doc).get("selection")
        if component_id is None:
            raise ValueError("No component armed for move")
        component = self.controller_service.get_component(doc, component_id)
        session = begin_drag(component_id, float(component["x"]), float(component["y"]))
        snap_config = SnapConfig(grid_mm=float(settings["grid_mm"]), enabled=bool(settings["snap_enabled"]))
        session = update_drag(session, target_x, target_y, snap_config)
        return self.interaction_service.move_component(
            doc,
            component_id=session.component_id,
            target_x=session.target_x,
            target_y=session.target_y,
            grid_mm=snap_config.grid_mm,
            snap_enabled=snap_config.enabled,
        )

    def cancel(self, doc: Any) -> dict[str, Any]:
        return self.interaction_service.cancel_move(doc)
