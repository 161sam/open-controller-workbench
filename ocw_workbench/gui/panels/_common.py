from __future__ import annotations

import traceback
from typing import Any

try:
    import FreeCAD as App
except ImportError:
    App = None

_QT_MODULES: tuple[Any, Any, Any] | None = None
_QT_BINDING_NAME: str | None = None


def log_to_console(message: str, level: str = "message") -> None:
    text = f"[OCW] {message}"
    if not text.endswith("\n"):
        text += "\n"
    console = getattr(App, "Console", None) if App is not None else None
    writer_name = {
        "error": "PrintError",
        "warning": "PrintWarning",
        "message": "PrintMessage",
    }.get(level, "PrintMessage")
    writer = getattr(console, writer_name, None) if console is not None else None
    if callable(writer):
        writer(text)
        return
    print(text, end="")


def log_exception(context: str, exc: Exception) -> None:
    details = traceback.format_exc()
    if details.strip() == "NoneType: None":
        details = f"{exc.__class__.__name__}: {exc}"
    log_to_console(f"{context}: {exc.__class__.__name__}: {exc}", level="error")
    log_to_console(details.rstrip(), level="error")


def load_qt() -> tuple[Any, Any, Any]:
    global _QT_MODULES
    global _QT_BINDING_NAME

    if _QT_MODULES is not None:
        return _QT_MODULES

    attempts = [
        ("PySide", "PySide"),
        ("PySide6", "PySide6"),
        ("PySide2", "PySide2"),
    ]
    for import_name, binding_name in attempts:
        loaded = _import_qt_binding(import_name)
        if loaded is None:
            continue
        qtcore, qtgui, qtwidgets = loaded
        _QT_MODULES = (qtcore, qtgui, qtwidgets)
        _QT_BINDING_NAME = binding_name
        log_to_console(f"Qt binding loaded via {binding_name}.")
        return _QT_MODULES

    log_to_console("Unable to load a supported Qt binding (tried PySide, PySide6, PySide2).", level="error")
    _QT_BINDING_NAME = None
    _QT_MODULES = (None, None, None)
    return _QT_MODULES


def qt_binding_name() -> str:
    if _QT_MODULES is None:
        load_qt()
    return _QT_BINDING_NAME or "unavailable"


def qt_self_check() -> str:
    qtcore, qtgui, qtwidgets = load_qt()
    widgets_source = "QtWidgets" if qtwidgets is not None and qtwidgets is not qtgui else "QtGui"
    message = (
        f"Qt self-check: binding={qt_binding_name()} "
        f"QtCore={'yes' if qtcore is not None else 'no'} "
        f"QtGui={'yes' if qtgui is not None else 'no'} "
        f"widgets_source={widgets_source if qtwidgets is not None else 'none'}."
    )
    log_to_console(message)
    return message


def exec_dialog(dialog: Any) -> Any:
    executor = getattr(dialog, "exec", None)
    if not callable(executor):
        executor = getattr(dialog, "exec_", None)
    if not callable(executor):
        raise AttributeError(f"Dialog object {dialog!r} does not provide exec() or exec_()")
    return executor()


def _import_qt_binding(binding_name: str) -> tuple[Any, Any, Any] | None:
    try:
        module = __import__(binding_name, fromlist=["QtCore", "QtGui", "QtWidgets"])
        qtcore = getattr(module, "QtCore")
        qtgui = getattr(module, "QtGui")
        qtwidgets = getattr(module, "QtWidgets", None) or qtgui
        return (qtcore, qtgui, qtwidgets)
    except Exception as exc:
        log_to_console(
            f"Qt binding import failed for {binding_name}: {exc.__class__.__name__}: {exc}",
            level="warning",
        )
        return None


def set_combo_items(combo: Any, items: list[str]) -> None:
    if hasattr(combo, "clear"):
        combo.clear()
    if hasattr(combo, "addItems"):
        combo.addItems(items)
    else:
        combo.items = list(items)
        combo.index = 0


def current_text(combo: Any) -> str:
    if hasattr(combo, "currentText"):
        return str(combo.currentText())
    return combo.items[combo.index] if combo.items else ""


def set_current_text(combo: Any, value: str) -> bool:
    if hasattr(combo, "findText") and hasattr(combo, "setCurrentIndex"):
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
            return True
        return False
    if value in getattr(combo, "items", []):
        combo.index = combo.items.index(value)
        return True
    return False


def set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
        return
    if hasattr(widget, "setText"):
        widget.setText(value)
        return
    widget.text = value


def text_value(widget: Any) -> str:
    if hasattr(widget, "toPlainText"):
        return str(widget.toPlainText())
    if hasattr(widget, "text"):
        attr = widget.text
        if callable(attr):
            result = attr()
            return result if isinstance(result, str) else str(result)
        return str(attr)
    return str(getattr(widget, "text", ""))


def set_value(widget: Any, value: float) -> None:
    if hasattr(widget, "setValue"):
        widget.setValue(value)
        return
    widget.value = float(value)


def widget_value(widget: Any) -> float:
    if hasattr(widget, "value"):
        attr = widget.value
        if callable(attr):
            result = attr()
            return float(result) if not isinstance(result, float) else result
        return float(attr)
    return float(widget.value)


def set_enabled(widget: Any, enabled: bool) -> None:
    if hasattr(widget, "setEnabled"):
        widget.setEnabled(enabled)
        return
    widget.enabled = bool(enabled)


def set_label_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setText"):
        widget.setText(value)
        return
    widget.text = value


def set_tooltip(widget: Any, value: str) -> None:
    if hasattr(widget, "setToolTip"):
        widget.setToolTip(value)
        return
    widget.tooltip = value


def wrap_widget_in_scroll_area(widget: Any) -> Any:
    qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return widget
    scroll_area = qtwidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    if hasattr(scroll_area, "setHorizontalScrollBarPolicy") and qtcore is not None:
        scroll_area.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAsNeeded)
    if hasattr(scroll_area, "setVerticalScrollBarPolicy") and qtcore is not None:
        scroll_area.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAsNeeded)
    if hasattr(scroll_area, "setFrameShape") and hasattr(qtwidgets, "QFrame"):
        scroll_area.setFrameShape(qtwidgets.QFrame.NoFrame)
    if hasattr(widget, "setMinimumSize"):
        widget.setMinimumSize(0, 0)
    scroll_area.setWidget(widget)
    if hasattr(scroll_area, "setMinimumSize"):
        scroll_area.setMinimumSize(0, 0)
    set_size_policy(scroll_area, horizontal="preferred", vertical="expanding")
    return scroll_area


def configure_layout(
    layout: Any,
    *,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    spacing: int | None = None,
) -> Any:
    if hasattr(layout, "setContentsMargins"):
        layout.setContentsMargins(*margins)
    if spacing is not None and hasattr(layout, "setSpacing"):
        layout.setSpacing(spacing)
    return layout


def build_panel_container(
    qtwidgets: Any,
    *,
    spacing: int = 8,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[Any, Any]:
    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    configure_layout(layout, margins=margins, spacing=spacing)
    return widget, layout


def build_group_box(
    qtwidgets: Any,
    title: str,
    *,
    layout_kind: str = "vbox",
    spacing: int = 6,
    margins: tuple[int, int, int, int] = (8, 8, 8, 8),
) -> tuple[Any, Any]:
    group = qtwidgets.QGroupBox(title)
    layout_factory = {
        "vbox": qtwidgets.QVBoxLayout,
        "hbox": qtwidgets.QHBoxLayout,
        "form": qtwidgets.QFormLayout,
        "grid": qtwidgets.QGridLayout,
    }.get(layout_kind, qtwidgets.QVBoxLayout)
    layout = layout_factory(group)
    configure_layout(layout, margins=margins, spacing=spacing)
    return group, layout


def build_collapsible_section(
    qtwidgets: Any,
    title: str,
    *,
    expanded: bool = True,
    spacing: int = 6,
    margins: tuple[int, int, int, int] = (8, 8, 8, 8),
) -> tuple[Any, Any, Any]:
    qtcore, _qtgui, _qtwidgets = load_qt()
    widget = qtwidgets.QWidget()
    outer = qtwidgets.QVBoxLayout(widget)
    configure_layout(outer, margins=(0, 0, 0, 0), spacing=4)

    toggle = qtwidgets.QToolButton()
    if hasattr(toggle, "setText"):
        toggle.setText(title)
    if hasattr(toggle, "setCheckable"):
        toggle.setCheckable(True)
    if hasattr(toggle, "setChecked"):
        toggle.setChecked(expanded)
    if hasattr(toggle, "setToolButtonStyle") and qtcore is not None:
        toggle.setToolButtonStyle(qtcore.Qt.ToolButtonTextBesideIcon)
    if hasattr(toggle, "setArrowType") and qtcore is not None:
        toggle.setArrowType(qtcore.Qt.DownArrow if expanded else qtcore.Qt.RightArrow)
    if hasattr(toggle, "setObjectName"):
        toggle.setObjectName("OCWCollapsibleToggle")

    body = qtwidgets.QFrame()
    if hasattr(body, "setObjectName"):
        body.setObjectName("OCWCollapsibleBody")
    body_layout = qtwidgets.QVBoxLayout(body)
    configure_layout(body_layout, margins=margins, spacing=spacing)
    if hasattr(body, "setVisible"):
        body.setVisible(expanded)

    if hasattr(toggle, "toggled"):
        def _handle_toggled(checked: bool) -> None:
            if hasattr(body, "setVisible"):
                body.setVisible(bool(checked))
            if hasattr(toggle, "setArrowType") and qtcore is not None:
                toggle.setArrowType(qtcore.Qt.DownArrow if checked else qtcore.Qt.RightArrow)

        toggle.toggled.connect(_handle_toggled)

    outer.addWidget(toggle)
    outer.addWidget(body)
    return widget, body_layout, toggle


def create_text_panel(qtwidgets: Any, *, max_height: int = 160) -> Any:
    widget = qtwidgets.QPlainTextEdit()
    configure_text_panel(widget, max_height=max_height)
    return widget


def build_form_layout(
    qtwidgets: Any,
    *,
    spacing: int = 4,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Any:
    layout = qtwidgets.QFormLayout()
    configure_layout(layout, margins=margins, spacing=spacing)
    return layout


def create_label(qtwidgets: Any, text: str = "", *, word_wrap: bool = False) -> Any:
    widget = qtwidgets.QLabel(text)
    if word_wrap and hasattr(widget, "setWordWrap"):
        widget.setWordWrap(True)
    return widget


def create_wrapped_label(qtwidgets: Any, text: str = "", *, style: str | None = None) -> Any:
    widget = create_label(qtwidgets, text, word_wrap=True)
    if style and hasattr(widget, "setStyleSheet"):
        widget.setStyleSheet(style)
    return widget


def create_hint_label(qtwidgets: Any, text: str = "") -> Any:
    return create_wrapped_label(qtwidgets, text, style="color: #94a3b8;")


def create_status_label(qtwidgets: Any, text: str = "") -> Any:
    return create_wrapped_label(qtwidgets, text)


def create_row_widget(qtwidgets: Any, *widgets: Any, spacing: int = 6, stretch_index: int | None = None) -> Any:
    row = qtwidgets.QWidget()
    layout = qtwidgets.QHBoxLayout(row)
    configure_layout(layout, spacing=spacing)
    for index, widget in enumerate(widgets):
        if stretch_index is not None and index == stretch_index:
            layout.addWidget(widget, 1)
        else:
            layout.addWidget(widget)
    return row


def create_button_row(qtwidgets: Any, *buttons: Any, spacing: int = 8) -> Any:
    layout = qtwidgets.QHBoxLayout()
    configure_layout(layout, spacing=spacing)
    for button in buttons:
        layout.addWidget(button, 1)
    return layout


def add_layout_content(layout: Any, content: Any, *, stretch: int | None = None) -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    is_layout = bool(
        qtwidgets is not None
        and hasattr(qtwidgets, "QLayout")
        and isinstance(content, qtwidgets.QLayout)
    )
    if is_layout:
        if stretch is None:
            layout.addLayout(content)
        else:
            layout.addLayout(content, stretch)
        return
    if stretch is None:
        layout.addWidget(content)
    else:
        layout.addWidget(content, stretch)


def set_size_policy(widget: Any, horizontal: str = "preferred", vertical: str = "preferred") -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None or not hasattr(widget, "setSizePolicy") or not hasattr(qtwidgets, "QSizePolicy"):
        return
    policy = qtwidgets.QSizePolicy
    horizontal_policy = {
        "fixed": policy.Fixed,
        "minimum": policy.Minimum,
        "preferred": policy.Preferred,
        "expanding": policy.Expanding,
    }.get(horizontal, policy.Preferred)
    vertical_policy = {
        "fixed": policy.Fixed,
        "minimum": policy.Minimum,
        "preferred": policy.Preferred,
        "expanding": policy.Expanding,
    }.get(vertical, policy.Preferred)
    widget.setSizePolicy(horizontal_policy, vertical_policy)


def configure_text_panel(widget: Any, max_height: int = 160) -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if hasattr(widget, "setReadOnly"):
        widget.setReadOnly(True)
    if qtwidgets is not None and hasattr(qtwidgets, "QPlainTextEdit") and isinstance(widget, qtwidgets.QPlainTextEdit):
        widget.setLineWrapMode(qtwidgets.QPlainTextEdit.WidgetWidth)
    if hasattr(widget, "setMaximumHeight"):
        widget.setMaximumHeight(max_height)
    if hasattr(widget, "setMinimumHeight"):
        widget.setMinimumHeight(72)
    set_size_policy(widget, horizontal="preferred", vertical="preferred")


def configure_combo_box(widget: Any, minimum_contents_length: int = 12) -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return
    if hasattr(widget, "setMinimumSize"):
        widget.setMinimumSize(0, 0)
    if hasattr(widget, "setMinimumContentsLength"):
        widget.setMinimumContentsLength(minimum_contents_length)
    if hasattr(widget, "setSizeAdjustPolicy") and hasattr(qtwidgets, "QComboBox"):
        widget.setSizeAdjustPolicy(qtwidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
    set_size_policy(widget, horizontal="preferred", vertical="preferred")


class FallbackSignal:
    def __init__(self) -> None:
        self._callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FallbackCombo:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = list(items or [])
        self.index = 0
        self.enabled = True
        self.currentIndexChanged = FallbackSignal()

    def clear(self) -> None:
        self.items = []
        self.index = 0

    def addItems(self, items: list[str]) -> None:
        self.items.extend(items)

    def currentText(self) -> str:
        return self.items[self.index] if self.items else ""

    def findText(self, value: str) -> int:
        try:
            return self.items.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index: int) -> None:
        if not self.items:
            self.index = 0
        else:
            self.index = max(0, min(index, len(self.items) - 1))
        self.currentIndexChanged.emit(self.index)


class FallbackText:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def setPlainText(self, value: str) -> None:
        self.text = value

    def setText(self, value: str) -> None:
        self.text = value

    def toPlainText(self) -> str:
        return self.text


class FallbackValue:
    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)
        self.enabled = True

    def setValue(self, value: float) -> None:
        self.value = float(value)


class FallbackButton:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.enabled = True
        self.clicked = FallbackSignal()

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)


class FallbackLabel(FallbackText):
    pass
