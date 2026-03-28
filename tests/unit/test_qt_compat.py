import builtins
import types

from ocw_workbench.gui import docking
from ocw_workbench.gui.panels import create_panel
from ocw_workbench.gui.panels import _common
from ocw_workbench.gui.taskpanels import constraints_taskpanel, layout_taskpanel, library_taskpanel
from ocw_workbench.gui.widgets import parameter_editor, plugin_list
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


def test_add_layout_content_routes_widgets_and_layouts(monkeypatch):
    class FakeWidget:
        pass

    class FakeLayout:
        def __init__(self, *_args, **_kwargs) -> None:
            self.widgets = []
            self.layouts = []

        def addWidget(self, widget, *_args):
            if isinstance(widget, FakeLayout):
                raise TypeError("layout passed to addWidget")
            self.widgets.append(widget)

        def addLayout(self, layout, *_args):
            if not isinstance(layout, FakeLayout):
                raise TypeError("widget passed to addLayout")
            self.layouts.append(layout)

    qtwidgets = types.SimpleNamespace(QLayout=FakeLayout)
    monkeypatch.setattr(_common, "load_qt", lambda: (None, None, qtwidgets))

    parent = FakeLayout()
    row_widget = FakeWidget()
    row_layout = FakeLayout()

    _common.add_layout_content(parent, row_widget)
    _common.add_layout_content(parent, row_layout)

    assert parent.widgets == [row_widget]
    assert parent.layouts == [row_layout]


def test_add_layout_content_wraps_nested_layout_for_form_layout_without_add_layout(monkeypatch):
    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeLayout:
        pass

    class FakeFormLayout:
        def __init__(self) -> None:
            self.rows = []

        def addRow(self, widget) -> None:
            self.rows.append(widget)

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtwidgets = types.SimpleNamespace(QLayout=FakeLayout, QWidget=FakeWidget, QSizePolicy=FakeSizePolicy)
    monkeypatch.setattr(_common, "load_qt", lambda: (None, object(), qtwidgets))

    parent = FakeFormLayout()
    nested = FakeLayout()

    _common.add_layout_content(parent, nested)

    assert len(parent.rows) == 1
    assert parent.rows[0].layout_ref is nested
    assert parent.rows[0].minimum_size == (0, 0)


def test_parameter_editor_wraps_row_layout_before_adding_form_row(monkeypatch):
    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeControl:
        pass

    class FakeRowLayout:
        def __init__(self, *_args, **_kwargs) -> None:
            self.widgets = []

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

    class FakeLabel(FakeWidget):
        def __init__(self, text: str = "") -> None:
            super().__init__()
            self.text = text
            self.minimum_width = None

        def setMinimumWidth(self, width: int) -> None:
            self.minimum_width = width

        def setText(self, text: str) -> None:
            self.text = text

    class FakeFormLayout:
        def __init__(self) -> None:
            self.rows = []

        def count(self) -> int:
            return 0

        def takeAt(self, _index: int):
            raise AssertionError("takeAt should not be called for an empty layout")

        def addRow(self, label, widget) -> None:
            self.rows.append((label, widget))

    class FakeContainer:
        def __init__(self, layout) -> None:
            self._layout = layout

        def layout(self):
            return self._layout

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QHBoxLayout=FakeRowLayout,
        QLabel=FakeLabel,
        QSizePolicy=FakeSizePolicy,
    )

    monkeypatch.setattr(parameter_editor, "load_qt", lambda: (None, object(), qtwidgets))
    monkeypatch.setattr(_common, "load_qt", lambda: (None, object(), qtwidgets))

    editor = parameter_editor.ParameterEditorWidget.__new__(parameter_editor.ParameterEditorWidget)
    editor.parts = {
        "controls_container": FakeContainer(FakeFormLayout()),
        "summary": FakeLabel(),
    }
    editor._definitions = [
        {
            "id": "speed",
            "label": "Speed",
            "default": 0,
            "type": "int",
            "control": "spinbox",
        }
    ]
    editor._controls = {}
    editor.changed = parameter_editor.FallbackSignal()
    editor.preset_changed = parameter_editor.FallbackSignal()
    editor._build_control = lambda _definition, _value: FakeControl()
    editor._connect_widget = lambda _definition, _widget: None

    editor._rebuild_controls(values={"speed": 12}, sources={"speed": "preset"})

    rows = editor.parts["controls_container"].layout().rows
    assert len(rows) == 1
    label, row_widget = rows[0]
    assert label == "Speed"
    assert isinstance(row_widget, FakeWidget)
    assert isinstance(row_widget.layout_ref, FakeRowLayout)
    assert row_widget.minimum_size == (0, 0)
    assert row_widget.size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Preferred)
    assert editor.parts["summary"].text == "1 parameters available."


def test_wrap_widget_in_scroll_area_sets_resizable_container_and_layout_constraint(monkeypatch):
    class FakeLayout:
        SetMinAndMaxSize = 7

        def __init__(self) -> None:
            self.constraint = None

        def setSizeConstraint(self, value) -> None:
            self.constraint = value

    class FakeWidget:
        def __init__(self) -> None:
            self._layout = FakeLayout()
            self.minimum_size = None
            self.size_policy = None

        def layout(self):
            return self._layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeScrollArea:
        def __init__(self) -> None:
            self.resizable = False
            self.widget = None
            self.minimum_size = None
            self.size_policy = None

        def setWidgetResizable(self, value: bool) -> None:
            self.resizable = value

        def setHorizontalScrollBarPolicy(self, *_args) -> None:
            return

        def setVerticalScrollBarPolicy(self, *_args) -> None:
            return

        def setFrameShape(self, *_args) -> None:
            return

        def setWidget(self, widget) -> None:
            self.widget = widget

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeFrame:
        NoFrame = 0

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(ScrollBarAsNeeded=1))
    qtwidgets = types.SimpleNamespace(
        QScrollArea=FakeScrollArea,
        QFrame=FakeFrame,
        QSizePolicy=FakeSizePolicy,
        QLayout=FakeLayout,
    )
    monkeypatch.setattr(_common, "load_qt", lambda: (qtcore, object(), qtwidgets))

    content = FakeWidget()
    scroll_area = _common.wrap_widget_in_scroll_area(content)

    assert scroll_area.resizable is True
    assert scroll_area.widget is content
    assert content._layout.constraint == FakeLayout.SetMinAndMaxSize


def test_build_group_box_uses_layout_margin_and_minimum_expanding_policy(monkeypatch):
    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.margins = None
            self.spacing = None
            self.constraint = None
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *margins) -> None:
            self.margins = margins

        def setSpacing(self, spacing) -> None:
            self.spacing = spacing

        def setSizeConstraint(self, value) -> None:
            self.constraint = value

        def setVerticalSpacing(self, value) -> None:
            self.vertical_spacing = value

        def setHorizontalSpacing(self, value) -> None:
            self.horizontal_spacing = value

    class FakeGroupBox:
        def __init__(self, title) -> None:
            self.title = title
            self.object_name = None
            self.flat = None
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None

        def setObjectName(self, name: str) -> None:
            self.object_name = name

        def setFlat(self, flat: bool) -> None:
            self.flat = flat

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeQLayout:
        SetMinAndMaxSize = 9

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtwidgets = types.SimpleNamespace(
        QGroupBox=FakeGroupBox,
        QVBoxLayout=FakeLayout,
        QHBoxLayout=FakeLayout,
        QFormLayout=FakeLayout,
        QGridLayout=FakeLayout,
        QLayout=FakeQLayout,
        QSizePolicy=FakeSizePolicy,
    )
    monkeypatch.setattr(_common, "load_qt", lambda: (None, object(), qtwidgets))

    group, layout = _common.build_group_box(qtwidgets, "Placement Settings", layout_kind="form")

    assert group.object_name == "OCWSectionGroup"
    assert group.flat is True
    assert group.minimum_size == (0, 0)
    assert group.size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.MinimumExpanding)
    assert layout.margins == (0, _common.SPACE_1, 0, 0)
    assert layout.constraint == FakeQLayout.SetMinAndMaxSize
    assert layout.vertical_spacing == _common.SPACE_2
    assert layout.horizontal_spacing == _common.SPACE_2


def test_create_compact_header_widget_returns_widget_shell_with_safe_layout(monkeypatch):
    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.margins = None
            self.spacing = None
            self.widgets = []
            self.layouts = []
            self.constraint = None
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *margins) -> None:
            self.margins = margins

        def setSpacing(self, spacing) -> None:
            self.spacing = spacing

        def setSizeConstraint(self, value) -> None:
            self.constraint = value

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

        def addLayout(self, layout, *_args) -> None:
            self.layouts.append(layout)

    class FakeQLayout:
        SetMinAndMaxSize = 5

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QHBoxLayout=FakeLayout,
        QVBoxLayout=FakeLayout,
        QLayout=FakeQLayout,
        QSizePolicy=FakeSizePolicy,
    )
    monkeypatch.setattr(_common, "load_qt", lambda: (None, object(), qtwidgets))

    primary = object()
    secondary = object()
    trailing = object()
    header = _common.create_compact_header_widget(qtwidgets, primary, secondary=secondary, trailing=trailing)

    assert header.minimum_size == (0, 0)
    assert header.size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Preferred)
    assert trailing in header.layout_ref.widgets
    assert len(header.layout_ref.widgets) + len(header.layout_ref.layouts) >= 2


def test_task_panel_builders_use_shared_layout_defaults(monkeypatch):
    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None
            self.read_only = False
            self.line_wrap_mode = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def layout(self):
            return self.layout_ref

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

        def setReadOnly(self, value: bool) -> None:
            self.read_only = value

        def setLineWrapMode(self, value) -> None:
            self.line_wrap_mode = value

        def setMinimumHeight(self, value: int) -> None:
            self.minimum_height = value

    class FakeComboBox(FakeWidget):
        AdjustToMinimumContentsLengthWithIcon = 1

        def addItems(self, items) -> None:
            self.items = list(items)

        def setMinimumContentsLength(self, value: int) -> None:
            self.minimum_contents_length = value

        def setSizeAdjustPolicy(self, value) -> None:
            self.size_adjust_policy = value

    class FakeSpinBox(FakeWidget):
        def setRange(self, low: float, high: float) -> None:
            self.range = (low, high)

        def setValue(self, value: float) -> None:
            self.value = value

    class FakePlainTextEdit(FakeWidget):
        WidgetWidth = 1

    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.margins = None
            self.spacing = None
            self.vertical_spacing = None
            self.horizontal_spacing = None
            self.constraint = None
            self.widgets = []
            self.layouts = []
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *margins) -> None:
            self.margins = margins

        def setSpacing(self, spacing) -> None:
            self.spacing = spacing

        def setVerticalSpacing(self, spacing) -> None:
            self.vertical_spacing = spacing

        def setHorizontalSpacing(self, spacing) -> None:
            self.horizontal_spacing = spacing

        def setFieldGrowthPolicy(self, value) -> None:
            self.field_growth_policy = value

        def setLabelAlignment(self, value) -> None:
            self.label_alignment = value

        def setFormAlignment(self, value) -> None:
            self.form_alignment = value

        def setSizeConstraint(self, value) -> None:
            self.constraint = value

        def addRow(self, *_args) -> None:
            return

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

        def addLayout(self, layout, *_args) -> None:
            self.layouts.append(layout)

    class FakeQLayout:
        SetMinAndMaxSize = 7

    class FakeQFormLayout(FakeLayout):
        AllNonFixedFieldsGrow = 11

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(AlignLeft=1, AlignTop=2, AlignVCenter=4))
    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QVBoxLayout=FakeLayout,
        QHBoxLayout=FakeLayout,
        QFormLayout=FakeQFormLayout,
        QComboBox=FakeComboBox,
        QDoubleSpinBox=FakeSpinBox,
        QPlainTextEdit=FakePlainTextEdit,
        QSizePolicy=FakeSizePolicy,
        QLayout=FakeQLayout,
    )

    monkeypatch.setattr(_common, "load_qt", lambda: (qtcore, object(), qtwidgets))
    for module in (layout_taskpanel, library_taskpanel, constraints_taskpanel):
        monkeypatch.setattr(module, "load_qt", lambda: (qtcore, object(), qtwidgets))

    layout_form = layout_taskpanel._build_layout_form()
    library_form = library_taskpanel._build_library_form()
    constraints_form = constraints_taskpanel._build_constraints_form()

    assert layout_form["widget"].minimum_size == (0, 0)
    assert layout_form["widget"].size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Expanding)
    assert layout_form["strategy"].size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Preferred)
    assert library_form["widget"].minimum_size == (0, 0)
    assert library_form["category"].size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Preferred)
    assert constraints_form["widget"].minimum_size == (0, 0)
    assert constraints_form["results"].read_only is True


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


def test_emit_runtime_traceback_logs_full_details(monkeypatch):
    from ocw_workbench import workbench as workbench_module

    logged = []

    monkeypatch.setattr(workbench_module, "log_to_console", lambda message, level="message": logged.append((level, message)))
    monkeypatch.setattr(workbench_module.traceback, "format_exc", lambda: "Traceback line 1\nTraceback line 2\nValueError: broken")

    workbench_module._emit_runtime_traceback("UI build failed", ValueError("broken"))

    assert logged == [
        ("error", "UI build failed: ValueError: broken"),
        ("error", "[OCW TRACEBACK START]"),
        ("error", "Traceback line 1\nTraceback line 2\nValueError: broken"),
        ("error", "[OCW TRACEBACK END]"),
    ]


def test_build_unavailable_panel_widget_includes_traceback_view(monkeypatch):
    from ocw_workbench import workbench as workbench_module

    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

    class FakeLayout:
        SetMinAndMaxSize = 7

        def __init__(self, parent=None) -> None:
            self.widgets = []
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *_args) -> None:
            return

        def setSpacing(self, *_args) -> None:
            return

        def setSizeConstraint(self, *_args) -> None:
            return

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

    class FakeLabel(FakeWidget):
        def __init__(self, text: str = "") -> None:
            super().__init__()
            self.text = text
            self.word_wrap = False

        def setStyleSheet(self, *_args) -> None:
            return

        def setWordWrap(self, value: bool) -> None:
            self.word_wrap = value

    class FakePlainTextEdit(FakeWidget):
        NoWrap = 0

        def __init__(self) -> None:
            super().__init__()
            self.read_only = False
            self.line_wrap_mode = None
            self.plain_text = ""
            self.minimum_height = None
            self.object_name = None
            self.placeholder_text = None

        def setReadOnly(self, value: bool) -> None:
            self.read_only = value

        def setLineWrapMode(self, value) -> None:
            self.line_wrap_mode = value

        def setPlainText(self, text: str) -> None:
            self.plain_text = text

        def setMinimumHeight(self, value: int) -> None:
            self.minimum_height = value

        def setObjectName(self, value: str) -> None:
            self.object_name = value

        def setPlaceholderText(self, value: str) -> None:
            self.placeholder_text = value

    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QVBoxLayout=FakeLayout,
        QLabel=FakeLabel,
        QPlainTextEdit=FakePlainTextEdit,
        QLayout=FakeLayout,
    )

    monkeypatch.setattr(workbench_module, "load_qt", lambda: (None, object(), qtwidgets))

    widget = workbench_module._build_unavailable_panel_widget(
        "Open Controller Workbench",
        "The UI failed.",
        "AttributeError: broken",
        traceback_text="Traceback line 1\nTraceback line 2",
    )

    layout = widget.layout_ref
    assert layout is not None
    assert len(layout.widgets) == 4
    traceback_view = layout.widgets[3]
    assert isinstance(traceback_view, FakePlainTextEdit)
    assert traceback_view.read_only is True
    assert traceback_view.line_wrap_mode == FakePlainTextEdit.NoWrap
    assert traceback_view.plain_text == "Traceback line 1\nTraceback line 2"
    assert traceback_view.minimum_height == 220
    assert traceback_view.object_name == "OCWFailureTraceback"


def test_create_panel_build_wraps_nested_form_inside_selection_form(monkeypatch):
    class FakeWidget:
        def __init__(self, text: str = "") -> None:
            self.text = text
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def layout(self):
            return self.layout_ref

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

        def setWordWrap(self, _value: bool) -> None:
            return

    class FakeComboBox(FakeWidget):
        def addItems(self, items) -> None:
            self.items = list(items)

    class FakeLayout:
        def __init__(self, *_args, **_kwargs) -> None:
            self.widgets = []
            self.layouts = []
            self.spacing = None

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

        def addLayout(self, layout, *_args) -> None:
            self.layouts.append(layout)

        def addStretch(self, *_args) -> None:
            return

        def setSpacing(self, value: int) -> None:
            self.spacing = value

    class FakeFormLayout:
        def __init__(self) -> None:
            self.rows = []

        def addRow(self, *args) -> None:
            self.rows.append(args)

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    class FakeComposite:
        def __init__(self, label: str = "widget") -> None:
            self.widget = FakeWidget(label)
            self.parts = {"combo": FakeComboBox()}

    class FakeParameterEditor:
        def __init__(self) -> None:
            self.widget = FakeWidget("parameter-editor")

    qtwidgets = types.SimpleNamespace(
        QHBoxLayout=FakeLayout,
        QVBoxLayout=FakeLayout,
        QComboBox=FakeComboBox,
        QLineEdit=FakeWidget,
        QPushButton=FakeWidget,
    )

    template_layout = FakeFormLayout()
    action_layout = FakeFormLayout()
    marketplace_form = FakeFormLayout()
    selection_form = FakeFormLayout()
    created_forms = iter([marketplace_form, selection_form])
    wrapped_forms = []
    created_sections = iter(
        [
            (FakeWidget("template-section"), template_layout),
            (FakeWidget("action-section"), action_layout),
        ]
    )
    geometry_layout = FakeFormLayout()

    def _fake_collapsible(_qtwidgets, title, **_kwargs):
        if title == "Geometry":
            return (FakeWidget("geometry-section"), geometry_layout, object())
        return (FakeWidget("section"), FakeLayout(), object())

    monkeypatch.setattr(create_panel, "load_qt", lambda: (None, object(), qtwidgets))
    monkeypatch.setattr(create_panel, "build_panel_container", lambda _qtwidgets: (FakeWidget("content"), FakeLayout()))
    monkeypatch.setattr(
        create_panel,
        "create_collapsible_section_widget",
        _fake_collapsible,
    )
    monkeypatch.setattr(
        create_panel,
        "create_form_section_widget",
        lambda *_args, **_kwargs: next(created_sections),
    )
    monkeypatch.setattr(create_panel, "create_form_layout", lambda *_args, **_kwargs: next(created_forms))
    monkeypatch.setattr(create_panel, "create_hint_label", lambda _qtwidgets, text="": FakeWidget(text))
    monkeypatch.setattr(create_panel, "create_status_label", lambda _qtwidgets, text="": FakeWidget(text))
    monkeypatch.setattr(create_panel, "create_text_panel", lambda *_args, **_kwargs: FakeWidget("text-panel"))
    monkeypatch.setattr(create_panel, "create_button_row_layout", lambda *_args, **_kwargs: FakeLayout())
    monkeypatch.setattr(create_panel, "configure_combo_box", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_panel, "set_button_role", lambda button, *_args, **_kwargs: button)
    monkeypatch.setattr(create_panel, "set_size_policy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_panel, "wrap_widget_in_scroll_area", lambda widget: widget)
    monkeypatch.setattr(
        create_panel,
        "wrap_layout_in_widget",
        lambda _qtwidgets, layout: wrapped_forms.append((layout, FakeWidget("wrapped-form"))) or wrapped_forms[-1][1],
    )
    monkeypatch.setattr(create_panel, "FavoritesListWidget", lambda: FakeComposite("favorites"))
    monkeypatch.setattr(create_panel, "RecentListWidget", lambda: FakeComposite("recents"))
    monkeypatch.setattr(create_panel, "PresetListWidget", lambda: FakeComposite("presets"))
    monkeypatch.setattr(create_panel, "ParameterEditorWidget", FakeParameterEditor)

    form = create_panel._build_form()

    assert form["widget"] is not None
    assert form["template_section"] is not None
    assert form["geometry_section"] is not None
    assert form["action_section"] is not None
    assert form["document_actions_section"] is not None
    assert len(selection_form.rows) == 2
    assert selection_form.rows[0] == ("Template", form["template"])
    assert selection_form.rows[1] == ("Variant", form["variant"])
    assert len(wrapped_forms) == 2
    assert wrapped_forms[0][0] is selection_form
    assert wrapped_forms[1][0] is not selection_form
    assert len(template_layout.rows) == 3
    assert template_layout.rows[0][0].text == "wrapped-form"
    assert len(geometry_layout.rows) == 4
    assert geometry_layout.rows[0][0] is form["geometry_summary"]
    assert len(action_layout.rows) == 2
    assert action_layout.rows[0][0].text == "wrapped-form"


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


def test_create_or_reuse_dock_reuses_existing_named_dock(monkeypatch):
    class FakeDockWidget:
        DockWidgetClosable = 1
        DockWidgetMovable = 2

        def __init__(self, title, parent):
            self.title = title
            self.parent = parent
            self._object_name = ""
            self._widget = None
            self.shown = False
            self.raised = False
            self.activated = False

        def setObjectName(self, name):
            self._object_name = name

        def objectName(self):
            return self._object_name

        def setAllowedAreas(self, *_args):
            return

        def setFeatures(self, *_args):
            return

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

        def setWindowTitle(self, title):
            self.title = title

    class FakeMainWindow:
        def __init__(self):
            self.children = []
            self.added = []

        def findChild(self, cls, object_name):
            for child in self.children:
                if isinstance(child, cls) and child.objectName() == object_name:
                    return child
            return None

        def addDockWidget(self, area, dock):
            self.children.append(dock)
            self.added.append((area, dock.objectName()))

        def findChildren(self, cls):
            return [child for child in self.children if isinstance(child, cls)]

    fake_main_window = FakeMainWindow()
    existing = FakeDockWidget("Existing", fake_main_window)
    existing.setObjectName("OCWWorkbenchDock")
    existing.setWidget("old")
    fake_main_window.children.append(existing)

    qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(LeftDockWidgetArea=1, RightDockWidgetArea=2))
    qtwidgets = types.SimpleNamespace(QDockWidget=FakeDockWidget)

    monkeypatch.setattr("ocw_workbench.gui.docking.load_qt", lambda: (qtcore, object(), qtwidgets))
    monkeypatch.setattr("ocw_workbench.gui.docking.get_main_window", lambda: fake_main_window)
    monkeypatch.setattr("ocw_workbench.gui.docking.log_to_console", lambda *args, **kwargs: None)

    dock_ref = docking.create_or_reuse_dock("Open Controller", "new")

    assert dock_ref is existing
    assert dock_ref.widget() == "new"
    assert fake_main_window.added == []
    assert dock_ref.shown is True
    assert dock_ref.raised is True
    assert dock_ref.activated is True


def test_product_workbench_panel_uses_stepper_shell(monkeypatch):
    from ocw_workbench.services.controller_service import ControllerService
    from ocw_workbench import workbench as workbench_module

    class FakeStyle:
        def unpolish(self, *_args) -> None:
            return

        def polish(self, *_args) -> None:
            return

    class FakeSignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in list(self._callbacks):
                callback(*args)

    class FakeWidget:
        def __init__(self, text: str = "") -> None:
            self.text = text
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None
            self.object_name = ""
            self.word_wrap = False
            self.style_sheet = ""
            self._style = FakeStyle()
            self.properties = {}
            self.focused = False

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def layout(self):
            return self.layout_ref

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

        def setObjectName(self, name: str) -> None:
            self.object_name = name

        def setWordWrap(self, value: bool) -> None:
            self.word_wrap = value

        def setStyleSheet(self, value: str) -> None:
            self.style_sheet = value

        def setText(self, value: str) -> None:
            self.text = value

        def setProperty(self, key: str, value) -> None:
            self.properties[key] = value

        def property(self, key: str):
            return self.properties.get(key)

        def style(self):
            return self._style

        def update(self) -> None:
            return

        def setFocus(self) -> None:
            self.focused = True

    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.widgets = []
            self.margins = None
            self.spacing = None
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *margins) -> None:
            self.margins = margins

        def setSpacing(self, spacing: int) -> None:
            self.spacing = spacing

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

        def addStretch(self, *_args) -> None:
            return

    class FakeFrame(FakeWidget):
        pass

    class FakeLabel(FakeWidget):
        pass

    class FakeButton(FakeWidget):
        def __init__(self, text: str = "") -> None:
            super().__init__(text)
            self.clicked = FakeSignal()
            self.checkable = False
            self.checked = False

        def setCheckable(self, value: bool) -> None:
            self.checkable = value

        def setChecked(self, value: bool) -> None:
            self.checked = value

        def isChecked(self) -> bool:
            return self.checked

    class FakeStackedWidget(FakeWidget):
        def __init__(self) -> None:
            super().__init__()
            self.pages = []
            self.index = 0

        def addWidget(self, widget) -> None:
            self.pages.append(widget)

        def setCurrentIndex(self, index: int) -> None:
            self.index = index

        def currentIndex(self) -> int:
            return self.index

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    class FakePanel:
        def __init__(self, *args, **kwargs) -> None:
            self.widget = FakeWidget("panel")

        def refresh(self):
            return []

        def validate(self):
            return {"summary": {"error_count": 0, "warning_count": 0}}

    class FakeDocument:
        def __init__(self) -> None:
            self.Objects = []

        def recompute(self) -> None:
            return

    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QFrame=FakeFrame,
        QLabel=FakeLabel,
        QPushButton=FakeButton,
        QVBoxLayout=FakeLayout,
        QHBoxLayout=FakeLayout,
        QStackedWidget=FakeStackedWidget,
        QSizePolicy=FakeSizePolicy,
    )

    monkeypatch.setattr(workbench_module, "load_qt", lambda: (None, object(), qtwidgets))
    monkeypatch.setattr(
        workbench_module,
        "build_panel_container",
        lambda _qtwidgets, spacing=12, margins=(12, 12, 12, 12): (FakeWidget(), FakeLayout()),
    )
    monkeypatch.setattr(
        workbench_module,
        "set_size_policy",
        lambda widget, horizontal="preferred", vertical="preferred": widget.setSizePolicy(horizontal, vertical),
    )
    monkeypatch.setattr(workbench_module, "CreatePanel", FakePanel)
    monkeypatch.setattr(workbench_module, "LayoutPanel", FakePanel)
    monkeypatch.setattr(workbench_module, "ComponentsPanel", FakePanel)
    monkeypatch.setattr(workbench_module, "ConstraintsPanel", FakePanel)
    monkeypatch.setattr(workbench_module, "InfoPanel", FakePanel)
    monkeypatch.setattr(workbench_module, "PluginManagerPanel", FakePanel)
    monkeypatch.setattr(workbench_module, "OverlayRenderer", lambda *_args, **_kwargs: types.SimpleNamespace(refresh=lambda _doc: {}))
    monkeypatch.setattr(workbench_module, "_section_splitter", lambda _orientation, widgets, stretch_factors=None: widgets[0])

    panel = workbench_module.ProductWorkbenchPanel(FakeDocument(), controller_service=ControllerService())

    assert panel.form["primary_navigation"] == "stepper"
    assert panel.form["navigation_count"] == 1
    assert panel.form["navigation_items"] == ["Template", "Components", "Layout", "Validate", "Plugins"]
    assert panel.form["header_bar"] is not None
    assert panel.form["stepper_bar"] is not None
    assert len(panel.form["step_flow_markers"]) == 4
    assert panel.form["step_flow_markers"][0].text == "››"
    assert panel.form["content_host"] is not None
    assert panel.form["footer_bar"] is not None
    assert panel.form["content_host"] is panel.form["stack"]
    assert set(panel.form["step_buttons"]) == {"create", "components", "layout", "constraints", "plugins"}
    assert panel.form["title"].text == "Open Controller Workbench"
    assert panel.form["context_summary"].text.startswith("Template |")
    assert panel.form["active_step"] == "create"
    assert panel.form["step_buttons"]["create"].properties["active"] is True
    assert panel.form["step_buttons"]["components"].properties["future"] is True

    panel.focus_panel("components")
    assert panel.form["content_host"].currentIndex() == 1
    assert panel.form["step_buttons"]["components"].isChecked() is True
    assert panel.form["step_buttons"]["create"].isChecked() is False
    assert panel.form["active_step"] == "components"
    assert panel.form["step_buttons"]["create"].properties["done"] is True
    assert panel.form["step_buttons"]["create"].text.startswith("✓ ")
    assert panel.form["step_buttons"]["layout"].properties["future"] is True
    assert panel.form["step_flow_markers"][0].properties["done"] is True

    panel.focus_panel("plugins")
    assert panel.form["content_host"].currentIndex() == 4
    assert panel.form["step_buttons"]["plugins"].isChecked() is True
    assert panel.form["step_buttons"]["constraints"].properties["done"] is True
    assert panel.form["active_step"] == "plugins"


def test_create_collapsible_section_widget_returns_widget_body_and_toggle(monkeypatch):
    class FakeSignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in list(self._callbacks):
                callback(*args)

    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.minimum_size = None
            self.size_policy = None
            self.visible = True
            self.object_name = ""

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setMinimumSize(self, width: int, height: int) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

        def setVisible(self, visible: bool) -> None:
            self.visible = visible

        def setObjectName(self, name: str) -> None:
            self.object_name = name

    class FakeToolButton(FakeWidget):
        def __init__(self, *_args, **_kwargs) -> None:
            super().__init__()
            self.text_value = ""
            self.checked = False
            self.arrow = None
            self.toggled = FakeSignal()

        def setText(self, text: str) -> None:
            self.text_value = text

        def setCheckable(self, *_args) -> None:
            return

        def setChecked(self, checked: bool) -> None:
            self.checked = checked

        def setToolButtonStyle(self, *_args) -> None:
            return

        def setArrowType(self, arrow) -> None:
            self.arrow = arrow

    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.widgets = []
            self.layouts = []
            self.constraint = None
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *_args) -> None:
            return

        def setSpacing(self, *_args) -> None:
            return

        def setSizeConstraint(self, value) -> None:
            self.constraint = value

        def addWidget(self, widget, *_args) -> None:
            self.widgets.append(widget)

        def addLayout(self, layout, *_args) -> None:
            self.layouts.append(layout)

    class FakeQLayout:
        SetMinAndMaxSize = 7

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(ToolButtonTextBesideIcon=1, DownArrow=2, RightArrow=3))
    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QFrame=FakeWidget,
        QToolButton=FakeToolButton,
        QVBoxLayout=FakeLayout,
        QHBoxLayout=FakeLayout,
        QLayout=FakeQLayout,
        QSizePolicy=FakeSizePolicy,
    )
    monkeypatch.setattr(_common, "load_qt", lambda: (qtcore, object(), qtwidgets))

    widget, body_layout, toggle = _common.create_collapsible_section_widget(qtwidgets, "Helpers", expanded=False)

    assert widget.minimum_size == (0, 0)
    assert body_layout.constraint == FakeQLayout.SetMinAndMaxSize
    assert toggle.text_value == "Helpers"
    assert toggle.arrow == qtcore.Qt.RightArrow
    body = widget.layout_ref.widgets[1]
    assert body.visible is False

    toggle.toggled.emit(True)

    assert body.visible is True
    assert toggle.arrow == qtcore.Qt.DownArrow


def test_plugin_list_build_uses_widget_safe_row_insertion(monkeypatch):
    class FakeWidget:
        def __init__(self, *_args, **_kwargs) -> None:
            self.layout_ref = None
            self.visible = True
            self.object_name = ""
            self.text_value = ""

        def setLayout(self, layout) -> None:
            self.layout_ref = layout

        def setObjectName(self, name: str) -> None:
            self.object_name = name

        def setVisible(self, visible: bool) -> None:
            self.visible = visible

        def setWordWrap(self, *_args) -> None:
            return

        def setText(self, text: str) -> None:
            self.text_value = text

        def setCheckable(self, *_args) -> None:
            return

        def setChecked(self, *_args) -> None:
            return

        def setToolButtonStyle(self, *_args) -> None:
            return

        def setArrowType(self, *_args) -> None:
            return

        def setReadOnly(self, *_args) -> None:
            return

        def setLineWrapMode(self, *_args) -> None:
            return

        def setMaximumHeight(self, *_args) -> None:
            return

        def setMinimumHeight(self, *_args) -> None:
            return

        def setSizePolicy(self, *_args) -> None:
            return

        def setToolTip(self, *_args) -> None:
            return

        def setMinimumSize(self, *_args) -> None:
            return

    class FakeSignal:
        def connect(self, *_args, **_kwargs) -> None:
            return

    class FakeToolButton(FakeWidget):
        def __init__(self, *_args, **_kwargs) -> None:
            super().__init__()
            self.toggled = FakeSignal()

    class FakePlainTextEdit(FakeWidget):
        WidgetWidth = 1

    class FakeLayout:
        def __init__(self, parent=None) -> None:
            self.widgets = []
            self.layouts = []
            if parent is not None and hasattr(parent, "setLayout"):
                parent.setLayout(self)

        def setContentsMargins(self, *_args) -> None:
            return

        def setSpacing(self, *_args) -> None:
            return

        def addWidget(self, widget, *_args) -> None:
            if isinstance(widget, FakeLayout):
                raise TypeError("layout passed to addWidget")
            self.widgets.append(widget)

        def addLayout(self, layout, *_args) -> None:
            if not isinstance(layout, FakeLayout):
                raise TypeError("widget passed to addLayout")
            self.layouts.append(layout)

    class FakeComboBox(FakeWidget):
        AdjustToMinimumContentsLengthWithIcon = 1

        def addItems(self, items) -> None:
            self.items = list(items)

        def setSizeAdjustPolicy(self, *_args) -> None:
            return

        def setMinimumContentsLength(self, *_args) -> None:
            return

    class FakeLineEdit(FakeWidget):
        pass

    class FakePushButton(FakeWidget):
        pass

    class FakeLabel(FakeWidget):
        pass

    class FakeGroupBox(FakeWidget):
        pass

    class FakeFrame(FakeWidget):
        NoFrame = 0

        def setFrameShape(self, *_args) -> None:
            return

    class FakeScrollArea(FakeWidget):
        def setWidgetResizable(self, *_args) -> None:
            return

        def setHorizontalScrollBarPolicy(self, *_args) -> None:
            return

        def setVerticalScrollBarPolicy(self, *_args) -> None:
            return

        def setFrameShape(self, *_args) -> None:
            return

        def setWidget(self, widget) -> None:
            self.widget = widget

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        Expanding = 3

    qtcore = types.SimpleNamespace(
        Qt=types.SimpleNamespace(
            ToolButtonTextBesideIcon=1,
            DownArrow=2,
            RightArrow=3,
            ScrollBarAsNeeded=4,
        )
    )
    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QLayout=FakeLayout,
        QVBoxLayout=FakeLayout,
        QHBoxLayout=FakeLayout,
        QFormLayout=FakeLayout,
        QGridLayout=FakeLayout,
        QGroupBox=FakeGroupBox,
        QComboBox=FakeComboBox,
        QLineEdit=FakeLineEdit,
        QPushButton=FakePushButton,
        QLabel=FakeLabel,
        QPlainTextEdit=FakePlainTextEdit,
        QToolButton=FakeToolButton,
        QFrame=FakeFrame,
        QScrollArea=FakeScrollArea,
        QSizePolicy=FakeSizePolicy,
    )

    monkeypatch.setattr(plugin_list, "load_qt", lambda: (qtcore, object(), qtwidgets))
    monkeypatch.setattr("ocw_workbench.gui.widgets.plugin_status_badge.load_qt", lambda: (qtcore, object(), qtwidgets))
    monkeypatch.setattr("ocw_workbench.gui.panels._common.load_qt", lambda: (qtcore, object(), qtwidgets))

    widget = plugin_list.PluginListWidget()

    assert widget.widget is not None


def test_product_workbench_panel_survives_plugin_panel_init_failure(monkeypatch):
    from ocw_workbench.services.controller_service import ControllerService
    from ocw_workbench.workbench import ProductWorkbenchPanel, _UnavailablePluginManagerPanel

    class FakeDocument:
        def __init__(self) -> None:
            self.Objects = []

        def recompute(self) -> None:
            return

    monkeypatch.setattr("ocw_workbench.workbench.PluginManagerPanel", lambda *args, **kwargs: (_ for _ in ()).throw(TypeError("broken plugin panel")))

    panel = ProductWorkbenchPanel(FakeDocument(), controller_service=ControllerService())

    assert isinstance(panel.plugin_manager_panel, _UnavailablePluginManagerPanel)
    assert panel.plugin_manager_panel.error_message == "Plugins panel unavailable. Check the report view for details."


def test_add_layout_content_wraps_nested_layout_for_form_layout(monkeypatch):
    from ocw_workbench.gui.panels import _common

    class FakeWidget:
        def __init__(self) -> None:
            self.layout = None
            self.minimum_size = None
            self.size_policy = None

        def setLayout(self, layout) -> None:
            self.layout = layout

        def setMinimumSize(self, width, height) -> None:
            self.minimum_size = (width, height)

        def setSizePolicy(self, horizontal, vertical) -> None:
            self.size_policy = (horizontal, vertical)

    class FakeQLayout:
        pass

    class FakeNestedLayout(FakeQLayout):
        pass

    class FakeFormLayout:
        def __init__(self) -> None:
            self.rows = []

        def addRow(self, widget) -> None:
            self.rows.append(widget)

    class FakeSizePolicy:
        Fixed = 0
        Minimum = 1
        Preferred = 2
        MinimumExpanding = 3
        Expanding = 4

    qtwidgets = types.SimpleNamespace(
        QWidget=FakeWidget,
        QLayout=FakeQLayout,
        QSizePolicy=FakeSizePolicy,
    )

    monkeypatch.setattr(_common, "load_qt", lambda: (None, object(), qtwidgets))

    form_layout = FakeFormLayout()
    nested_layout = FakeNestedLayout()

    _common.add_layout_content(form_layout, nested_layout)

    assert len(form_layout.rows) == 1
    wrapped = form_layout.rows[0]
    assert isinstance(wrapped, FakeWidget)
    assert wrapped.layout is nested_layout
    assert wrapped.minimum_size == (0, 0)
    assert wrapped.size_policy == (FakeSizePolicy.Expanding, FakeSizePolicy.Preferred)
