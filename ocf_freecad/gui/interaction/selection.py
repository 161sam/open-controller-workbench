from __future__ import annotations

from typing import Any

from ocf_freecad.gui.interaction.hit_test import hit_test_components
from ocf_freecad.services.controller_service import ControllerService


class SelectionController:
    def __init__(self, controller_service: ControllerService | None = None) -> None:
        self.controller_service = controller_service or ControllerService()

    def select_component(self, doc: Any, component_id: str | None) -> dict[str, Any]:
        return self.controller_service.select_component(doc, component_id)

    def select_from_overlay(self, doc: Any, overlay_items: list[dict[str, Any]], x: float, y: float) -> str | None:
        component_id = hit_test_components(overlay_items, x, y)
        self.controller_service.select_component(doc, component_id)
        return component_id
