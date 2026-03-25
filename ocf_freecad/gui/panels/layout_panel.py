from __future__ import annotations

from typing import Any

from ocf_freecad.services.controller_service import ControllerService


class LayoutPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.form = _build_form()

    def apply_auto_layout(self) -> dict[str, Any]:
        preset = _current_text(self.form["preset"]) or "grid"
        strategy = preset if preset in {"grid", "row", "column"} else "zone"
        config = {
            "grid_mm": _widget_value(self.form["grid_mm"]),
            "spacing_mm": _widget_value(self.form["spacing_mm"]),
            "padding_mm": _widget_value(self.form["padding_mm"]),
            "strategy": strategy,
        }
        result = self.controller_service.auto_layout(self.doc, strategy=strategy, config=config)
        _set_text(
            self.form["summary"],
            (
                f"Placed: {len(result['placed_components'])}\n"
                f"Unplaced: {len(result['unplaced_component_ids'])}\n"
                f"Warnings: {len(result['warnings'])}"
            ),
        )
        return result

    def accept(self) -> bool:
        self.apply_auto_layout()
        return True


def _build_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {
                "preset": _FallbackCombo(["zone", "grid", "row", "column"]),
                "grid_mm": _FallbackValue(1.0),
                "spacing_mm": _FallbackValue(24.0),
                "padding_mm": _FallbackValue(8.0),
                "summary": _FallbackText(),
            }

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(widget)
    preset = QtWidgets.QComboBox()
    preset.addItems(["zone", "grid", "row", "column"])
    grid_mm = QtWidgets.QDoubleSpinBox()
    spacing_mm = QtWidgets.QDoubleSpinBox()
    padding_mm = QtWidgets.QDoubleSpinBox()
    summary = QtWidgets.QPlainTextEdit()
    summary.setReadOnly(True)
    for spinbox in (grid_mm, spacing_mm, padding_mm):
        spinbox.setRange(0.0, 1000.0)
    grid_mm.setValue(1.0)
    spacing_mm.setValue(24.0)
    padding_mm.setValue(8.0)
    layout.addRow("Preset", preset)
    layout.addRow("Grid (mm)", grid_mm)
    layout.addRow("Spacing (mm)", spacing_mm)
    layout.addRow("Padding (mm)", padding_mm)
    layout.addRow("Result", summary)
    return {
        "widget": widget,
        "preset": preset,
        "grid_mm": grid_mm,
        "spacing_mm": spacing_mm,
        "padding_mm": padding_mm,
        "summary": summary,
    }


def _current_text(combo: Any) -> str:
    if hasattr(combo, "currentText"):
        return str(combo.currentText())
    return combo.items[combo.index] if combo.items else ""


def _widget_value(widget: Any) -> float:
    if hasattr(widget, "value"):
        return float(widget.value())
    return float(widget.value)


def _set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
    else:
        widget.text = value


class _FallbackCombo:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = items or []
        self.index = 0


class _FallbackValue:
    def __init__(self, value: float) -> None:
        self.value = value


class _FallbackText:
    def __init__(self) -> None:
        self.text = ""
