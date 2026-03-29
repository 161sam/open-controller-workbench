from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.view_event_helpers import (
    extract_position,
    get_active_view,
    get_view_point,
    is_escape_event,
    is_left_click_down,
    is_mouse_move,
)
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.gui.panels._common import log_exception, log_to_console
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


def map_view_point_to_controller_xy(
    point: tuple[float, float, float] | list[float],
    *,
    controller_width: float,
    controller_depth: float,
    snap_enabled: bool,
    grid_mm: float,
) -> tuple[float, float]:
    raw_x = float(point[0]) if len(point) >= 1 else 0.0
    raw_y = float(point[1]) if len(point) >= 2 else 0.0
    clamped_x = max(0.0, min(float(controller_width), raw_x))
    clamped_y = max(0.0, min(float(controller_depth), raw_y))
    if snap_enabled and grid_mm > 0:
        clamped_x = round(clamped_x / grid_mm) * grid_mm
        clamped_y = round(clamped_y / grid_mm) * grid_mm
        clamped_x = max(0.0, min(float(controller_width), clamped_x))
        clamped_y = max(0.0, min(float(controller_depth), clamped_y))
    return (clamped_x, clamped_y)




class ViewPlaceController:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        interaction_service: InteractionService | None = None,
        overlay_renderer: OverlayRenderer | None = None,
        on_status: Any | None = None,
        on_finished: Any | None = None,
        on_committed: Any | None = None,
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_committed = on_committed
        self.doc: Any | None = None
        self.view: Any | None = None
        self.active_template_id: str | None = None
        self.preview_active = False
        self._view_callbacks = view_callbacks or ViewEventCallbackRegistry()
        self._last_preview_status: str | None = None

    def start(self, doc: Any, template_id: str) -> bool:
        self.controller_service.library_service.get(template_id)
        view = self._active_view(doc)
        if view is None:
            self._publish_status("Could not start placement mode because no active 3D view is available.")
            return False
        self.cancel(reason="switch", publish_status=False)
        self.doc = doc
        self.view = view
        self.active_template_id = template_id
        self.preview_active = True
        self._last_preview_status = None
        self.interaction_service.begin_interaction(doc, "place", template_id=template_id)
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.cancel(reason="error", publish_status=False)
            self._publish_status("Interaction error")
            return False
        self._publish_status(f"Move the pointer in 3D, then click to place '{template_id}'. ESC cancels.")
        return self._view_callbacks.is_registered

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        doc = self.doc
        self._view_callbacks.detach()
        if doc is not None:
            try:
                self.interaction_service.end_interaction(doc)
            except Exception as exc:
                log_exception("Failed to clear placement interaction state", exc)
            try:
                self.interaction_service.clear_component_preview(doc)
            except Exception as exc:
                log_exception("Failed to clear placement preview state", exc)
            try:
                self.overlay_renderer.refresh(doc)
            except Exception as exc:
                log_exception("Failed to refresh overlay during placement cleanup", exc)
        self.doc = None
        self.view = None
        self.active_template_id = None
        self.preview_active = False
        self._last_preview_status = None
        self._notify_finished()
        if publish_status:
            self._publish_status(self._status_for_reason(reason))

    def commit(self) -> dict[str, Any]:
        if self.doc is None or self.active_template_id is None:
            raise ValueError("No active placement preview to commit")
        preview = load_preview_state(self.doc)
        if preview is None:
            raise ValueError("No preview position available")
        if not self._preview_allows_commit(preview):
            raise ValueError("Preview position is invalid")
        doc = self.doc
        try:
            template_id = self.active_template_id
            state = self.controller_service.add_component(
                doc,
                library_ref=self.active_template_id,
                x=float(preview["x"]),
                y=float(preview["y"]),
                rotation=float(preview.get("rotation", 0.0) or 0.0),
            )
        except Exception as exc:
            self._handle_interaction_error(exc)
            raise
        self._continue_after_commit(doc)
        self._notify_committed(state)
        self._publish_status(f"Placed '{template_id}'. Click to place another or ESC to cancel.")
        return state

    def update_preview_from_screen(self, screen_x: float, screen_y: float) -> dict[str, Any] | None:
        if self.doc is None or self.active_template_id is None:
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
        payload = self.interaction_service.add_component_preview(
            self.doc,
            self.active_template_id,
            target_x=x,
            target_y=y,
            rotation=0.0,
            grid_mm=float(settings.get("grid_mm", 1.0)),
            snap_enabled=bool(settings.get("snap_enabled", True)),
        )
        self.overlay_renderer.refresh(self.doc)
        self._publish_preview_status(payload)
        return payload

    def handle_view_event(self, info: Any) -> None:
        if self.doc is None or self.active_template_id is None:
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
            if position is not None and is_mouse_move(event_type, payload):
                self.update_preview_from_screen(float(position[0]), float(position[1]))
                return
            if position is not None and is_left_click_down(event_type, payload):
                preview = self.update_preview_from_screen(float(position[0]), float(position[1]))
                if preview is not None and self._preview_allows_commit(preview):
                    self.commit()
        except Exception as exc:
            self._handle_interaction_error(exc)

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
        log_exception("Placement interaction failed", exc)
        self.cancel(reason="error")

    def _continue_after_commit(self, doc: Any) -> None:
        try:
            self.interaction_service.clear_component_preview(doc)
        except Exception as exc:
            log_exception("Failed to clear placement preview after commit", exc)
        try:
            self.overlay_renderer.refresh(doc)
        except Exception as exc:
            log_exception("Failed to refresh overlay after placement commit", exc)
        self.preview_active = True
        self._last_preview_status = None

    def _notify_committed(self, state: dict[str, Any]) -> None:
        if self.on_committed is not None:
            try:
                self.on_committed(state)
            except Exception:
                pass

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
            return "Placement finished."
        if reason == "switch":
            return "Placement mode switched."
        if reason == "view_unavailable":
            return "Placement mode stopped because the 3D view is no longer available."
        return "Placement cancelled."
