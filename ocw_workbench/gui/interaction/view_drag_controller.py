from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ocw_workbench.gui.interaction.hit_test import hit_test_components
from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.view_event_helpers import (
    extract_position,
    get_active_view,
    get_view_point,
    is_escape_event,
    is_left_click_down,
    is_left_click_up,
    is_mouse_move,
)
from ocw_workbench.gui.interaction.view_place_controller import map_view_point_to_controller_xy
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.panels._common import log_exception, log_to_console
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


@dataclass
class DragMoveSession:
    component_id: str
    original_x: float
    original_y: float
    original_rotation: float
    previous_selection: str | None
    dragging: bool = False


class ViewDragController:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        interaction_service: InteractionService | None = None,
        overlay_renderer: OverlayRenderer | None = None,
        on_status: Any | None = None,
        on_finished: Any | None = None,
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
        self.doc: Any | None = None
        self.view: Any | None = None
        self.armed = False
        self.session: DragMoveSession | None = None
        self._view_callbacks = view_callbacks or ViewEventCallbackRegistry()
        self._last_preview_status: str | None = None
        self._last_hover_component_id: str | None = None

    def start(self, doc: Any) -> bool:
        view = self._active_view(doc)
        if view is None:
            self._publish_status("Could not start drag mode because no active 3D view is available.")
            return False
        self.cancel(reason="switch", publish_status=False)
        self.doc = doc
        self.view = view
        self.armed = True
        self._last_preview_status = None
        self._last_hover_component_id = None
        self.interaction_service.begin_interaction(doc, "drag")
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.cancel(reason="error", publish_status=False)
            self._publish_status("Interaction error")
            return False
        self._publish_status("Drag in 3D. Hover to highlight, press and hold to move, release to commit, ESC to cancel.")
        return self._view_callbacks.is_registered

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        doc = self.doc
        session = self.session
        self._view_callbacks.detach()
        if doc is not None:
            try:
                self.interaction_service.set_hovered_component(doc, None)
            except Exception as exc:
                log_exception("Failed to clear drag hover state", exc)
            try:
                self.interaction_service.end_interaction(doc)
            except Exception as exc:
                log_exception("Failed to clear drag interaction state", exc)
            try:
                self.interaction_service.clear_component_preview(doc)
            except Exception as exc:
                log_exception("Failed to clear drag preview state", exc)
            if session is not None and reason != "finish":
                try:
                    self.controller_service.select_component(doc, session.previous_selection)
                except Exception as exc:
                    log_exception("Failed to restore selection during drag cleanup", exc)
            try:
                self.overlay_renderer.refresh(doc)
            except Exception as exc:
                log_exception("Failed to refresh overlay during drag cleanup", exc)
        self.doc = None
        self.view = None
        self.armed = False
        self.session = None
        self._last_preview_status = None
        self._last_hover_component_id = None
        self._notify_finished()
        if publish_status:
            self._publish_status(self._status_for_reason(reason))

    def handle_view_event(self, info: Any) -> None:
        if self.doc is None:
            return
        try:
            if not self._ensure_view_binding():
                return
            payload = info if isinstance(info, dict) else {}
            event_type = str(payload.get("Type") or payload.get("type") or "")
            if is_escape_event(event_type, payload):
                self.cancel()
                return
            position = extract_position(payload)
            if position is None:
                return
            screen_x = float(position[0])
            screen_y = float(position[1])
            if is_left_click_down(event_type, payload):
                if self.session is None or not self.session.dragging:
                    self._begin_drag(screen_x, screen_y)
                return
            if is_mouse_move(event_type, payload):
                if self.session is not None and self.session.dragging:
                    self.update_preview_from_screen(screen_x, screen_y)
                else:
                    self.update_hover_from_screen(screen_x, screen_y)
                return
            if self.session is not None and self.session.dragging and is_left_click_up(event_type, payload):
                preview = self.update_preview_from_screen(screen_x, screen_y)
                if preview is not None and self._preview_allows_commit(preview):
                    self.commit()
        except Exception as exc:
            self._handle_interaction_error(exc)

    def _begin_drag(self, screen_x: float, screen_y: float) -> bool:
        if self.doc is None or self.view is None:
            return False
        point = get_view_point(self.view, screen_x, screen_y)
        if point is None:
            return False
        overlay = self.overlay_renderer.refresh(self.doc)
        component_id = hit_test_components(list(overlay.get("items", [])), x=float(point[0]), y=float(point[1]))
        if component_id is None:
            self._publish_status("No component at that position. Hover over a component to highlight it, then click to drag.")
            return False
        self._set_hover_component(component_id, announce=False)
        component = self.controller_service.get_component(self.doc, component_id)
        previous_selection = self.controller_service.get_ui_context(self.doc).get("selection")
        self.controller_service.select_component(self.doc, component_id)
        self.session = DragMoveSession(
            component_id=component_id,
            original_x=float(component["x"]),
            original_y=float(component["y"]),
            original_rotation=float(component.get("rotation", 0.0) or 0.0),
            previous_selection=previous_selection,
            dragging=True,
        )
        self.interaction_service.move_component_preview(
            self.doc,
            component_id=component_id,
            target_x=float(component["x"]),
            target_y=float(component["y"]),
            rotation=float(component.get("rotation", 0.0) or 0.0),
            grid_mm=float(self.interaction_service.get_settings(self.doc).get("grid_mm", 1.0)),
            snap_enabled=bool(self.interaction_service.get_settings(self.doc).get("snap_enabled", True)),
        )
        self.overlay_renderer.refresh(self.doc)
        self._publish_status(f"Dragging '{component_id}'. Move the pointer, release to commit, ESC to cancel.")
        return True

    def update_hover_from_screen(self, screen_x: float, screen_y: float) -> str | None:
        if self.doc is None or self.view is None:
            return None
        point = get_view_point(self.view, screen_x, screen_y)
        if point is None:
            return None
        overlay = getattr(self.doc, "OCWOverlayState", None)
        if not isinstance(overlay, dict):
            overlay = self.overlay_renderer.refresh(self.doc)
        component_id = hit_test_components(list(overlay.get("items", [])), x=float(point[0]), y=float(point[1]))
        self._set_hover_component(component_id, announce=True)
        return component_id

    def update_preview_from_screen(self, screen_x: float, screen_y: float) -> dict[str, Any] | None:
        if self.doc is None or self.session is None:
            return None
        if not self._ensure_view_binding():
            return None
        point = get_view_point(self.view, screen_x, screen_y)
        if point is None:
            return None
        state = self.controller_service.get_state(self.doc)
        settings = self.interaction_service.get_settings(self.doc)
        x, y = map_view_point_to_controller_xy(
            point,
            controller_width=float(state["controller"]["width"]),
            controller_depth=float(state["controller"]["depth"]),
            snap_enabled=bool(settings.get("snap_enabled", True)),
            grid_mm=float(settings.get("grid_mm", 1.0)),
        )
        payload = self.interaction_service.move_component_preview(
            self.doc,
            component_id=self.session.component_id,
            target_x=x,
            target_y=y,
            rotation=self.session.original_rotation,
            grid_mm=float(settings.get("grid_mm", 1.0)),
            snap_enabled=bool(settings.get("snap_enabled", True)),
        )
        self.overlay_renderer.refresh(self.doc)
        self._publish_preview_status(payload)
        return payload

    def commit(self) -> dict[str, Any]:
        if self.doc is None or self.session is None:
            raise ValueError("No active drag session to commit")
        preview = load_preview_state(self.doc)
        if preview is None:
            raise ValueError("No drag preview position available")
        if not self._preview_allows_commit(preview):
            raise ValueError("Preview position is invalid")
        component_id = self.session.component_id
        try:
            state = self.controller_service.move_component(
                self.doc,
                component_id=component_id,
                x=float(preview["x"]),
                y=float(preview["y"]),
                rotation=self.session.original_rotation,
            )
        except Exception as exc:
            self._handle_interaction_error(exc)
            raise
        component_id = self.session.component_id
        self.cancel(reason="finish", publish_status=False)
        self._publish_status(f"Moved '{component_id}'.")
        return state

    def _active_view(self, doc: Any) -> Any | None:
        return get_active_view(doc)

    def _publish_status(self, message: str) -> None:
        log_to_console(message)
        if self.on_status is not None:
            self.on_status(message)

    def _ensure_view_binding(self) -> bool:
        if self.doc is None:
            return False
        view = self._active_view(self.doc)
        if view is None and self.view is not None:
            view = self.view
        if view is None:
            self.cancel(reason="view_unavailable")
            return False
        self.view = view
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.cancel(reason="error")
            return False
        return True

    def _handle_interaction_error(self, exc: Exception) -> None:
        log_exception("Drag interaction failed", exc)
        self.cancel(reason="error")

    def _notify_finished(self) -> None:
        if self.on_finished is not None:
            try:
                self.on_finished(self)
            except Exception:
                pass

    def _publish_preview_status(self, preview: dict[str, Any]) -> None:
        validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        status = validation.get("status") if isinstance(validation.get("status"), str) else "Valid placement"
        if status == self._last_preview_status:
            return
        self._last_preview_status = status
        self._publish_status(status)

    def _preview_allows_commit(self, preview: dict[str, Any]) -> bool:
        validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        allowed = bool(validation.get("commit_allowed", True))
        if not allowed:
            self._publish_preview_status(preview)
        return allowed

    def _status_for_reason(self, reason: str) -> str:
        if reason == "error":
            return "Interaction error"
        if reason == "finish":
            return "Move finished."
        if reason == "switch":
            return "Drag mode switched."
        if reason == "view_unavailable":
            return "Drag mode stopped because the 3D view is no longer available."
        return "Drag cancelled."

    def _set_hover_component(self, component_id: str | None, *, announce: bool) -> None:
        if self.doc is None:
            return
        if component_id == self._last_hover_component_id:
            return
        self._last_hover_component_id = component_id
        self.interaction_service.set_hovered_component(self.doc, component_id)
        if not announce:
            return
        if component_id is None:
            self._publish_status("Drag in 3D. Hover to highlight, press and hold to move, release to commit, ESC to cancel.")
            return
        component = self.controller_service.get_component(self.doc, component_id)
        label = component.get("label") or component_id
        self._publish_status(f"Ready to drag '{label}'. Press and hold the left mouse button, then release to commit.")
