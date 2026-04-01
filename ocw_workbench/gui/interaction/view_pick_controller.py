from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.hit_test import hit_test_components
from ocw_workbench.gui.interaction.priority import handles_visible
from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.selection import SelectionController
from ocw_workbench.gui.interaction.view_event_helpers import (
    extract_position,
    get_active_view,
    get_view_point,
    is_escape_event,
    is_left_click_down,
    is_mouse_move,
)
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.freecad_api.gui import clear_interaction_cursor, set_interaction_cursor
from ocw_workbench.gui.panels._common import log_exception, log_to_console
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


class ViewPickController:
    """Lightweight idle-state listener that selects components from 3D view clicks.

    Active whenever no placement or drag mode is running. Does not consume
    events — FreeCAD's native selection still processes the same click.
    """

    def __init__(
        self,
        controller_service: ControllerService | None = None,
        interaction_service: InteractionService | None = None,
        overlay_renderer: OverlayRenderer | None = None,
        on_status: Any | None = None,
        on_finished: Any | None = None,
        on_selected: Any | None = None,
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_selected = on_selected
        self.selection_controller = SelectionController(self.controller_service)
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
        set_interaction_cursor(view, "pick")
        return True

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        view = self.view
        doc = self.doc
        self._view_callbacks.detach()
        if doc is not None:
            try:
                self.interaction_service.set_hovered_component(doc, None)
            except Exception as exc:
                log_exception("Failed to clear pick hover state", exc)
        self.doc = None
        self.view = None
        clear_interaction_cursor(view)
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
            if position is None:
                return
            screen_x = float(position[0])
            screen_y = float(position[1])
            if is_mouse_move(event_type, payload):
                self._hover_at(screen_x, screen_y)
                return
            if is_left_click_down(event_type, payload):
                self._pick_at(screen_x, screen_y)
        except Exception as exc:
            log_exception("Pick interaction failed", exc)

    def _hover_at(self, screen_x: float, screen_y: float) -> str | None:
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
        self.interaction_service.set_hovered_component(self.doc, component_id)
        return component_id

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
            self.interaction_service.set_hovered_component(self.doc, None)
            return None
        try:
            self.interaction_service.set_hovered_component(self.doc, component_id)
            self.selection_controller.select_component(self.doc, component_id)
        except Exception as exc:
            log_exception("Pick selection failed", exc)
            return None
        component = self.controller_service.get_component(self.doc, component_id)
        label = component.get("label") or component_id
        context = self.controller_service.get_ui_context(self.doc)
        if handles_visible(selection_count=len(context.get("selected_ids", [])), ui_settings=context.get("ui", {})):
            self._publish_status(f"Selected '{label}'. Inline handles are ready in the 3D view.")
        else:
            self._publish_status(f"Selected '{label}'. Direct actions now target it.")
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
        set_interaction_cursor(view, "pick")
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
