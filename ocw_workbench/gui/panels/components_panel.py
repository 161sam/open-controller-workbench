from __future__ import annotations

from collections import defaultdict
from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
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
    set_current_text,
    set_size_policy,
    set_text,
    set_tooltip,
    set_value,
    text_value,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocw_workbench.gui.widgets.parameter_editor import FallbackCheckBox, ParameterEditorWidget
from ocw_workbench.services.component_property_service import ComponentPropertyService
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.library_service import LibraryService


class ComponentsPanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        library_service: LibraryService | None = None,
        property_service: ComponentPropertyService | None = None,
        interaction_service: InteractionService | None = None,
        on_selection_changed: Any | None = None,
        on_components_changed: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.library_service = library_service or LibraryService()
        self.property_service = property_service or ComponentPropertyService(self.library_service)
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.on_selection_changed = on_selection_changed
        self.on_components_changed = on_components_changed
        self.on_status = on_status
        self._component_lookup: dict[str, str] = {}
        self._add_library_lookup: dict[str, str] = {}
        self._property_model: dict[str, Any] | None = None
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._configure_specific_editor()
        self._configure_tooltips()
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
            self.load_selected_component(notify=False)
            move_mode = self.interaction_service.get_settings(self.doc).get("move_component_id")
            selection_count = len(state["meta"].get("selected_ids", []))
            suffix = f" 3D move active for {move_mode}." if move_mode else ""
            apply_status_message(
                self.form["status"],
                f"{len(labels)} components ready. {selection_count} selected. Adjust the primary selection below and save.{suffix}",
                level="info",
            )
        else:
            self._clear_component_details()
            set_text(self.form["details"], "No components in this controller yet.")
            apply_status_message(
                self.form["status"],
                "Add a component from the library to start building the controller.",
                level="info",
            )

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

    def load_selected_component(self, notify: bool = True) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        component = self.controller_service.get_component(self.doc, component_id)
        if self.controller_service.get_ui_context(self.doc).get("selection") != component_id:
            self.controller_service.select_component(self.doc, component_id)
        self._property_model = self.property_service.build_property_model(component)
        values = self.property_service.reset_values(self._property_model)
        set_value(self.form["x"], float(values.get("x", 0.0)))
        set_value(self.form["y"], float(values.get("y", 0.0)))
        set_value(self.form["rotation"], float(values.get("rotation", 0.0)))
        set_text(self.form["label"], str(values.get("label", "")))
        set_text(self.form["tags"], str(values.get("tags", "")))
        if hasattr(self.form["visible"], "setChecked"):
            self.form["visible"].setChecked(bool(values.get("visible", True)))
        set_text(self.form["selected_id"], f"ID: {component['id']}")
        set_text(self.form["selected_type"], f"Type: {self._property_model['category']}")
        set_text(self.form["selected_library"], f"Library: {self._property_model['library_label']}")
        self._populate_library_ref_options(self._property_model)
        self._set_specific_fields(self._property_model)
        set_text(self.form["details"], self._build_details_text(component, self._property_model))
        if notify and self.on_selection_changed is not None:
            self.on_selection_changed(component_id)
        return component

    def update_selected_component(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        current = self.controller_service.get_component(self.doc, component_id)
        model = self._property_model or self.property_service.build_property_model(current)
        values = self._read_form_values(model)
        updates = self._changed_updates(model, values)
        if not updates:
            self._publish_status(f"No changes to apply for '{component_id}'. Adjust placement or properties first.")
            return self.controller_service.get_state(self.doc)
        target_x = float(values["x"])
        target_y = float(values["y"])
        position_changed = (
            "x" in updates
            or "y" in updates
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
            updates.pop("x", None)
            updates.pop("y", None)
        if updates:
            state = self.controller_service.update_component(self.doc, component_id, updates)
        if state is None:
            return self.controller_service.get_state(self.doc)
        self.refresh_components()
        self._publish_status(f"Applied changes to '{component_id}'. Placement and component properties are up to date.")
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
        self._publish_status(f"Added '{library_ref}'. Review its position below and adjust if needed.")
        if self.on_components_changed is not None:
            self.on_components_changed(state)
        return state

    def arm_move_for_selected(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        settings = self.interaction_service.arm_move(self.doc, component_id)
        self._publish_status(
            f"Pick In 3D is active for '{component_id}'. Click in the view to choose a new location, "
            "or return here and edit X/Y directly."
        )
        return settings

    def snap_selected_component(self) -> dict[str, Any]:
        result = self.interaction_service.snap_selected_component(self.doc)
        self.refresh_components()
        self._publish_status(f"Snapped '{result['component_id']}' to the current grid.")
        if self.on_components_changed is not None:
            self.on_components_changed(result["state"])
        return result

    def handle_component_changed(self, *_args: Any) -> None:
        try:
            self.load_selected_component()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not load component details", exc))

    def handle_category_changed(self, *_args: Any) -> None:
        self.populate_add_library_components()

    def handle_update_clicked(self) -> None:
        try:
            self.update_selected_component()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not apply component changes", exc))

    def handle_add_clicked(self) -> None:
        try:
            self.add_component()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not add component", exc))

    def handle_arm_move_clicked(self) -> None:
        try:
            self.arm_move_for_selected()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not enable Pick In 3D", exc))

    def handle_snap_clicked(self) -> None:
        try:
            self.snap_selected_component()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not snap component", exc))

    def handle_reset_clicked(self) -> None:
        try:
            self.load_selected_component(notify=False)
            self._publish_status("Reset the editor to the current component state.")
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not reset component properties", exc))

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
        level = "error" if message.lower().startswith("could not") else "info"
        apply_status_message(self.form["status"], message, level=level)
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
        if hasattr(self.form["reset_button"], "clicked"):
            self.form["reset_button"].clicked.connect(self.handle_reset_clicked)
        if hasattr(self.form["add_button"], "clicked"):
            self.form["add_button"].clicked.connect(self.handle_add_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["component"], "Select the component you want to inspect or adjust.")
        set_tooltip(self.form["x"], "Horizontal center position in millimeters.")
        set_tooltip(self.form["y"], "Vertical center position in millimeters.")
        set_tooltip(self.form["rotation"], "Rotation around the component center in degrees.")
        set_tooltip(self.form["library_ref"], "Choose the component variant from the library family.")
        set_tooltip(self.form["label"], "Human-readable label shown in exported data and inspectors.")
        set_tooltip(self.form["tags"], "Comma-separated tags for grouping, filtering or downstream workflows.")
        set_tooltip(self.form["visible"], "Toggle whether the component is treated as visible metadata.")
        set_tooltip(self.form["update_button"], "Apply the edited placement and component properties.")
        set_tooltip(self.form["arm_move_button"], "Pick a new location directly in the 3D view.")
        set_tooltip(self.form["snap_button"], "Move the selected component to the current snap grid.")
        set_tooltip(self.form["reset_button"], "Discard unsaved panel edits and reload the selected component.")
        set_tooltip(self.form["add_category"], "Filter the component library by category.")
        set_tooltip(self.form["add_component"], "Choose the library part to insert into the controller.")
        set_tooltip(self.form["add_x"], "Initial X position for the new component.")
        set_tooltip(self.form["add_y"], "Initial Y position for the new component.")
        set_tooltip(self.form["add_rotation"], "Initial rotation for the new component.")
        set_tooltip(self.form["add_button"], "Insert the selected library component into the active controller.")

    def _configure_specific_editor(self) -> None:
        preset = self.form["specific_editor"].parts.get("preset")
        apply_button = self.form["specific_editor"].parts.get("apply_preset_button")
        summary = self.form["specific_editor"].parts.get("summary")
        if hasattr(preset, "hide"):
            preset.hide()
        if hasattr(apply_button, "hide"):
            apply_button.hide()
        set_text(summary, "Type-specific properties are generated from the selected library component.")

    def _populate_library_ref_options(self, model: dict[str, Any]) -> None:
        variant_field = next((field for field in model["fields"] if field["id"] == "library_ref"), None)
        labels = [str(option["label"]) for option in variant_field.get("options", [])] if variant_field else []
        set_combo_items(self.form["library_ref"], labels)
        if not variant_field:
            return
        current_value = str(variant_field.get("value", ""))
        for option in variant_field.get("options", []):
            if str(option["value"]) == current_value:
                set_current_text(self.form["library_ref"], str(option["label"]))
                return

    def _set_specific_fields(self, model: dict[str, Any]) -> None:
        definitions = [_property_definition(field) for field in model["fields"] if field["id"] not in {"x", "y", "rotation", "label", "tags", "visible", "library_ref"}]
        values = {definition["id"]: definition["default"] for definition in definitions}
        self.form["specific_editor"].set_schema(definitions, [], values, sources={}, preset_id=None)

    def _read_form_values(self, model: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {
            "x": widget_value(self.form["x"]),
            "y": widget_value(self.form["y"]),
            "rotation": widget_value(self.form["rotation"]),
            "label": text_value(self.form["label"]).strip(),
            "tags": text_value(self.form["tags"]).strip(),
            "visible": bool(self.form["visible"].isChecked()) if hasattr(self.form["visible"], "isChecked") else bool(getattr(self.form["visible"], "checked", True)),
        }
        variant_field = next((field for field in model["fields"] if field["id"] == "library_ref"), None)
        variant_label = current_text(self.form["library_ref"])
        if variant_field:
            variant_value = str(variant_field.get("value", ""))
            for option in variant_field.get("options", []):
                if str(option["label"]) == variant_label:
                    variant_value = str(option["value"])
                    break
            values["library_ref"] = variant_value
        values.update(self.form["specific_editor"].values())
        return values

    def _changed_updates(self, model: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        baseline = self.property_service.reset_values(model)
        changed: dict[str, Any] = {}
        for field_id, current_value in values.items():
            original = baseline.get(field_id)
            if _values_equal(original, current_value):
                continue
            changed[field_id] = current_value
        return self.property_service.normalize_updates(model, changed)

    def _clear_component_details(self) -> None:
        self._property_model = None
        set_text(self.form["selected_id"], "ID: -")
        set_text(self.form["selected_type"], "Type: -")
        set_text(self.form["selected_library"], "Library: -")
        set_value(self.form["x"], 0.0)
        set_value(self.form["y"], 0.0)
        set_value(self.form["rotation"], 0.0)
        set_combo_items(self.form["library_ref"], [])
        set_text(self.form["label"], "")
        set_text(self.form["tags"], "")
        if hasattr(self.form["visible"], "setChecked"):
            self.form["visible"].setChecked(True)
        self.form["specific_editor"].clear()

    def _build_details_text(self, component: dict[str, Any], model: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"Component: {component['id']}",
                f"Type: {component['type']}",
                f"Library: {component.get('library_ref', '-')}",
                f"Rotation: {float(component.get('rotation', 0.0)):.2f} deg",
                f"Zone: {component.get('zone_id') or '-'}",
                "Groups: placement, generic metadata, and type-specific properties.",
                "Normal workflow: adjust values here, apply changes, then validate if geometry changed.",
                model["details"],
            ]
        )


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    specific_editor = ParameterEditorWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "component": FallbackCombo(),
            "selected_id": FallbackLabel("ID: -"),
            "selected_type": FallbackLabel("Type: -"),
            "selected_library": FallbackLabel("Library: -"),
            "x": FallbackValue(0.0),
            "y": FallbackValue(0.0),
            "rotation": FallbackValue(0.0),
            "library_ref": FallbackCombo(),
            "label": FallbackText(),
            "tags": FallbackText(),
            "visible": FallbackCheckBox(True),
            "specific_editor": specific_editor,
            "update_button": FallbackButton("Apply Changes"),
            "arm_move_button": FallbackButton("Pick In 3D"),
            "snap_button": FallbackButton("Snap To Grid"),
            "reset_button": FallbackButton("Reset Properties"),
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
    selector_box = qtwidgets.QGroupBox("Adjust Selected Component")
    selector_layout = qtwidgets.QFormLayout(selector_box)
    component = qtwidgets.QComboBox()
    configure_combo_box(component)
    selected_id = qtwidgets.QLabel("ID: -")
    selected_type = qtwidgets.QLabel("Type: -")
    selected_library = qtwidgets.QLabel("Library: -")
    x = qtwidgets.QDoubleSpinBox()
    y = qtwidgets.QDoubleSpinBox()
    rotation = qtwidgets.QDoubleSpinBox()
    library_ref = qtwidgets.QComboBox()
    label = qtwidgets.QLineEdit()
    tags = qtwidgets.QLineEdit()
    visible = qtwidgets.QCheckBox()
    visible.setChecked(True)
    update_button = qtwidgets.QPushButton("Apply Changes")
    arm_move_button = qtwidgets.QPushButton("Pick In 3D")
    snap_button = qtwidgets.QPushButton("Snap To Grid")
    reset_button = qtwidgets.QPushButton("Reset Properties")
    configure_combo_box(library_ref)
    set_tooltip(component, "Select the component you want to inspect or adjust.")
    set_tooltip(x, "Horizontal center position in millimeters.")
    set_tooltip(y, "Vertical center position in millimeters.")
    set_tooltip(rotation, "Rotation around the component center in degrees.")
    set_tooltip(library_ref, "Choose the component variant from the library family.")
    set_tooltip(label, "Human-readable label shown in exported data and inspectors.")
    set_tooltip(tags, "Comma-separated tags for grouping, filtering or downstream workflows.")
    set_tooltip(visible, "Toggle whether the component is treated as visible metadata.")
    set_tooltip(update_button, "Apply the edited placement and component properties.")
    set_tooltip(arm_move_button, "Pick a new location directly in the 3D view.")
    set_tooltip(snap_button, "Move the selected component to the current snap grid.")
    set_tooltip(reset_button, "Discard unsaved panel edits and reload the selected component.")
    for spinbox in (x, y, rotation):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    selector_actions = qtwidgets.QGridLayout()
    selector_actions.addWidget(update_button, 0, 0)
    selector_actions.addWidget(arm_move_button, 0, 1)
    selector_actions.addWidget(snap_button, 1, 0)
    selector_actions.addWidget(reset_button, 1, 1)
    selector_layout.addRow("Component", component)
    selector_layout.addRow("", selected_id)
    selector_layout.addRow("", selected_type)
    selector_layout.addRow("", selected_library)
    selector_layout.addRow("X (mm)", x)
    selector_layout.addRow("Y (mm)", y)
    selector_layout.addRow("Rotation", rotation)
    selector_layout.addRow("Variant", library_ref)
    selector_layout.addRow("Label", label)
    selector_layout.addRow("Tags", tags)
    selector_layout.addRow("Visible", visible)
    selector_layout.addRow("Type-Specific", specific_editor.widget)
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
    set_tooltip(add_category, "Filter the component library by category.")
    set_tooltip(add_component, "Choose the library part to insert into the controller.")
    set_tooltip(add_x, "Initial X position for the new component.")
    set_tooltip(add_y, "Initial Y position for the new component.")
    set_tooltip(add_rotation, "Initial rotation for the new component.")
    set_tooltip(add_button, "Insert the selected library component into the active controller.")
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
        "selected_id": selected_id,
        "selected_type": selected_type,
        "selected_library": selected_library,
        "x": x,
        "y": y,
        "rotation": rotation,
        "library_ref": library_ref,
        "label": label,
        "tags": tags,
        "visible": visible,
        "specific_editor": specific_editor,
        "update_button": update_button,
        "arm_move_button": arm_move_button,
        "snap_button": snap_button,
        "reset_button": reset_button,
        "add_category": add_category,
        "add_component": add_component,
        "add_x": add_x,
        "add_y": add_y,
        "add_rotation": add_rotation,
        "add_button": add_button,
        "details": details,
        "status": status,
    }


def _friendly_component_error(prefix: str, exc: Exception) -> str:
    message = str(exc).strip().lower()
    if "unknown component id" in message:
        return f"{prefix}. The selected component is no longer available. Refresh the list and try again."
    return friendly_ui_error(prefix, exc)


def _property_definition(field: dict[str, Any]) -> dict[str, Any]:
    field_type = str(field["type"])
    return {
        "id": str(field["id"]),
        "label": str(field["label"]),
        "type": field_type,
        "default": field.get("value"),
        "control": "select" if field_type == "enum" else "input",
        "unit": field.get("unit"),
        "options": list(field.get("options", [])),
        "help": field.get("help"),
    }


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return float(left or 0.0) == float(right or 0.0)
    return left == right
