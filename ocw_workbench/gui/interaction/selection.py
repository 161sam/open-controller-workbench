from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.hit_test import hit_test_components
from ocw_workbench.services.controller_service import ControllerService


class SelectionController:
    def __init__(self, controller_service: ControllerService | None = None) -> None:
        self.controller_service = controller_service or ControllerService()

    def get_selected_component_ids(self, doc: Any) -> list[str]:
        return self.controller_service.get_selected_component_ids(doc)

    def select_component(
        self,
        doc: Any,
        component_id: str | None,
        *,
        additive: bool = False,
        toggle: bool = False,
    ) -> dict[str, Any]:
        if component_id is None:
            return self.controller_service.clear_selection(doc)
        if toggle:
            return self.controller_service.toggle_selection(doc, component_id, make_primary=True)
        if additive:
            return self.controller_service.toggle_selection(doc, component_id, make_primary=False)
        return self.controller_service.select_component(doc, component_id)

    def select_from_overlay(
        self,
        doc: Any,
        overlay_items: list[dict[str, Any]],
        x: float,
        y: float,
        *,
        additive: bool = False,
        toggle: bool = False,
    ) -> str | None:
        component_id = hit_test_components(overlay_items, x, y)
        self.select_component(doc, component_id, additive=additive, toggle=toggle)
        return component_id
