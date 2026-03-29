from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.hit_test import hit_test_components
from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.view_event_helpers import (
    extract_position,
    get_active_view,
    get_view_point,
    is_escape_event,
    is_left_click_down,
)
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.panels._common import log_exception, log_to_console
from ocw_workbench.services.controller_service import ControllerService


class ViewPickController:
    """Lightweight idle-state listener that selects components from 3D view clicks.

    Active whenever no placement or drag mode is running. Does not consume
    events — FreeCAD's native selection still processes the same click.
    """

    def __init__(
        self,
        controller_service: ControllerService | None = None,
        overlay_renderer: OverlayRenderer | None = None,
        on_status: Any | None = None,
        on_finished: Any | None = None,
        on_selected: Any | None = None,
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_selected = on_selected
        self.doc: Any | None = None
        self.view: Any | None = None
        self._view_callbacks = view_callbacks or ViewEventCallbackRegistry()

    def start(self, doc: Any) -> bool:
        view = self._active_view(doc)
        if view is None:
            return False
        self.cancel(publish_status=False)
        self.doc = doc
        self.view = view
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.doc = None
            self.view = None
            return False
        return True

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        self._view_callbacks.detach()
        self.doc = None
        self.view = None
        self._notify_finished()

    def handle_view_event(self, info: Any) -> None:
        if self.doc is None:
            return
        try:
            if not self._ensure_view_binding():
                return
            payload = info if isinstance(info, dict) else {}
            event_type = str(payload.get("Type") or payload.get("type") or "")
            if is_escape_event(event_type, payload):
                return
            position = extract_position(payload)
            if position is None or not is_left_click_down(event_type, payload):
                return
            screen_x = float(position[0])
            screen_y = float(position[1])
            self._pick_at(screen_x, screen_y)
        except Exception as exc:
            log_exception("Pick interaction failed", exc)

    def _pick_at(self, screen_x: float, screen_y: float) -> str | None:
        view = self.view
        if view is None:
            view = self._active_view(self.doc)
        if view is None:
            return None
        point = get_view_point(view, screen_x, screen_y)
        if point is None:
            return None
        overlay = getattr(self.doc, "OCWOverlayState", None)
        if not isinstance(overlay, dict):
            overlay = self.overlay_renderer.refresh(self.doc)
        component_id = hit_test_components(
            list(overlay.get("items", [])),
            x=float(point[0]),
            y=float(point[1]),
        )
        if component_id is None:
            return None
        try:
            self.controller_service.select_component(self.doc, component_id)
        except Exception as exc:
            log_exception("Pick selection failed", exc)
            return None
        component = self.controller_service.get_component(self.doc, component_id)
        label = component.get("label") or component_id
        self._publish_status(f"Selected '{label}'.")
        self._notify_selected(component_id)
        return component_id

    def _active_view(self, doc: Any) -> Any | None:
        return get_active_view(doc)

    def _ensure_view_binding(self) -> bool:
        if self.doc is None:
            return False
        view = self._active_view(self.doc)
        if view is None and self.view is not None:
            view = self.view
        if view is None:
            self.cancel(publish_status=False)
            return False
        self.view = view
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.cancel(publish_status=False)
            return False
        return True

    def _publish_status(self, message: str) -> None:
        log_to_console(message)
        if self.on_status is not None:
            self.on_status(message)

    def _notify_finished(self) -> None:
        if self.on_finished is not None:
            try:
                self.on_finished(self)
            except Exception:
                pass

    def _notify_selected(self, component_id: str) -> None:
        if self.on_selected is not None:
            try:
                self.on_selected(component_id)
            except Exception:
                pass
