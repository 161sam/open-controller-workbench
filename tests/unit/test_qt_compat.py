import builtins
import types

from ocw_workbench.gui import docking
from ocw_workbench.gui.panels import _common
from ocw_workbench.gui.runtime import _show_message
from ocw_workbench.workbench import OpenControllerWorkbench


class _Recorder:
    def __init__(self) -> None:
        self.entries = []

    def __call__(self, message: str, level: str = "message") -> None:
        self.entries.append((level, message))


def test_load_qt_falls_back_after_non_importerror(monkeypatch):
    qtcore = object()
    qtgui = object()
    pyside6_module = types.SimpleNamespace(QtCore=qtcore, QtGui=qtgui, QtWidgets=None)
    calls = []
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PySide":
            calls.append(name)
            raise NameError("_init_pyside_extension is not defined")
        if name == "PySide6":
            calls.append(name)
            return pyside6_module
        if name == "PySide2":
            calls.append(name)
            raise AssertionError("PySide2 should not be tried after a successful PySide6 import")
        return original_import(name, globals, locals, fromlist, level)

    recorder = _Recorder()
    monkeypatch.setattr(_common, "_QT_MODULES", None)
    monkeypatch.setattr(_common, "log_to_console", recorder)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    loaded_core, loaded_gui, loaded_widgets = _common.load_qt()

    assert calls == ["PySide", "PySide6"]
    assert loaded_core is qtcore
    assert loaded_gui is qtgui
    assert loaded_widgets is qtgui
    assert recorder.entries[0][0] == "warning"
    assert "PySide" in recorder.entries[0][1]
    assert recorder.entries[1] == ("message", "Qt binding loaded via PySide6.")


def test_load_qt_uses_qtgui_when_qtwidgets_is_missing(monkeypatch):
    qtcore = object()
    qtgui = object()
    pyside_module = types.SimpleNamespace(QtCore=qtcore, QtGui=qtgui)
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PySide":
            return pyside_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(_common, "_QT_MODULES", None)
    monkeypatch.setattr(_common, "log_to_console", lambda *args, **kwargs: None)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    loaded_core, loaded_gui, loaded_widgets = _common.load_qt()

    assert loaded_core is qtcore
    assert loaded_gui is qtgui
    assert loaded_widgets is qtgui


def test_qt_self_check_logs_binding(monkeypatch):
    qtcore = object()
    qtgui = object()
    recorder = _Recorder()

    monkeypatch.setattr(_common, "_QT_MODULES", (qtcore, qtgui, qtgui))
    monkeypatch.setattr(_common, "_QT_BINDING_NAME", "PySide6")
    monkeypatch.setattr(_common, "log_to_console", recorder)

    message = _common.qt_self_check()

    assert "binding=PySide6" in message
    assert recorder.entries == [("message", message)]


def test_show_message_prefers_exec(monkeypatch):
    class FakeMessageBox:
        Critical = 1
        Information = 2

        def __init__(self, *_args, **_kwargs) -> None:
            self.executed = None
            self.details = None

        def setDetailedText(self, details):
            self.details = details

        def exec(self):
            self.executed = "exec"

        def exec_(self):
            self.executed = "exec_"

    qtwidgets = types.SimpleNamespace(QMessageBox=FakeMessageBox)
    monkeypatch.setattr("ocw_workbench.gui.runtime.load_qt", lambda: (object(), object(), qtwidgets))
    monkeypatch.setattr("ocw_workbench.gui.runtime._main_window", lambda: None)

    captured = {}

    def fake_exec_dialog(dialog):
        result = _common.exec_dialog(dialog)
        captured["executed"] = dialog.executed
        captured["details"] = dialog.details
        return result

    monkeypatch.setattr("ocw_workbench.gui.runtime.exec_dialog", fake_exec_dialog)

    _show_message("critical", "Failure", "Broken", details="trace")

    assert captured["executed"] == "exec"
    assert captured["details"] == "trace"


def test_workbench_activated_logs_instead_of_raising(monkeypatch):
    fake_doc = types.SimpleNamespace(Name="Controller", Objects=[], recompute=lambda: None)
    fake_app = types.SimpleNamespace(ActiveDocument=fake_doc, newDocument=lambda name: fake_doc)
    logged = []

    monkeypatch.setattr("ocw_workbench.workbench.App", fake_app)
    monkeypatch.setattr("ocw_workbench.workbench.ensure_workbench_ui", lambda *_args, **_kwargs: (_ for _ in ()).throw(NameError("_init_pyside_extension is not defined")))
    monkeypatch.setattr("ocw_workbench.workbench.log_exception", lambda context, exc: logged.append((context, str(exc))))
    monkeypatch.setattr("ocw_workbench.workbench.ControllerService", lambda: types.SimpleNamespace(create_controller=lambda *_args, **_kwargs: None))

    workbench = OpenControllerWorkbench()
    workbench.Activated()

    assert logged == [("Workbench activation failed", "_init_pyside_extension is not defined")]


def test_create_or_reuse_dock_tabifies_existing_right_dock(monkeypatch):
    class FakeDockWidget:
        DockWidgetClosable = 1
        DockWidgetMovable = 2

        def __init__(self, title, parent):
            self.title = title
            self.parent = parent
            self._object_name = ""
            self._widget = None
            self.features = None
            self.allowed_areas = None
            self.shown = False
            self.raised = False
            self.activated = False

        def setObjectName(self, name):
            self._object_name = name

        def objectName(self):
            return self._object_name

        def setAllowedAreas(self, areas):
            self.allowed_areas = areas

        def setFeatures(self, features):
            self.features = features

        def widget(self):
            return self._widget

        def setWidget(self, widget):
            self._widget = widget

        def show(self):
            self.shown = True

        def raise_(self):
            self.raised = True

        def activateWindow(self):
            self.activated = True

    class FakeMainWindow:
        def __init__(self):
            self.children = []
            self.tabified = []
            self.areas = {}

        def findChild(self, cls, object_name):
            for child in self.children:
                if isinstance(child, cls) and child.objectName() == object_name:
                    return child
            return None

        def addDockWidget(self, area, dock):
            self.children.append(dock)
            self.areas[dock] = area

        def findChildren(self, cls):
            return [child for child in self.children if isinstance(child, cls)]

        def dockWidgetArea(self, dock):
            return self.areas[dock]

        def tabifyDockWidget(self, candidate, dock):
            self.tabified.append((candidate.objectName(), dock.objectName()))

    fake_main_window = FakeMainWindow()
    existing = FakeDockWidget("Existing", fake_main_window)
    existing.setObjectName("PropertyView")
    fake_main_window.children.append(existing)
    fake_main_window.areas[existing] = 2

    qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(LeftDockWidgetArea=1, RightDockWidgetArea=2))
    qtwidgets = types.SimpleNamespace(QDockWidget=FakeDockWidget)
    logs = []

    monkeypatch.setattr("ocw_workbench.gui.docking.load_qt", lambda: (qtcore, object(), qtwidgets))
    monkeypatch.setattr("ocw_workbench.gui.docking.get_main_window", lambda: fake_main_window)
    monkeypatch.setattr("ocw_workbench.gui.docking.log_to_console", lambda message, level="message": logs.append((level, message)))

    dock_widget = object()
    dock_ref = docking.create_or_reuse_dock("Open Controller", dock_widget)

    assert dock_ref is not None
    assert dock_ref.widget() is dock_widget
    assert fake_main_window.tabified == [("PropertyView", "OCWWorkbenchDock")]
    assert dock_ref.shown is True
    assert dock_ref.raised is True
    assert dock_ref.activated is True
    assert all("setFloating" not in message for _level, message in logs)


def test_product_workbench_panel_uses_tab_shell():
    from ocw_workbench.services.controller_service import ControllerService
    from ocw_workbench.workbench import ProductWorkbenchPanel

    class FakeDocument:
        def __init__(self) -> None:
            self.Objects = []

        def recompute(self) -> None:
            return

    doc = FakeDocument()
    panel = ProductWorkbenchPanel(doc, controller_service=ControllerService())

    assert "tabs" not in panel.form or panel.form["tabs"] is not None
