from __future__ import annotations

from pathlib import Path
from typing import Any
import traceback

from ocf_freecad.gui.panels._common import load_qt

_ACTIVE_DIALOGS: list[Any] = []


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def icon_path(name: str) -> str:
    candidate = repo_root() / "resources" / "icons" / f"{name}.svg"
    if candidate.exists():
        return str(candidate)
    fallback = repo_root() / "resources" / "icons" / "default.svg"
    return str(fallback)


def show_error(title: str, exc: Exception | str) -> None:
    message = str(exc)
    details = traceback.format_exc() if isinstance(exc, Exception) else ""
    _show_message("critical", title, message, details=details if details.strip() else None)


def show_info(title: str, message: str, details: str | None = None) -> None:
    _show_message("information", title, message, details=details)


def open_dialog(title: str, content: Any, width: int = 720, height: int = 560) -> Any | None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return None
    dialog = qtwidgets.QDialog(_main_window())
    dialog.setWindowTitle(title)
    dialog.resize(width, height)
    layout = qtwidgets.QVBoxLayout(dialog)
    if hasattr(content, "widget"):
        layout.addWidget(content.widget)
    else:
        layout.addWidget(content)
    close_button = qtwidgets.QPushButton("Close")
    close_button.clicked.connect(dialog.close)
    layout.addWidget(close_button)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _ACTIVE_DIALOGS.append(dialog)
    dialog.finished.connect(lambda *_args: _discard_dialog(dialog))
    return dialog


def _main_window() -> Any | None:
    try:
        import FreeCADGui as Gui
    except ImportError:
        return None
    if hasattr(Gui, "getMainWindow"):
        return Gui.getMainWindow()
    return None


def _discard_dialog(dialog: Any) -> None:
    try:
        _ACTIVE_DIALOGS.remove(dialog)
    except ValueError:
        pass


def _show_message(kind: str, title: str, message: str, details: str | None = None) -> None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        print(f"{title}: {message}")
        if details:
            print(details)
        return
    box_cls = qtwidgets.QMessageBox
    if kind == "critical":
        box = box_cls(box_cls.Critical, title, message, parent=_main_window())
    else:
        box = box_cls(box_cls.Information, title, message, parent=_main_window())
    if details:
        box.setDetailedText(details)
    box.exec_()
