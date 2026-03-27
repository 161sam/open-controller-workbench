from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels._common import load_qt, log_to_console

DOCK_OBJECT_NAME = "OCWWorkbenchDock"
LEGACY_DOCK_OBJECT_NAMES = ("OCFWorkbenchV2Dock",)


def get_main_window() -> Any | None:
    try:
        import FreeCADGui as Gui
    except ImportError:
        return None
    if not hasattr(Gui, "getMainWindow"):
        return None
    try:
        main_window = Gui.getMainWindow()
    except Exception:
        return None
    if main_window is not None:
        log_to_console("FreeCAD main window found.")
    return main_window


def find_existing_dock(object_name: str = DOCK_OBJECT_NAME) -> Any | None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return None
    main_window = get_main_window()
    if main_window is None:
        return None
    for candidate_name in (object_name, *LEGACY_DOCK_OBJECT_NAMES):
        dock = main_window.findChild(qtwidgets.QDockWidget, candidate_name)
        if dock is not None:
            log_to_console(f"Existing dock '{candidate_name}' found.")
            return dock
    return None


def create_or_reuse_dock(title: str, widget: Any, object_name: str = DOCK_OBJECT_NAME) -> Any | None:
    qtcore, _qtgui, qtwidgets = load_qt()
    if qtcore is None or qtwidgets is None:
        return None
    main_window = get_main_window()
    if main_window is None:
        return None

    dock = find_existing_dock(object_name)
    created = dock is None
    if dock is None:
        dock = qtwidgets.QDockWidget(title, main_window)
        dock.setObjectName(object_name)
        dock.setAllowedAreas(qtcore.Qt.LeftDockWidgetArea | qtcore.Qt.RightDockWidgetArea)
        if hasattr(dock, "setMinimumWidth"):
            dock.setMinimumWidth(360)
        if hasattr(qtwidgets.QDockWidget, "DockWidgetClosable") and hasattr(qtwidgets.QDockWidget, "DockWidgetMovable"):
            features = qtwidgets.QDockWidget.DockWidgetClosable | qtwidgets.QDockWidget.DockWidgetMovable
            if hasattr(qtwidgets.QDockWidget, "DockWidgetFloatable"):
                features |= qtwidgets.QDockWidget.DockWidgetFloatable
            dock.setFeatures(features)
        main_window.addDockWidget(qtcore.Qt.RightDockWidgetArea, dock)
        if hasattr(main_window, "resizeDocks"):
            try:
                main_window.resizeDocks([dock], [420], qtcore.Qt.Horizontal)
            except Exception:
                log_to_console("Dock resize hint skipped due to Qt/FreeCAD limitation.", level="warning")
        log_to_console("Created Open Controller dock in right dock area.")

    current_widget = dock.widget() if hasattr(dock, "widget") else None
    if current_widget is not widget and hasattr(dock, "setWidget"):
        dock.setWidget(widget)
        log_to_console("Dock widget content set.")
    if hasattr(dock, "setWindowTitle"):
        dock.setWindowTitle(title)

    if created:
        _tabify_with_existing_dock(main_window, dock, qtcore.Qt.RightDockWidgetArea)
    focus_dock(dock)
    return dock


def focus_dock(dock: Any | None) -> None:
    if dock is None:
        return
    if hasattr(dock, "show"):
        dock.show()
    if hasattr(dock, "raise_"):
        dock.raise_()
    if hasattr(dock, "activateWindow"):
        dock.activateWindow()
    log_to_console("Open Controller dock focused.")


def remove_dock(object_name: str = DOCK_OBJECT_NAME) -> bool:
    dock = find_existing_dock(object_name)
    if dock is None:
        return False
    if hasattr(dock, "setWidget") and hasattr(dock, "widget"):
        current_widget = dock.widget()
        if current_widget is not None and hasattr(current_widget, "setParent"):
            current_widget.setParent(None)
    if hasattr(dock, "close"):
        dock.close()
    log_to_console("Open Controller dock removed.")
    return True


def _tabify_with_existing_dock(main_window: Any, dock: Any, area: Any) -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return
    if not hasattr(main_window, "dockWidgetArea") or not hasattr(main_window, "tabifyDockWidget"):
        return
    for candidate in main_window.findChildren(qtwidgets.QDockWidget):
        if candidate is dock:
            continue
        try:
            candidate_area = main_window.dockWidgetArea(candidate)
        except Exception:
            continue
        if candidate_area != area:
            continue
        candidate_name = candidate.objectName() if hasattr(candidate, "objectName") else ""
        if candidate_name == DOCK_OBJECT_NAME:
            continue
        try:
            main_window.tabifyDockWidget(candidate, dock)
            log_to_console(f"Dock tabified with existing dock '{candidate_name}'.")
        except Exception:
            log_to_console("Dock tabify skipped due to Qt/FreeCAD limitation.", level="warning")
        return
