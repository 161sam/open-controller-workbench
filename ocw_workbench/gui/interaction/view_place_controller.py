from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.lifecycle import ViewEventCallbackRegistry
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
        view_callbacks: ViewEventCallbackRegistry | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.overlay_renderer = overlay_renderer or OverlayRenderer()
        self.on_status = on_status
        self.on_finished = on_finished
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
        if not self._view_callbacks.attach(view, self.handle_view_event):
            self.cancel(reason="error", publish_status=False)
            self._publish_status("Interaction error")
            return False
        self._publish_status("Placing ...")
        return self._view_callbacks.is_registered

    def cancel(self, reason: str = "cancel", publish_status: bool = True) -> None:
        doc = self.doc
        self._view_callbacks.detach()
        if doc is not None:
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
        try:
            state = self.controller_service.add_component(
                self.doc,
                library_ref=self.active_template_id,
                x=float(preview["x"]),
                y=float(preview["y"]),
                rotation=float(preview.get("rotation", 0.0) or 0.0),
            )
        except Exception as exc:
            self._handle_interaction_error(exc)
            raise
        self.cancel(reason="finish", publish_status=False)
        self._publish_status("Committed")
        return state

    def update_preview_from_screen(self, screen_x: float, screen_y: float) -> dict[str, Any] | None:
        if self.doc is None or self.active_template_id is None:
            return None
        if not self._ensure_view_binding():
            return None
        point = self._view_point(self.view, screen_x, screen_y)
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
            if self._is_escape_event(event_type, payload):
                self.cancel()
                return
            position = self._extract_position(payload)
            if position is not None and self._is_mouse_move(event_type, payload):
                self.update_preview_from_screen(float(position[0]), float(position[1]))
                return
            if position is not None and self._is_left_click_down(event_type, payload):
                preview = self.update_preview_from_screen(float(position[0]), float(position[1]))
                if preview is not None and self._preview_allows_commit(preview):
                    self.commit()
        except Exception as exc:
            self._handle_interaction_error(exc)

    def _active_view(self, doc: Any) -> Any | None:
        try:
            import FreeCADGui as Gui
        except ImportError:
            return None
        gui_doc = None
        doc_name = getattr(doc, "Name", None)
        if isinstance(doc_name, str) and hasattr(Gui, "getDocument"):
            try:
                gui_doc = Gui.getDocument(doc_name)
            except Exception:
                gui_doc = None
        active_gui_doc = getattr(Gui, "ActiveDocument", None)
        active_gui_doc_name = getattr(active_gui_doc, "Document", None)
        active_gui_doc_name = getattr(active_gui_doc_name, "Name", getattr(active_gui_doc, "Name", None))
        if gui_doc is None and not isinstance(doc_name, str):
            gui_doc = getattr(Gui, "ActiveDocument", None)
        if gui_doc is None and isinstance(doc_name, str) and active_gui_doc_name == doc_name:
            gui_doc = active_gui_doc
        if gui_doc is None or not hasattr(gui_doc, "activeView"):
            return None
        try:
            return gui_doc.activeView()
        except Exception:
            return None

    def _view_point(self, view: Any, screen_x: float, screen_y: float) -> tuple[float, float, float] | None:
        if not hasattr(view, "getPoint"):
            return None
        try:
            point = view.getPoint(int(round(screen_x)), int(round(screen_y)))
        except Exception:
            return None
        if isinstance(point, (list, tuple)) and len(point) >= 3:
            return (float(point[0]), float(point[1]), float(point[2]))
        if hasattr(point, "__iter__"):
            values = list(point)
            if len(values) >= 3:
                return (float(values[0]), float(values[1]), float(values[2]))
        return None

    def _extract_position(self, payload: dict[str, Any]) -> tuple[float, float] | None:
        for key in ("Position", "position", "pos"):
            value = payload.get(key)
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                return (float(value[0]), float(value[1]))
        return None

    def _is_mouse_move(self, event_type: str, payload: dict[str, Any]) -> bool:
        state = str(payload.get("State") or payload.get("state") or "")
        return event_type in {"SoLocation2Event", "SoEvent"} and state.lower() != "down"

    def _is_left_click_down(self, event_type: str, payload: dict[str, Any]) -> bool:
        if event_type not in {"SoMouseButtonEvent", "SoEvent"}:
            return False
        button = str(payload.get("Button") or payload.get("button") or "").upper()
        state = str(payload.get("State") or payload.get("state") or "").upper()
        return button in {"BUTTON1", "LEFT"} and state == "DOWN"

    def _is_escape_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        if event_type not in {"SoKeyboardEvent", "SoEvent"}:
            return False
        key = str(payload.get("Key") or payload.get("key") or payload.get("Printable") or "").upper()
        state = str(payload.get("State") or payload.get("state") or "").upper()
        return key in {"ESCAPE", "ESC"} and state in {"DOWN", ""}

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
            return "Committed"
        return "Cancelled"
