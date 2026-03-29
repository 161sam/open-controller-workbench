from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.gui.interaction.view_place_preview import clear_preview_state, store_preview_state
from ocw_workbench.layout.snap import snap_point
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.preview_validation_service import PreviewValidationService

DEFAULT_UI_SETTINGS = {
    "active_interaction": None,
    "hovered_component_id": None,
    "overlay_enabled": True,
    "show_constraints": True,
    "grid_mm": 1.0,
    "snap_enabled": True,
    "move_component_id": None,
    "measurements_enabled": True,
    "conflict_lines_enabled": True,
    "constraint_labels_enabled": True,
    "show_warnings": True,
    "show_errors": True,
    "active_component_template_id": None,
}


class InteractionService:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        preview_validation_service: PreviewValidationService | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.preview_validation_service = preview_validation_service or PreviewValidationService(self.controller_service)

    def get_settings(self, doc: Any) -> dict[str, Any]:
        state = self.controller_service.get_state(doc)
        settings = deepcopy(DEFAULT_UI_SETTINGS)
        settings.update(deepcopy(state["meta"].get("ui", {})))
        return settings

    def update_settings(self, doc: Any, updates: dict[str, Any]) -> dict[str, Any]:
        state = self.controller_service.get_state(doc)
        settings = self.get_settings(doc)
        settings.update(deepcopy(updates))
        state["meta"]["ui"] = settings
        self.controller_service.save_state(doc, state)
        return settings

    def toggle_overlay(self, doc: Any) -> dict[str, Any]:
        settings = self.get_settings(doc)
        return self.update_settings(doc, {"overlay_enabled": not settings["overlay_enabled"]})

    def toggle_constraint_overlay(self, doc: Any) -> dict[str, Any]:
        settings = self.get_settings(doc)
        return self.update_settings(doc, {"show_constraints": not settings["show_constraints"]})

    def toggle_measurements(self, doc: Any) -> dict[str, Any]:
        settings = self.get_settings(doc)
        return self.update_settings(doc, {"measurements_enabled": not settings["measurements_enabled"]})

    def toggle_conflict_lines(self, doc: Any) -> dict[str, Any]:
        settings = self.get_settings(doc)
        return self.update_settings(doc, {"conflict_lines_enabled": not settings["conflict_lines_enabled"]})

    def toggle_constraint_labels(self, doc: Any) -> dict[str, Any]:
        settings = self.get_settings(doc)
        return self.update_settings(doc, {"constraint_labels_enabled": not settings["constraint_labels_enabled"]})

    def set_grid(self, doc: Any, grid_mm: float) -> dict[str, Any]:
        return self.update_settings(doc, {"grid_mm": float(grid_mm)})

    def set_active_component_template(self, doc: Any, template_id: str | None) -> dict[str, Any]:
        if template_id is not None:
            self.controller_service.library_service.get(template_id)
        return self.update_settings(doc, {"active_component_template_id": template_id})

    def begin_interaction(self, doc: Any, kind: str, *, template_id: str | None = None) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "active_interaction": str(kind),
            "move_component_id": None,
            "hovered_component_id": None,
        }
        if template_id is not None:
            self.controller_service.library_service.get(template_id)
            updates["active_component_template_id"] = template_id
        return self.update_settings(doc, updates)

    def end_interaction(self, doc: Any) -> dict[str, Any]:
        return self.update_settings(
            doc,
            {
                "active_interaction": None,
                "move_component_id": None,
                "hovered_component_id": None,
            },
        )

    def set_hovered_component(self, doc: Any, component_id: str | None) -> dict[str, Any]:
        if component_id is not None:
            self.controller_service.get_component(doc, component_id)
        settings = self.get_settings(doc)
        if settings.get("hovered_component_id") == component_id:
            return settings
        updated = self.update_settings(doc, {"hovered_component_id": component_id})
        self.controller_service.refresh_document_visuals(doc, recompute=False)
        return updated

    def add_component_preview(
        self,
        doc: Any,
        template_id: str,
        target_x: float,
        target_y: float,
        rotation: float = 0.0,
        grid_mm: float | None = None,
        snap_enabled: bool | None = None,
        snap: dict[str, Any] | None = None,
        axis_lock: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.controller_service.library_service.get(template_id)
        settings = self.get_settings(doc)
        resolved_grid = float(grid_mm if grid_mm is not None else settings["grid_mm"])
        resolved_snap = settings["snap_enabled"] if snap_enabled is None else bool(snap_enabled)
        x = float(target_x)
        y = float(target_y)
        if resolved_snap:
            x, y = snap_point(x, y, resolved_grid)
        validation = self.preview_validation_service.validate_place(
            doc,
            template_id=template_id,
            x=x,
            y=y,
            rotation=float(rotation),
        )
        payload = store_preview_state(
            doc,
            template_id=template_id,
            x=x,
            y=y,
            rotation=float(rotation),
            mode="place",
            snap_enabled=resolved_snap,
            grid_mm=resolved_grid,
            validation=validation,
            snap=snap,
            axis_lock=axis_lock,
        )
        self.controller_service.refresh_document_visuals(doc, recompute=False)
        return payload

    def move_component_preview(
        self,
        doc: Any,
        component_id: str,
        target_x: float,
        target_y: float,
        rotation: float | None = None,
        grid_mm: float | None = None,
        snap_enabled: bool | None = None,
        snap: dict[str, Any] | None = None,
        axis_lock: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        component = self.controller_service.get_component(doc, component_id)
        settings = self.get_settings(doc)
        resolved_grid = float(grid_mm if grid_mm is not None else settings["grid_mm"])
        resolved_snap = settings["snap_enabled"] if snap_enabled is None else bool(snap_enabled)
        x = float(target_x)
        y = float(target_y)
        if resolved_snap:
            x, y = snap_point(x, y, resolved_grid)
        resolved_rotation = float(component.get("rotation", 0.0) if rotation is None else rotation)
        validation = self.preview_validation_service.validate_move(
            doc,
            component_id=component_id,
            x=x,
            y=y,
            rotation=resolved_rotation,
        )
        payload = store_preview_state(
            doc,
            component_id=component_id,
            x=x,
            y=y,
            rotation=resolved_rotation,
            mode="move",
            snap_enabled=resolved_snap,
            grid_mm=resolved_grid,
            validation=validation,
            snap=snap,
            axis_lock=axis_lock,
        )
        self.controller_service.refresh_document_visuals(doc, recompute=False)
        return payload

    def clear_component_preview(self, doc: Any) -> None:
        clear_preview_state(doc)
        self.controller_service.refresh_document_visuals(doc, recompute=False)


    def arm_move(self, doc: Any, component_id: str | None = None) -> dict[str, Any]:
        selection = component_id or self.controller_service.get_ui_context(doc).get("selection")
        if selection is None:
            raise ValueError("No component selected for move mode")
        self.controller_service.select_component(doc, selection)
        return self.update_settings(doc, {"move_component_id": selection})

    def cancel_move(self, doc: Any) -> dict[str, Any]:
        return self.update_settings(doc, {"move_component_id": None})

    def move_selected_component(
        self,
        doc: Any,
        target_x: float,
        target_y: float,
        grid_mm: float | None = None,
        snap_enabled: bool | None = None,
    ) -> dict[str, Any]:
        context = self.controller_service.get_ui_context(doc)
        component_id = context.get("selection")
        if component_id is None:
            raise ValueError("No component selected")
        return self.move_component(
            doc,
            component_id=component_id,
            target_x=target_x,
            target_y=target_y,
            grid_mm=grid_mm,
            snap_enabled=snap_enabled,
        )

    def move_component(
        self,
        doc: Any,
        component_id: str,
        target_x: float,
        target_y: float,
        grid_mm: float | None = None,
        snap_enabled: bool | None = None,
    ) -> dict[str, Any]:
        settings = self.get_settings(doc)
        resolved_grid = float(grid_mm if grid_mm is not None else settings["grid_mm"])
        resolved_snap = settings["snap_enabled"] if snap_enabled is None else bool(snap_enabled)
        x = float(target_x)
        y = float(target_y)
        if resolved_snap:
            x, y = snap_point(x, y, resolved_grid)
        state = self.controller_service.move_component(doc, component_id, x=x, y=y)
        report = self.controller_service.validate_layout(doc)
        settings = self.update_settings(doc, {"move_component_id": component_id, "grid_mm": resolved_grid})
        return {
            "component_id": component_id,
            "x": x,
            "y": y,
            "state": state,
            "validation": report,
            "ui": settings,
        }

    def snap_selected_component(self, doc: Any, grid_mm: float | None = None) -> dict[str, Any]:
        context = self.controller_service.get_ui_context(doc)
        component_id = context.get("selection")
        if component_id is None:
            raise ValueError("No component selected")
        component = self.controller_service.get_component(doc, component_id)
        return self.move_component(
            doc,
            component_id=component_id,
            target_x=float(component["x"]),
            target_y=float(component["y"]),
            grid_mm=grid_mm,
            snap_enabled=True,
        )
