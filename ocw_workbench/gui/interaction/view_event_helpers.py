from __future__ import annotations

from typing import Any


def get_active_view(doc: Any) -> Any | None:
    """Return the active 3D view for the given FreeCAD document, or None."""
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


def get_view_point(view: Any, screen_x: float, screen_y: float) -> tuple[float, float, float] | None:
    """Map screen coordinates to a 3D point using view.getPoint()."""
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


def extract_position(payload: dict[str, Any]) -> tuple[float, float] | None:
    for key in ("Position", "position", "pos"):
        value = payload.get(key)
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (float(value[0]), float(value[1]))
    return None


def is_mouse_move(event_type: str, payload: dict[str, Any]) -> bool:
    state = str(payload.get("State") or payload.get("state") or "")
    return event_type in {"SoLocation2Event", "SoEvent"} and state.lower() != "down"


def is_left_click_down(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type not in {"SoMouseButtonEvent", "SoEvent"}:
        return False
    button = str(payload.get("Button") or payload.get("button") or "").upper()
    state = str(payload.get("State") or payload.get("state") or "").upper()
    return button in {"BUTTON1", "LEFT"} and state == "DOWN"


def is_left_click_up(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type not in {"SoMouseButtonEvent", "SoEvent"}:
        return False
    button = str(payload.get("Button") or payload.get("button") or "").upper()
    state = str(payload.get("State") or payload.get("state") or "").upper()
    return button in {"BUTTON1", "LEFT"} and state == "UP"


def is_escape_event(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type not in {"SoKeyboardEvent", "SoEvent"}:
        return False
    key = str(payload.get("Key") or payload.get("key") or payload.get("Printable") or "").upper()
    state = str(payload.get("State") or payload.get("state") or "").upper()
    return key in {"ESCAPE", "ESC"} and state in {"DOWN", ""}


def is_shift_pressed(payload: dict[str, Any]) -> bool:
    candidates = (
        payload.get("ShiftDown"),
        payload.get("shift_down"),
        payload.get("shift"),
    )
    for value in candidates:
        if isinstance(value, bool):
            return value
    modifiers = payload.get("Modifiers") or payload.get("modifiers")
    if isinstance(modifiers, (list, tuple, set)):
        return any(str(item).upper() == "SHIFT" for item in modifiers)
    if isinstance(modifiers, str):
        return "SHIFT" in modifiers.upper()
    return False
