from __future__ import annotations

from collections import defaultdict
from typing import Any

from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.library_service import LibraryService


class ComponentsPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        library_service: LibraryService | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.library_service = library_service or LibraryService()
        self._component_lookup: dict[str, str] = {}
        self._add_library_lookup: dict[str, str] = {}
        self.form = _build_form()
        self.refresh_add_library()
        self.refresh_components()

    def refresh_components(self) -> None:
        state = self.controller_service.get_state(self.doc)
        grouped: dict[str, list[str]] = defaultdict(list)
        self._component_lookup = {}
        for component in state["components"]:
            label = f"{component['type']} / {component['id']}"
            grouped[str(component["type"])].append(label)
            self._component_lookup[label] = component["id"]
        labels = []
        for category in sorted(grouped):
            labels.extend(sorted(grouped[category]))
        _set_combo_items(self.form["component"], labels)
        if labels:
            self.load_selected_component()
        else:
            _set_text(self.form["details"], "No components in controller.")

    def refresh_add_library(self) -> None:
        categories = sorted({item["category"] for item in self.library_service.list_by_category()})
        _set_combo_items(self.form["add_category"], ["all"] + categories)
        self.populate_add_library_components()

    def populate_add_library_components(self) -> None:
        category = _current_text(self.form["add_category"])
        selected_category = None if category in {"", "all"} else category
        components = self.library_service.list_by_category(selected_category)
        labels = [f"{item['manufacturer']} {item['part_number']} ({item['id']})" for item in components]
        self._add_library_lookup = {label: item["id"] for label, item in zip(labels, components)}
        _set_combo_items(self.form["add_component"], labels)

    def selected_component_id(self) -> str | None:
        label = _current_text(self.form["component"])
        return self._component_lookup.get(label)

    def load_selected_component(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        component = self.controller_service.get_component(self.doc, component_id)
        self.controller_service.select_component(self.doc, component_id)
        _set_value(self.form["x"], float(component.get("x", 0.0)))
        _set_value(self.form["y"], float(component.get("y", 0.0)))
        _set_value(self.form["rotation"], float(component.get("rotation", 0.0)))
        _set_text(self.form["library_ref"], str(component.get("library_ref", "")))
        _set_text(
            self.form["details"],
            (
                f"Component: {component['id']}\n"
                f"Type: {component['type']}\n"
                f"Library: {component.get('library_ref', '-')}\n"
                f"Zone: {component.get('zone_id') or '-'}"
            ),
        )
        return component

    def update_selected_component(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        library_ref = _text_value(self.form["library_ref"]).strip()
        updates = {
            "x": _widget_value(self.form["x"]),
            "y": _widget_value(self.form["y"]),
            "rotation": _widget_value(self.form["rotation"]),
        }
        if library_ref:
            updates["library_ref"] = library_ref
        state = self.controller_service.update_component(self.doc, component_id, updates)
        self.refresh_components()
        return state

    def add_component(self) -> dict[str, Any]:
        library_ref = self._add_library_lookup.get(_current_text(self.form["add_component"]))
        if not library_ref:
            raise ValueError("No library component selected")
        state = self.controller_service.add_component(
            self.doc,
            library_ref=library_ref,
            x=_widget_value(self.form["add_x"]),
            y=_widget_value(self.form["add_y"]),
            rotation=_widget_value(self.form["add_rotation"]),
        )
        self.refresh_components()
        return state

    def accept(self) -> bool:
        self.update_selected_component()
        return True


def _build_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {
                "component": _FallbackCombo(),
                "add_category": _FallbackCombo(["all"]),
                "add_component": _FallbackCombo(),
                "x": _FallbackValue(0.0),
                "y": _FallbackValue(0.0),
                "rotation": _FallbackValue(0.0),
                "library_ref": _FallbackText(),
                "add_x": _FallbackValue(10.0),
                "add_y": _FallbackValue(10.0),
                "add_rotation": _FallbackValue(0.0),
                "details": _FallbackText(),
            }

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    form = QtWidgets.QFormLayout()
    component = QtWidgets.QComboBox()
    add_category = QtWidgets.QComboBox()
    add_component = QtWidgets.QComboBox()
    x = QtWidgets.QDoubleSpinBox()
    y = QtWidgets.QDoubleSpinBox()
    rotation = QtWidgets.QDoubleSpinBox()
    library_ref = QtWidgets.QLineEdit()
    add_x = QtWidgets.QDoubleSpinBox()
    add_y = QtWidgets.QDoubleSpinBox()
    add_rotation = QtWidgets.QDoubleSpinBox()
    details = QtWidgets.QPlainTextEdit()
    details.setReadOnly(True)
    for spinbox in (x, y, rotation, add_x, add_y, add_rotation):
        spinbox.setRange(-1000.0, 1000.0)
    add_x.setValue(10.0)
    add_y.setValue(10.0)
    form.addRow("Component", component)
    form.addRow("X (mm)", x)
    form.addRow("Y (mm)", y)
    form.addRow("Rotation", rotation)
    form.addRow("Library Ref", library_ref)
    form.addRow("Add Category", add_category)
    form.addRow("Add Component", add_component)
    form.addRow("Add X", add_x)
    form.addRow("Add Y", add_y)
    form.addRow("Add Rotation", add_rotation)
    layout.addLayout(form)
    layout.addWidget(details)
    return {
        "widget": widget,
        "component": component,
        "add_category": add_category,
        "add_component": add_component,
        "x": x,
        "y": y,
        "rotation": rotation,
        "library_ref": library_ref,
        "add_x": add_x,
        "add_y": add_y,
        "add_rotation": add_rotation,
        "details": details,
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


def _set_value(widget: Any, value: float) -> None:
    if hasattr(widget, "setValue"):
        widget.setValue(value)
    else:
        widget.value = value


def _set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
    elif hasattr(widget, "setText"):
        widget.setText(value)
    else:
        widget.text = value


def _text_value(widget: Any) -> str:
    if hasattr(widget, "text"):
        result = widget.text()
        return str(result) if not isinstance(result, str) else result
    return str(getattr(widget, "text", ""))


class _FallbackCombo:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items: list[str] = items or []
        self.index = 0


class _FallbackValue:
    def __init__(self, value: float) -> None:
        self.value = value


class _FallbackText:
    def __init__(self) -> None:
        self.text = ""
