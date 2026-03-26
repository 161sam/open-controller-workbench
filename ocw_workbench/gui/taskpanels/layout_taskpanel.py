from __future__ import annotations

from typing import Any

from ocw_workbench.services.controller_service import ControllerService


class LayoutTaskPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.form = _build_layout_form()
        self.refresh_components()

    def refresh_components(self) -> None:
        state = self.controller_service.get_state(self.doc)
        items = [component["id"] for component in state["components"]]
        _set_combo_items(self.form["component"], items)

    def apply_auto_layout(self) -> dict[str, Any]:
        strategy = _current_text(self.form["strategy"]) or "grid"
        config = {
            "grid_mm": _widget_value(self.form["grid"]),
            "spacing_mm": _widget_value(self.form["spacing"]),
            "padding_mm": _widget_value(self.form["padding"]),
        }
        return self.controller_service.auto_layout(self.doc, strategy=strategy, config=config)

    def move_selected_component(self) -> dict[str, Any]:
        component_id = _current_text(self.form["component"])
        if not component_id:
            raise ValueError("No component selected")
        return self.controller_service.move_component(
            self.doc,
            component_id=component_id,
            x=_widget_value(self.form["x"]),
            y=_widget_value(self.form["y"]),
            rotation=_widget_value(self.form["rotation"]),
        )

    def accept(self) -> bool:
        self.apply_auto_layout()
        return True


def _build_layout_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {
                "strategy": _FallbackCombo(["grid", "row", "column", "zone"]),
                "component": _FallbackCombo(),
                "grid": _FallbackValue(1.0),
                "spacing": _FallbackValue(24.0),
                "padding": _FallbackValue(10.0),
                "x": _FallbackValue(10.0),
                "y": _FallbackValue(10.0),
                "rotation": _FallbackValue(0.0),
            }

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(widget)
    strategy = QtWidgets.QComboBox()
    component = QtWidgets.QComboBox()
    grid = QtWidgets.QDoubleSpinBox()
    spacing = QtWidgets.QDoubleSpinBox()
    padding = QtWidgets.QDoubleSpinBox()
    x = QtWidgets.QDoubleSpinBox()
    y = QtWidgets.QDoubleSpinBox()
    rotation = QtWidgets.QDoubleSpinBox()
    strategy.addItems(["grid", "row", "column", "zone"])
    for spinbox in (grid, spacing, padding, x, y, rotation):
        spinbox.setRange(-1000.0, 1000.0)
    grid.setValue(1.0)
    spacing.setValue(24.0)
    padding.setValue(10.0)
    x.setValue(10.0)
    y.setValue(10.0)
    layout.addRow("Strategy", strategy)
    layout.addRow("Component", component)
    layout.addRow("Grid (mm)", grid)
    layout.addRow("Spacing (mm)", spacing)
    layout.addRow("Padding (mm)", padding)
    layout.addRow("X (mm)", x)
    layout.addRow("Y (mm)", y)
    layout.addRow("Rotation", rotation)
    return {
        "widget": widget,
        "strategy": strategy,
        "component": component,
        "grid": grid,
        "spacing": spacing,
        "padding": padding,
        "x": x,
        "y": y,
        "rotation": rotation,
    }


def _set_combo_items(combo: Any, items: list[str]) -> None:
    if hasattr(combo, "clear"):
        combo.clear()
    if hasattr(combo, "addItems"):
        combo.addItems(items)
    else:
        combo.items = list(items)
        combo.index = 0


def _current_text(combo: Any) -> str:
    if hasattr(combo, "currentText"):
        return str(combo.currentText())
    return combo.items[combo.index] if combo.items else ""


def _widget_value(widget: Any) -> float:
    if hasattr(widget, "value"):
        return float(widget.value())
    return float(widget.value)


class _FallbackCombo:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = items or []
        self.index = 0


class _FallbackValue:
    def __init__(self, value: float) -> None:
        self.value = value
