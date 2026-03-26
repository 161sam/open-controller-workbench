from __future__ import annotations

from typing import Any

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None


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
