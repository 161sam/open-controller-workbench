from __future__ import annotations

from collections import defaultdict
from typing import Any

from ocf_freecad.gui.panels._common import (
    configure_combo_box,
    configure_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    current_text,
    load_qt,
    set_combo_items,
    set_label_text,
    set_size_policy,
    set_text,
    set_value,
    text_value,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.interaction_service import InteractionService
from ocf_freecad.services.library_service import LibraryService


class ComponentsPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        library_service: LibraryService | None = None,
        interaction_service: InteractionService | None = None,
        on_selection_changed: Any | None = None,
        on_components_changed: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.library_service = library_service or LibraryService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.on_selection_changed = on_selection_changed
        self.on_components_changed = on_components_changed
        self.on_status = on_status
        self._component_lookup: dict[str, str] = {}
        self._add_library_lookup: dict[str, str] = {}
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        self.refresh_add_library()
        self.refresh_components()

    def refresh_components(self) -> None:
        state = self.controller_service.get_state(self.doc)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for component in state["components"]:
            grouped[str(component["type"])].append(component)
        self._component_lookup = {}
        labels: list[str] = []
        for category in sorted(grouped):
            for component in sorted(grouped[category], key=lambda item: item["id"]):
                label = f"{category} / {component['id']}"
                labels.append(label)
                self._component_lookup[label] = component["id"]
        set_combo_items(self.form["component"], labels)
        selected_id = state["meta"].get("selection")
        if selected_id is not None:
            self._set_selected_component(selected_id)
        if labels:
            self.load_selected_component()
            move_mode = self.interaction_service.get_settings(self.doc).get("move_component_id")
            suffix = f" 3D move active for {move_mode}." if move_mode else ""
            set_label_text(self.form["status"], f"{len(labels)} components ready. Adjust values below and save.{suffix}")
        else:
            set_text(self.form["details"], "No components in this controller yet.")
            set_label_text(self.form["status"], "Add a component from the library to start building the controller.")

    def refresh_add_library(self) -> None:
        categories = sorted({item["category"] for item in self.library_service.list_by_category()})
        set_combo_items(self.form["add_category"], ["all"] + categories)
        self.populate_add_library_components()

    def populate_add_library_components(self) -> None:
        category = current_text(self.form["add_category"])
        selected_category = None if category in {"", "all"} else category
        components = self.library_service.list_by_category(selected_category)
        labels = [f"{item['manufacturer']} {item['part_number']} ({item['id']})" for item in components]
        self._add_library_lookup = {label: item["id"] for label, item in zip(labels, components)}
        set_combo_items(self.form["add_component"], labels)

    def selected_component_id(self) -> str | None:
        return self._component_lookup.get(current_text(self.form["component"]))

    def load_selected_component(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        component = self.controller_service.get_component(self.doc, component_id)
        self.controller_service.select_component(self.doc, component_id)
        set_value(self.form["x"], float(component.get("x", 0.0)))
        set_value(self.form["y"], float(component.get("y", 0.0)))
        set_value(self.form["rotation"], float(component.get("rotation", 0.0)))
        set_text(self.form["library_ref"], str(component.get("library_ref", "")))
        set_text(
            self.form["details"],
            "\n".join(
                [
                    f"Component: {component['id']}",
                    f"Type: {component['type']}",
                    f"Library: {component.get('library_ref', '-')}",
                    f"Rotation: {float(component.get('rotation', 0.0)):.2f} deg",
                    f"Zone: {component.get('zone_id') or '-'}",
                    "Use Save Changes for normal edits. Enable 3D Move only if you want to pick positions visually.",
                ]
            ),
        )
        if self.on_selection_changed is not None:
            self.on_selection_changed(component_id)
        return component

    def update_selected_component(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        current = self.controller_service.get_component(self.doc, component_id)
        library_ref = text_value(self.form["library_ref"]).strip()
        target_x = widget_value(self.form["x"])
        target_y = widget_value(self.form["y"])
        target_rotation = widget_value(self.form["rotation"])
        position_changed = (
            float(current.get("x", 0.0)) != float(target_x)
            or float(current.get("y", 0.0)) != float(target_y)
        )
        state: dict[str, Any] | None = None
        if position_changed:
            result = self.interaction_service.move_component(
                self.doc,
                component_id=component_id,
                target_x=target_x,
                target_y=target_y,
            )
            state = result["state"]
        updates: dict[str, Any] = {}
        if float(current.get("rotation", 0.0)) != float(target_rotation):
            updates["rotation"] = target_rotation
        if library_ref and library_ref != str(current.get("library_ref", "")):
            updates["library_ref"] = library_ref
        if updates:
            state = self.controller_service.update_component(self.doc, component_id, updates)
        if state is None:
            self._publish_status(f"No changes to apply for '{component_id}'.")
            return self.controller_service.get_state(self.doc)
        self.refresh_components()
        self._publish_status(f"Saved component '{component_id}'.")
        if self.on_components_changed is not None:
            self.on_components_changed(state)
        return state

    def add_component(self) -> dict[str, Any]:
        library_ref = self._add_library_lookup.get(current_text(self.form["add_component"]))
        if not library_ref:
            raise ValueError("No library component selected")
        state = self.controller_service.add_component(
            self.doc,
            library_ref=library_ref,
            x=widget_value(self.form["add_x"]),
            y=widget_value(self.form["add_y"]),
            rotation=widget_value(self.form["add_rotation"]),
        )
        self.refresh_components()
        self._publish_status(f"Added library component '{library_ref}'.")
        if self.on_components_changed is not None:
            self.on_components_changed(state)
        return state

    def arm_move_for_selected(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        settings = self.interaction_service.arm_move(self.doc, component_id)
        self._publish_status(f"3D move is active for '{component_id}'. Use the view to pick a new location or return here to type coordinates.")
        return settings

    def snap_selected_component(self) -> dict[str, Any]:
        result = self.interaction_service.snap_selected_component(self.doc)
        self.refresh_components()
        self._publish_status(f"Snapped '{result['component_id']}' to grid.")
        if self.on_components_changed is not None:
            self.on_components_changed(result["state"])
        return result

    def handle_component_changed(self, *_args: Any) -> None:
        try:
            self.load_selected_component()
        except Exception as exc:
            self._publish_status(f"Could not load component details: {exc}")

    def handle_category_changed(self, *_args: Any) -> None:
        self.populate_add_library_components()

    def handle_update_clicked(self) -> None:
        try:
            self.update_selected_component()
        except Exception as exc:
            self._publish_status(f"Could not save component changes: {exc}")

    def handle_add_clicked(self) -> None:
        try:
            self.add_component()
        except Exception as exc:
            self._publish_status(f"Could not add component: {exc}")

    def handle_arm_move_clicked(self) -> None:
        try:
            self.arm_move_for_selected()
        except Exception as exc:
            self._publish_status(f"Could not enable 3D move: {exc}")

    def handle_snap_clicked(self) -> None:
        try:
            self.snap_selected_component()
        except Exception as exc:
            self._publish_status(f"Could not snap component: {exc}")

    def accept(self) -> bool:
        self.update_selected_component()
        return True

    def _set_selected_component(self, component_id: str) -> None:
        combo = self.form["component"]
        items = getattr(combo, "items", None)
        if items is None and hasattr(combo, "count") and hasattr(combo, "itemText"):
            items = [combo.itemText(index) for index in range(combo.count())]
        for index, label in enumerate(items or []):
            if self._component_lookup.get(str(label)) == component_id:
                combo.setCurrentIndex(index)
                return

    def _publish_status(self, message: str) -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        if hasattr(self.form["component"], "currentIndexChanged"):
            self.form["component"].currentIndexChanged.connect(self.handle_component_changed)
        if hasattr(self.form["add_category"], "currentIndexChanged"):
            self.form["add_category"].currentIndexChanged.connect(self.handle_category_changed)
        if hasattr(self.form["update_button"], "clicked"):
            self.form["update_button"].clicked.connect(self.handle_update_clicked)
        if hasattr(self.form["arm_move_button"], "clicked"):
            self.form["arm_move_button"].clicked.connect(self.handle_arm_move_clicked)
        if hasattr(self.form["snap_button"], "clicked"):
            self.form["snap_button"].clicked.connect(self.handle_snap_clicked)
        if hasattr(self.form["add_button"], "clicked"):
            self.form["add_button"].clicked.connect(self.handle_add_clicked)


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "component": FallbackCombo(),
            "x": FallbackValue(0.0),
            "y": FallbackValue(0.0),
            "rotation": FallbackValue(0.0),
            "library_ref": FallbackText(),
            "update_button": FallbackButton("Save Changes"),
            "arm_move_button": FallbackButton("Enable 3D Move"),
            "snap_button": FallbackButton("Snap To Grid"),
            "add_category": FallbackCombo(["all"]),
            "add_component": FallbackCombo(),
            "add_x": FallbackValue(10.0),
            "add_y": FallbackValue(10.0),
            "add_rotation": FallbackValue(0.0),
            "add_button": FallbackButton("Add To Controller"),
            "details": FallbackText(),
            "status": FallbackLabel(),
        }

    content = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(content)
    selector_box = qtwidgets.QGroupBox("Selected Component")
    selector_layout = qtwidgets.QFormLayout(selector_box)
    component = qtwidgets.QComboBox()
    configure_combo_box(component)
    x = qtwidgets.QDoubleSpinBox()
    y = qtwidgets.QDoubleSpinBox()
    rotation = qtwidgets.QDoubleSpinBox()
    library_ref = qtwidgets.QLineEdit()
    update_button = qtwidgets.QPushButton("Save Changes")
    arm_move_button = qtwidgets.QPushButton("Enable 3D Move")
    snap_button = qtwidgets.QPushButton("Snap To Grid")
    for spinbox in (x, y, rotation):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    selector_actions = qtwidgets.QGridLayout()
    selector_actions.addWidget(update_button, 0, 0)
    selector_actions.addWidget(arm_move_button, 0, 1)
    selector_actions.addWidget(snap_button, 1, 0, 1, 2)
    selector_layout.addRow("Component", component)
    selector_layout.addRow("X (mm)", x)
    selector_layout.addRow("Y (mm)", y)
    selector_layout.addRow("Rotation", rotation)
    selector_layout.addRow("Library Ref", library_ref)
    selector_layout.addRow("", selector_actions)
    add_box = qtwidgets.QGroupBox("Add From Library")
    add_layout = qtwidgets.QFormLayout(add_box)
    add_category = qtwidgets.QComboBox()
    add_component = qtwidgets.QComboBox()
    configure_combo_box(add_category)
    configure_combo_box(add_component)
    add_x = qtwidgets.QDoubleSpinBox()
    add_y = qtwidgets.QDoubleSpinBox()
    add_rotation = qtwidgets.QDoubleSpinBox()
    add_button = qtwidgets.QPushButton("Add To Controller")
    for spinbox in (add_x, add_y, add_rotation):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    add_x.setValue(10.0)
    add_y.setValue(10.0)
    add_layout.addRow("Category", add_category)
    add_layout.addRow("Library", add_component)
    add_layout.addRow("X (mm)", add_x)
    add_layout.addRow("Y (mm)", add_y)
    add_layout.addRow("Rotation", add_rotation)
    add_layout.addRow("", add_button)
    details = qtwidgets.QPlainTextEdit()
    configure_text_panel(details, max_height=120)
    status = qtwidgets.QLabel()
    status.setWordWrap(True)
    for child in (selector_box, add_box, component, add_category, add_component):
        set_size_policy(child, horizontal="expanding", vertical="preferred")
    layout.addWidget(selector_box)
    layout.addWidget(add_box)
    layout.addWidget(details)
    layout.addWidget(status)
    layout.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "component": component,
        "x": x,
        "y": y,
        "rotation": rotation,
        "library_ref": library_ref,
        "update_button": update_button,
        "arm_move_button": arm_move_button,
        "snap_button": snap_button,
        "add_category": add_category,
        "add_component": add_component,
        "add_x": add_x,
        "add_y": add_y,
        "add_rotation": add_rotation,
        "add_button": add_button,
        "details": details,
        "status": status,
    }
