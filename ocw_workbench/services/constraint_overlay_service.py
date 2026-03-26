from __future__ import annotations

from typing import Any

from ocw_workbench.gui.overlay.constraint_overlay import build_constraint_overlay


class ConstraintOverlayService:
    def build(
        self,
        surface: dict[str, Any],
        resolved_components: list[dict[str, Any]],
        keepouts: list[dict[str, Any]],
        mounting_holes: list[dict[str, Any]],
        validation: dict[str, Any],
        settings: dict[str, Any],
        selected_component_id: str | None,
        move_component_id: str | None,
    ) -> dict[str, Any]:
        return build_constraint_overlay(
            surface=surface,
            resolved_components=resolved_components,
            keepouts=keepouts,
            mounting_holes=mounting_holes,
            validation=validation,
            settings=settings,
            selected_component_id=selected_component_id,
            move_component_id=move_component_id,
        )
