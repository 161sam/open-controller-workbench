from __future__ import annotations

from typing import Any

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

try:
    from ocw_workbench.gui.panels._common import load_qt
except Exception:
    load_qt = None

_CURSOR_BY_ROLE = {
    "default": "ArrowCursor",
    "place": "CrossCursor",
    "pick": "PointingHandCursor",
    "drag_ready": "OpenHandCursor",
    "drag_active": "ClosedHandCursor",
    "edit_ready": "PointingHandCursor",
    "edit_active": "ClosedHandCursor",
}


def activate_document(doc: Any) -> bool:
    if Gui is None:
        return False
    doc_name = getattr(doc, "Name", None)
    if not isinstance(doc_name, str) or not doc_name:
        return False
    try:
        if hasattr(Gui, "setActiveDocument"):
            Gui.setActiveDocument(doc_name)
        return True
    except Exception:
        return False


def reveal_generated_objects(doc: Any, prefixes: tuple[str, ...] = ("OCW_", "OCF_")) -> int:
    count = 0
    for obj in getattr(doc, "Objects", []):
        label = str(getattr(obj, "Label", getattr(obj, "Name", "")))
        name = str(getattr(obj, "Name", ""))
        if not any(label.startswith(prefix) or name.startswith(prefix) for prefix in prefixes):
            continue
        view = getattr(obj, "ViewObject", None)
        if view is None:
            continue
        if hasattr(view, "Visibility"):
            view.Visibility = True
        count += 1
    return count


def focus_view(doc: Any, fit: bool = True) -> bool:
    if Gui is None:
        return False
    activate_document(doc)
    gui_doc = None
    doc_name = getattr(doc, "Name", None)
    if isinstance(doc_name, str) and hasattr(Gui, "getDocument"):
        try:
            gui_doc = Gui.getDocument(doc_name)
        except Exception:
            gui_doc = None
    if gui_doc is None:
        gui_doc = getattr(Gui, "ActiveDocument", None)
    if gui_doc is None or not hasattr(gui_doc, "activeView"):
        return False
    try:
        view = gui_doc.activeView()
    except Exception:
        return False
    if view is None:
        return False
    try:
        if hasattr(view, "viewAxometric"):
            view.viewAxometric()
        if fit:
            if hasattr(view, "fitAll"):
                view.fitAll()
            elif hasattr(Gui, "SendMsgToActiveView"):
                Gui.SendMsgToActiveView("ViewFit")
        return True
    except Exception:
        return False


def set_interaction_cursor(view: Any, role: str) -> bool:
    if view is None or not hasattr(view, "setCursor"):
        return False
    try:
        view.setCursor(_resolve_qt_cursor(_CURSOR_BY_ROLE.get(role, _CURSOR_BY_ROLE["default"])))
        return True
    except Exception:
        return False


def clear_interaction_cursor(view: Any) -> bool:
    if view is None:
        return False
    try:
        if hasattr(view, "unsetCursor"):
            view.unsetCursor()
            return True
        if hasattr(view, "setCursor"):
            view.setCursor(_resolve_qt_cursor(_CURSOR_BY_ROLE["default"]))
            return True
    except Exception:
        return False
    return False


def sync_selection(doc: Any, component_id: str | None) -> bool:
    if Gui is None or doc is None or not hasattr(Gui, "Selection"):
        return False
    selection = getattr(Gui, "Selection", None)
    if selection is None:
        return False
    try:
        if hasattr(selection, "clearSelection"):
            selection.clearSelection()
        if component_id is None:
            return True
        target = _find_component_object(doc, component_id)
        if target is None:
            return False
        doc_name = getattr(doc, "Name", None)
        object_name = getattr(target, "Name", None)
        if hasattr(selection, "addSelection"):
            if isinstance(doc_name, str) and doc_name and isinstance(object_name, str) and object_name:
                selection.addSelection(doc_name, object_name)
            else:
                selection.addSelection(target)
        return True
    except Exception:
        return False


def _resolve_qt_cursor(cursor_name: str) -> Any:
    if load_qt is None:
        return cursor_name
    try:
        qtcore, qtgui, _qtwidgets = load_qt()
    except Exception:
        return cursor_name
    if qtcore is None or qtgui is None:
        return cursor_name
    cursor_shape = getattr(getattr(qtcore, "Qt", object()), cursor_name, None)
    if cursor_shape is None:
        return cursor_name
    try:
        return qtgui.QCursor(cursor_shape)
    except Exception:
        return cursor_name


def _find_component_object(doc: Any, component_id: str) -> Any | None:
    for obj in getattr(doc, "Objects", []):
        if getattr(obj, "OCWComponentId", None) == component_id:
            return obj
    return None
