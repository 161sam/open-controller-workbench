from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from ocw_workbench.gui.interaction.hit_test import hit_test_inline_action, hit_test_inline_handle
from ocw_workbench.gui.interaction.inline_edit_state import (
    clear_inline_edit_state,
    load_inline_edit_state,
    store_inline_edit_state,
)
from ocw_workbench.gui.interaction.priority import handles_visible, inline_cursor_role
from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.snapping_engine import SnapContext, compute_snap
from ocw_workbench.gui.interaction.view_event_helpers import (
    extract_position,
    get_active_view,
    get_view_point,
    is_escape_event,
    is_left_click_down,
    is_left_click_up,
    is_mouse_move,
    is_shift_pressed,
)
from ocw_workbench.gui.interaction.view_place_controller import map_view_point_to_controller_xy
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.freecad_api.gui import clear_interaction_cursor, set_interaction_cursor
from ocw_workbench.gui.panels._common import log_exception, log_to_console
from ocw_workbench.gui.interaction.tool_manager import get_tool_manager
from ocw_workbench.services.controller_service import ControllerService


@dataclass
class InlineEditSession:
    component_id: str
    handle_id: str
    handle_type: str
    original_component: dict[str, Any]
    parameter_key: str | None = None
    axis_lock: dict[str, Any] | None = None


class InlineEditController:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        overlay_renderer: OverlayRenderer | None = None,
        on_status: Any | None = None,
        on_finished: Any | None = None,
        on_changed: Any | None = None,
        on_action: Any | None = None,
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_changed = on_changed
        self.on_action = on_action
        self.doc: Any | None = None
        self.view: Any | None = None
        self.session: InlineEditSession | None = None
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
        self._sync_state()
        set_interaction_cursor(view, self._cursor_role())
        self.overlay_renderer.refresh(doc)
        return True

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        if self.session is not None:
            self._revert_session()
            self._clear_tool_session()
            self.session = None
        view = self.view
        doc = self.doc
        self._view_callbacks.detach()
        self.doc = None
        self.view = None
        if doc is not None:
            clear_inline_edit_state(doc)
            self.overlay_renderer.refresh(doc)
        clear_interaction_cursor(view)
        if publish_status and reason == "cancel":
            self._publish_status("Inline edit cancelled.")
        self._notify_finished()

    def cancel_active_session(self, reason: str = "cancel", publish_status: bool = True) -> None:
        if self.session is None or self.doc is None:
            return
        self._revert_session()
        self._clear_tool_session()
        self.session = None
        self._sync_state()
        self.overlay_renderer.refresh(self.doc)
        if self.view is not None:
            set_interaction_cursor(self.view, self._cursor_role())
        if publish_status:
            self._publish_status("Inline edit cancelled." if reason == "cancel" else "Inline edit stopped.")

    def commit_active_session(self, publish_status: bool = True) -> None:
        if self.session is None or self.doc is None:
            return
        component_id = self.session.component_id
        handle_type = self.session.handle_type
        self._clear_tool_session()
        self.session = None
        self._sync_state()
        self.overlay_renderer.refresh(self.doc)
        if self.view is not None:
            set_interaction_cursor(self.view, self._cursor_role())
        if publish_status:
            self._publish_status(f"Inline edit committed for '{component_id}' ({handle_type}).")

    def handle_view_event(self, info: Any) -> None:
        if self.doc is None:
            return
        try:
            if not self._ensure_view_binding():
                return
            payload = info if isinstance(info, dict) else {}
            event_type = str(payload.get("Type") or payload.get("type") or "")
            if is_escape_event(event_type, payload):
                self.cancel_active_session()
                return
            position = extract_position(payload)
            if position is None:
                return
            screen_x = float(position[0])
            screen_y = float(position[1])
            shift_pressed = is_shift_pressed(payload)
            if is_mouse_move(event_type, payload):
                if self.session is not None:
                    self._update_active_session(screen_x, screen_y, shift_pressed=shift_pressed)
                else:
                    self._update_hover(screen_x, screen_y)
                return
            if is_left_click_down(event_type, payload):
                if self.session is None:
                    if self._invoke_action(screen_x, screen_y):
                        return
                    self._begin_session(screen_x, screen_y)
                return
            if is_left_click_up(event_type, payload) and self.session is not None:
                self.commit_active_session()
        except Exception as exc:
            log_exception("Inline edit interaction failed", exc)
            self.cancel_active_session(reason="error", publish_status=False)

    def refresh_selection(self) -> None:
        if self.doc is None:
            return
        selected_id = self._selected_component_id()
        if self.session is not None and self.session.component_id != selected_id:
            self.cancel_active_session(reason="switch", publish_status=False)
        self._sync_state()
        self.overlay_renderer.refresh(self.doc)

    def _begin_session(self, screen_x: float, screen_y: float) -> bool:
        if self.doc is None:
            return False
        if not self._handles_visible():
            return False
        handle = self._handle_at(screen_x, screen_y)
        if handle is None:
            return False
        component_id = str(handle.get("source_component_id") or "")
        if not component_id:
            return False
        component = self.controller_service.get_component(self.doc, component_id)
        handle_id = str(handle["id"])
        handle_type = self._handle_type_from_id(handle_id)
        parameter_key = None
        if handle_type not in {"move", "rotate"}:
            parameter_key = handle_type
            handle_type = "parameter"
        self.session = InlineEditSession(
            component_id=component_id,
            handle_id=handle_id,
            handle_type=handle_type,
            original_component=component,
            parameter_key=parameter_key,
        )
        store_inline_edit_state(
            self.doc,
            component_id=component_id,
            hovered_handle_id=handle_id,
            active_handle_id=handle_id,
            active_handle_type=handle_type if parameter_key is None else parameter_key,
        )
        self.overlay_renderer.refresh(self.doc)
        if self.view is not None:
            set_interaction_cursor(self.view, self._cursor_role())
        tool_id = f"inline_edit:{handle_id}"
        get_tool_manager().activate_tool(
            tool_id,
            activator=lambda: True,
            deactivate=lambda: self.cancel_active_session(reason="switch", publish_status=False),
            context={"doc": self.doc, "component_id": component_id, "handle_id": handle_id},
        )
        self._publish_status(f"Inline edit started for '{component_id}' via {handle_type} handle.")
        return True

    def _update_hover(self, screen_x: float, screen_y: float) -> None:
        if self.doc is None:
            return
        if not self._handles_visible():
            state = load_inline_edit_state(self.doc) or {}
            if state.get("hovered_handle_id") is not None:
                store_inline_edit_state(
                    self.doc,
                    component_id=self._selected_component_id(),
                    hovered_handle_id=None,
                    active_handle_id=state.get("active_handle_id"),
                    active_handle_type=state.get("active_handle_type"),
                )
                self.overlay_renderer.refresh(self.doc)
            if self.view is not None:
                set_interaction_cursor(self.view, self._cursor_role())
            return
        hovered_item_id = None
        action = self._action_at(screen_x, screen_y)
        if action is not None:
            hovered_item_id = str(action["id"])
        else:
            handle = self._handle_at(screen_x, screen_y)
            hovered_item_id = None if handle is None else str(handle["id"])
        selected_id = self._selected_component_id()
        state = load_inline_edit_state(self.doc) or {}
        if state.get("hovered_handle_id") == hovered_item_id and state.get("component_id") == selected_id:
            return
        store_inline_edit_state(
            self.doc,
            component_id=selected_id,
            hovered_handle_id=hovered_item_id,
            active_handle_id=state.get("active_handle_id"),
            active_handle_type=state.get("active_handle_type"),
        )
        self.overlay_renderer.refresh(self.doc)
        if self.view is not None:
            set_interaction_cursor(self.view, self._cursor_role())

    def _update_active_session(self, screen_x: float, screen_y: float, *, shift_pressed: bool) -> None:
        if self.doc is None or self.session is None:
            return
        point = get_view_point(self.view, screen_x, screen_y) if self.view is not None else None
        if point is None:
            return
        if self.session.handle_type == "move":
            self._apply_move(point, shift_pressed=shift_pressed)
        elif self.session.handle_type == "rotate":
            self._apply_rotation(point)
        elif self.session.parameter_key is not None:
            self._apply_parameter(point)
        self._sync_state(active_handle_id=self.session.handle_id)
        self.overlay_renderer.refresh(self.doc)
        self._notify_changed()

    def _apply_move(self, point: tuple[float, float, float], *, shift_pressed: bool) -> None:
        if self.doc is None or self.session is None:
            return
        state = self.controller_service.get_state(self.doc)
        settings = self.controller_service.get_ui_context(self.doc).get("ui", {})
        x, y = map_view_point_to_controller_xy(
            point,
            controller_width=float(state["controller"]["width"]),
            controller_depth=float(state["controller"]["depth"]),
            snap_enabled=False,
            grid_mm=float(settings.get("grid_mm", 1.0)),
        )
        x, y = self._apply_axis_lock((x, y), shift_pressed=shift_pressed)
        snapped_x, snapped_y = self._snap_position((x, y), ignore_component_id=self.session.component_id)
        self.controller_service.update_component(
            self.doc,
            self.session.component_id,
            {"x": snapped_x, "y": snapped_y},
        )

    def _apply_rotation(self, point: tuple[float, float, float]) -> None:
        if self.doc is None or self.session is None:
            return
        current = self.controller_service.get_component(self.doc, self.session.component_id)
        dx = float(point[0]) - float(current["x"])
        dy = float(point[1]) - float(current["y"])
        if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
            return
        rotation = round(math.degrees(math.atan2(dy, dx)) - 90.0, 1)
        self.controller_service.update_component(
            self.doc,
            self.session.component_id,
            {"rotation": rotation},
        )

    def _apply_parameter(self, point: tuple[float, float, float]) -> None:
        if self.doc is None or self.session is None or self.session.parameter_key is None:
            return
        current = self.controller_service.get_component(self.doc, self.session.component_id)
        rotation = float(current.get("rotation", 0.0) or 0.0)
        local_x, _local_y = self._point_to_local(point, origin=(float(current["x"]), float(current["y"])), rotation_deg=rotation)
        if self.session.parameter_key == "cap_width":
            value = max(round(abs(local_x) * 2.0, 1), 4.0)
            self.controller_service.update_component(
                self.doc,
                self.session.component_id,
                {"properties": {"cap_width": value}},
            )

    def _revert_session(self) -> None:
        if self.doc is None or self.session is None:
            return
        original = self.session.original_component
        state = self.controller_service.get_state(self.doc)
        for index, component in enumerate(state["components"]):
            if component["id"] != self.session.component_id:
                continue
            state["components"][index] = dict(original)
            self.controller_service.save_state(self.doc, state)
            self.controller_service.update_document(
                self.doc,
                mode="full",
                state=state,
                selection=state["meta"].get("selection"),
            )
            return

    def _sync_state(self, *, active_handle_id: str | None = None) -> None:
        if self.doc is None:
            return
        selected_id = self._selected_component_id()
        hovered = None
        active = active_handle_id
        active_type = None
        if self.session is not None:
            hovered = self.session.handle_id
            active = self.session.handle_id
            active_type = self.session.parameter_key or self.session.handle_type
            selected_id = self.session.component_id
        else:
            state = load_inline_edit_state(self.doc) or {}
            hovered = state.get("hovered_handle_id")
        store_inline_edit_state(
            self.doc,
            component_id=selected_id,
            hovered_handle_id=hovered,
            active_handle_id=active,
            active_handle_type=active_type,
        )

    def _selected_component_id(self) -> str | None:
        if self.doc is None:
            return None
        context = self.controller_service.get_ui_context(self.doc)
        selected_ids = context.get("selected_ids", [])
        if len(selected_ids) != 1:
            return None
        selected = context.get("selection")
        return str(selected) if isinstance(selected, str) and selected else None

    def _handle_at(self, screen_x: float, screen_y: float) -> dict[str, Any] | None:
        if self.doc is None:
            return None
        point = get_view_point(self.view, screen_x, screen_y) if self.view is not None else None
        if point is None:
            return None
        overlay = getattr(self.doc, "OCWOverlayState", None)
        if not isinstance(overlay, dict):
            overlay = self.overlay_renderer.refresh(self.doc)
        return hit_test_inline_handle(list(overlay.get("items", [])), x=float(point[0]), y=float(point[1]))

    def _action_at(self, screen_x: float, screen_y: float) -> dict[str, Any] | None:
        if self.doc is None:
            return None
        point = get_view_point(self.view, screen_x, screen_y) if self.view is not None else None
        if point is None:
            return None
        overlay = getattr(self.doc, "OCWOverlayState", None)
        if not isinstance(overlay, dict):
            overlay = self.overlay_renderer.refresh(self.doc)
        return hit_test_inline_action(list(overlay.get("items", [])), x=float(point[0]), y=float(point[1]))

    def _invoke_action(self, screen_x: float, screen_y: float) -> bool:
        if self.doc is None:
            return False
        action = self._action_at(screen_x, screen_y)
        if action is None:
            return False
        if self.on_action is None:
            return False
        action_id = str(action.get("action_id") or "")
        component_id = str(action.get("source_component_id") or "")
        command_id = str(action.get("command_id") or "")
        if not action_id or not component_id:
            return False
        self.on_action(action_id, component_id, command_id)
        self._sync_state()
        self.overlay_renderer.refresh(self.doc)
        if self.view is not None:
            set_interaction_cursor(self.view, self._cursor_role())
        return True

    def _snap_position(self, position: tuple[float, float], *, ignore_component_id: str | None) -> tuple[float, float]:
        if self.doc is None:
            return position
        settings = self.controller_service.get_ui_context(self.doc).get("ui", {})
        if not bool(settings.get("snap_enabled", True)):
            return position
        overlay = getattr(self.doc, "OCWOverlayState", None)
        if not isinstance(overlay, dict):
            overlay = self.overlay_renderer.refresh(self.doc)
        items = []
        for item in overlay.get("items", []) if isinstance(overlay.get("items"), list) else []:
            if item.get("source_component_id") == ignore_component_id:
                continue
            item_id = str(item.get("id") or "")
            if item_id.startswith("inline_handle:") or item_id.startswith("inline_action:"):
                continue
            items.append(item)
        result = compute_snap(position, SnapContext(overlay_items=tuple(items)))
        return result.snapped_position

    def _apply_axis_lock(self, position: tuple[float, float], *, shift_pressed: bool) -> tuple[float, float]:
        if self.session is None:
            return position
        anchor = (
            float(self.session.original_component.get("x", 0.0) or 0.0),
            float(self.session.original_component.get("y", 0.0) or 0.0),
        )
        if not shift_pressed:
            self.session.axis_lock = None
            return position
        if self.session.axis_lock is None:
            self.session.axis_lock = {"anchor": anchor, "axis": None}
            return position
        axis = self.session.axis_lock.get("axis")
        delta_x = abs(float(position[0]) - float(anchor[0]))
        delta_y = abs(float(position[1]) - float(anchor[1]))
        if axis is None and max(delta_x, delta_y) > 0.0:
            axis = "x" if delta_x >= delta_y else "y"
            self.session.axis_lock["axis"] = axis
        if axis == "x":
            return (float(position[0]), float(anchor[1]))
        if axis == "y":
            return (float(anchor[0]), float(position[1]))
        return position

    def _point_to_local(
        self,
        point: tuple[float, float, float],
        *,
        origin: tuple[float, float],
        rotation_deg: float,
    ) -> tuple[float, float]:
        angle = math.radians(-float(rotation_deg))
        dx = float(point[0]) - float(origin[0])
        dy = float(point[1]) - float(origin[1])
        local_x = (dx * math.cos(angle)) - (dy * math.sin(angle))
        local_y = (dx * math.sin(angle)) + (dy * math.cos(angle))
        return local_x, local_y

    def _handle_type_from_id(self, handle_id: str) -> str:
        parts = handle_id.split(":")
        if len(parts) < 3:
            return "move"
        return parts[1]

    def _clear_tool_session(self) -> None:
        if self.session is None:
            return
        get_tool_manager().clear_active_tool(f"inline_edit:{self.session.handle_id}")

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
        set_interaction_cursor(view, self._cursor_role())
        return True

    def _selection_count(self) -> int:
        if self.doc is None:
            return 0
        context = self.controller_service.get_ui_context(self.doc)
        return len(context.get("selected_ids", []))

    def _handles_visible(self) -> bool:
        if self.doc is None:
            return False
        context = self.controller_service.get_ui_context(self.doc)
        return handles_visible(
            selection_count=self._selection_count(),
            ui_settings=context.get("ui", {}),
        )

    def _cursor_role(self) -> str:
        if self.doc is None:
            return "default"
        context = self.controller_service.get_ui_context(self.doc)
        return inline_cursor_role(
            selection_count=self._selection_count(),
            ui_settings=context.get("ui", {}),
            inline_state=load_inline_edit_state(self.doc),
        )

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

    def _notify_changed(self) -> None:
        if self.on_changed is not None:
            try:
                self.on_changed()
            except Exception:
                pass
