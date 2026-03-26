from __future__ import annotations

from typing import Any

from ocw_workbench.services.controller_service import ControllerService


class LibraryTaskPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.selected_category: str | None = None
        self.selected_component_id: str | None = None
        self.form = _build_library_form()
        self.refresh_categories()

    def refresh_categories(self) -> None:
        categories = sorted({component["category"] for component in self.controller_service.list_library_components()})
        _set_combo_items(self.form["category"], ["all"] + categories)
        self.populate_components()

    def populate_components(self) -> None:
        category = _current_text(self.form["category"])
        self.selected_category = None if category in {"", "all"} else category
        components = self.controller_service.list_library_components(category=self.selected_category)
        labels = [f"{component['id']} [{component['category']}]" for component in components]
        self._component_lookup = {label: component["id"] for label, component in zip(labels, components)}
        _set_combo_items(self.form["component"], labels)

    def add_selected_component(self) -> dict[str, Any]:
        label = _current_text(self.form["component"])
        component_id = self._component_lookup.get(label)
        if component_id is None:
            raise ValueError("No library component selected")
        x = float(_widget_value(self.form["x"]))
        y = float(_widget_value(self.form["y"]))
        rotation = float(_widget_value(self.form["rotation"]))
        return self.controller_service.add_component(
            self.doc,
            library_ref=component_id,
            x=x,
            y=y,
            rotation=rotation,
        )

    def accept(self) -> bool:
        self.add_selected_component()
        return True


def _build_library_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {
                "category": _FallbackCombo(),
                "component": _FallbackCombo(),
                "x": _FallbackValue(10.0),
                "y": _FallbackValue(10.0),
                "rotation": _FallbackValue(0.0),
            }

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(widget)
    category = QtWidgets.QComboBox()
    component = QtWidgets.QComboBox()
    x = QtWidgets.QDoubleSpinBox()
    y = QtWidgets.QDoubleSpinBox()
    rotation = QtWidgets.QDoubleSpinBox()
    x.setRange(-1000.0, 1000.0)
    y.setRange(-1000.0, 1000.0)
    rotation.setRange(-360.0, 360.0)
    x.setValue(10.0)
    y.setValue(10.0)
    layout.addRow("Category", category)
    layout.addRow("Component", component)
    layout.addRow("X (mm)", x)
    layout.addRow("Y (mm)", y)
    layout.addRow("Rotation", rotation)
    return {"widget": widget, "category": category, "component": component, "x": x, "y": y, "rotation": rotation}


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
    def __init__(self) -> None:
        self.items: list[str] = []
        self.index = 0


class _FallbackValue:
    def __init__(self, value: float) -> None:
        self.value = value
