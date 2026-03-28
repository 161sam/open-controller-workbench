from __future__ import annotations

from collections import defaultdict
from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
    build_panel_container,
    configure_combo_box,
    create_button_row_layout,
    create_collapsible_section_widget,
    create_compact_header_widget,
    create_form_section_widget,
    create_hint_label,
    create_inline_status_widget,
    create_row_widget,
    create_section_widget,
    create_status_label,
    create_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    current_text,
    load_qt,
    set_enabled,
    set_combo_items,
    set_current_text,
    set_button_role,
    set_size_policy,
    set_text,
    set_tooltip,
    set_value,
    text_value,
    wrap_widget_in_scroll_area,
    widget_value,
)
from ocw_workbench.services.component_bulk_edit_service import ComponentBulkEditService
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
        self._bulk_model: dict[str, Any] | None = None
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
        selected_ids = list(state["meta"].get("selected_ids", []))
        self._set_context_summary(component_count=len(labels), selection_count=len(selected_ids))
        self._set_widget_visible(self.form["empty_state_box"], not bool(labels))
        self._set_widget_visible(self.form["component_list_box"], bool(labels))
        if selected_id is not None:
            self._set_selected_component(selected_id)
        if labels:
            if len(selected_ids) > 1:
                self.load_bulk_selection(notify=False)
            else:
                self.load_selected_component(notify=False)
            move_mode = self.interaction_service.get_settings(self.doc).get("move_component_id")
            selection_count = len(selected_ids)
            suffix = f" 3D move active for {move_mode}." if move_mode else ""
            apply_status_message(
                self.form["status"],
                f"{len(labels)} components available. {selection_count} selected.{suffix}",
                level="info",
            )
        else:
            self._clear_component_details()
            set_text(self.form["details"], "No components yet. Use Quick Add to place the first one.")
            apply_status_message(
                self.form["status"],
                "Add a component to start building the controller.",
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
        self._bulk_model = None
        self._set_bulk_mode(False)
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
        self._set_widget_visible(self.form["selector_details"], True)
        self._set_widget_visible(self.form["selected_component_box"], True)
        self._set_widget_visible(self.form["selected_empty_state"], False)
        self._populate_library_ref_options(self._property_model)
        self._set_specific_fields(self._property_model)
        set_text(self.form["details"], self._build_details_text(component, self._property_model))
        if notify and self.on_selection_changed is not None:
            self.on_selection_changed(component_id)
        return component

    def load_bulk_selection(self, notify: bool = True) -> list[dict[str, Any]]:
        component_ids = self.controller_service.get_selected_component_ids(self.doc)
        if len(component_ids) < 2:
            raise ValueError("Bulk edit requires multiple selected components")
        components = [self.controller_service.get_component(self.doc, component_id) for component_id in component_ids]
        self._bulk_model = ComponentBulkEditService(self.property_service, self.library_service).build_bulk_model(components)
        self._property_model = None
        self._set_bulk_mode(True)
        self._populate_bulk_fields(self._bulk_model)
        set_text(self.form["bulk_summary"], self._bulk_model["details"])
        self._set_widget_visible(self.form["selector_details"], False)
        self._set_widget_visible(self.form["selected_empty_state"], True)
        set_text(
            self.form["details"],
            "\n".join(
                [
                    f"Selected: {self._bulk_model['count']}",
                    f"Families: {', '.join(self._bulk_model['categories'])}",
                    "Only shared fields are shown.",
                ]
            ),
        )
        if notify and self.on_selection_changed is not None:
            self.on_selection_changed(component_ids[0] if component_ids else None)
        return components

    def update_selected_component(self) -> dict[str, Any]:
        if len(self.controller_service.get_selected_component_ids(self.doc)) > 1:
            return self.bulk_update_selected_components()
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        current = self.controller_service.get_component(self.doc, component_id)
        model = self._property_model or self.property_service.build_property_model(current)
        values = self._read_form_values(model)
        updates = self._changed_updates(model, values)
        if not updates:
            self._publish_status(f"No changes to apply for '{component_id}'.")
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
        self._publish_status(f"Changes applied to '{component_id}'.")
        if self.on_components_changed is not None:
            self.on_components_changed(state)
        return state

    def bulk_update_selected_components(self) -> dict[str, Any]:
        component_ids = self.controller_service.get_selected_component_ids(self.doc)
        if len(component_ids) < 2:
            raise ValueError("Bulk edit requires multiple selected components")
        service = ComponentBulkEditService(self.property_service, self.library_service)
        components = [self.controller_service.get_component(self.doc, component_id) for component_id in component_ids]
        model = self._bulk_model or service.build_bulk_model(components)
        apply_fields = self._bulk_apply_fields()
        values = self._bulk_values()
        updates_by_component = service.build_updates(model, values, apply_fields)
        if not updates_by_component:
            self._publish_status("No bulk changes selected. Enable at least one bulk field to apply.")
            return self.controller_service.get_state(self.doc)
        state = self.controller_service.bulk_update_components(self.doc, updates_by_component)
        self.refresh_components()
        self._publish_status(f"Applied bulk changes to {len(component_ids)} components.")
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
        self._publish_status(f"Added '{library_ref}'. Review its position and adjust as needed.")
        if self.on_components_changed is not None:
            self.on_components_changed(state)
        return state

    def arm_move_for_selected(self) -> dict[str, Any]:
        component_id = self.selected_component_id()
        if component_id is None:
            raise ValueError("No component selected")
        settings = self.interaction_service.arm_move(self.doc, component_id)
        self._publish_status(
            f"3D move is active for '{component_id}'. Click in the view to choose a new position, or edit X/Y here."
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
            self._publish_status(_friendly_component_error("Could not start 3D move", exc))

    def handle_snap_clicked(self) -> None:
        try:
            self.snap_selected_component()
        except Exception as exc:
            self._publish_status(_friendly_component_error("Could not snap component", exc))

    def handle_reset_clicked(self) -> None:
        try:
            if len(self.controller_service.get_selected_component_ids(self.doc)) > 1:
                self.load_bulk_selection(notify=False)
                self._publish_status("Bulk edit reset to the current selection.")
            else:
                self.load_selected_component(notify=False)
                self._publish_status("Component editor reset to the current state.")
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
        if hasattr(self.form["bulk_update_button"], "clicked"):
            self.form["bulk_update_button"].clicked.connect(self.handle_update_clicked)
        if hasattr(self.form["bulk_reset_button"], "clicked"):
            self.form["bulk_reset_button"].clicked.connect(self.handle_reset_clicked)
        if hasattr(self.form["add_button"], "clicked"):
            self.form["add_button"].clicked.connect(self.handle_add_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["component"], "Select the component to inspect or edit.")
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
        set_tooltip(self.form["bulk_update_button"], "Apply the checked bulk changes to all selected components.")
        set_tooltip(self.form["bulk_reset_button"], "Discard unsaved bulk edits and reload the current multi-selection.")

    def _configure_specific_editor(self) -> None:
        preset = self.form["specific_editor"].parts.get("preset")
        apply_button = self.form["specific_editor"].parts.get("apply_preset_button")
        summary = self.form["specific_editor"].parts.get("summary")
        if hasattr(preset, "hide"):
            preset.hide()
        if hasattr(apply_button, "hide"):
            apply_button.hide()
        set_text(summary, "Type-specific properties are generated from the selected library component.")
        self._set_bulk_mode(False)

    def _set_context_summary(self, *, component_count: int, selection_count: int) -> None:
        if component_count <= 0:
            message = "No components yet. Start with Quick Add."
        elif selection_count > 1:
            message = f"{selection_count} selected. Use the list to keep track and open Bulk Edit if needed."
        elif selection_count == 1:
            message = "Selected component ready. Adjust placement, metadata, and type-specific settings here."
        else:
            message = "Pick a component from the list to edit it, or use Quick Add to insert another one."
        set_text(self.form["context_summary"], message)

    def _set_bulk_mode(self, enabled: bool) -> None:
        self._set_widget_visible(self.form["selected_component_box"], not enabled)
        self._set_widget_visible(self.form["bulk_box"], enabled)

    def _populate_bulk_fields(self, model: dict[str, Any]) -> None:
        available = {field["id"]: field for field in model["fields"]}
        set_text(self.form["bulk_count"], f"Selected: {model['count']}")
        set_text(self.form["bulk_types"], f"Types: {', '.join(model['categories'])}")
        self._set_bulk_row("rotation", available)
        self._set_bulk_row("visible", available)
        self._set_bulk_row("library_ref", available)
        self._set_bulk_row("label_prefix", available)
        self._set_bulk_row("orientation", available)
        self._set_bulk_row("bezel", available)
        self._set_bulk_row("cap_width", available)

    def _set_bulk_row(self, field_id: str, available: dict[str, dict[str, Any]]) -> None:
        apply_widget = self.form[f"bulk_apply_{field_id}"]
        value_widget = self.form[f"bulk_{field_id}"]
        label_widget = self.form[f"bulk_label_{field_id}"]
        field = available.get(field_id)
        enabled = field is not None and bool(field.get("editable", True))
        self._set_widget_visible(label_widget, enabled)
        self._set_widget_visible(apply_widget, enabled)
        self._set_widget_visible(value_widget, enabled)
        set_enabled(apply_widget, enabled)
        set_enabled(value_widget, enabled)
        if hasattr(apply_widget, "setChecked"):
            apply_widget.setChecked(False)
        if not enabled:
            return
        label = str(field["label"])
        if field.get("mixed"):
            label = f"{label} (mixed)"
        set_text(label_widget, label)
        if field_id in {"rotation", "cap_width"}:
            set_value(value_widget, float(field.get("value", 0.0) or 0.0))
        elif field_id in {"visible", "bezel"} and hasattr(value_widget, "setChecked"):
            value_widget.setChecked(bool(field.get("value", False)))
        elif field_id in {"library_ref", "orientation"}:
            labels = [str(option["label"]) for option in field.get("options", [])]
            set_combo_items(value_widget, labels)
            current_value = str(field.get("value", ""))
            for option in field.get("options", []):
                if str(option["value"]) == current_value:
                    set_current_text(value_widget, str(option["label"]))
                    break
        elif field_id == "label_prefix":
            set_text(value_widget, "")

    def _bulk_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "rotation": widget_value(self.form["bulk_rotation"]),
            "visible": bool(self.form["bulk_visible"].isChecked()) if hasattr(self.form["bulk_visible"], "isChecked") else bool(getattr(self.form["bulk_visible"], "checked", True)),
            "label_prefix": text_value(self.form["bulk_label_prefix"]).strip(),
            "bezel": bool(self.form["bulk_bezel"].isChecked()) if hasattr(self.form["bulk_bezel"], "isChecked") else bool(getattr(self.form["bulk_bezel"], "checked", True)),
            "cap_width": widget_value(self.form["bulk_cap_width"]),
        }
        for field_id in ("library_ref", "orientation"):
            model_field = next((field for field in (self._bulk_model or {}).get("fields", []) if field["id"] == field_id), None)
            if model_field is None:
                continue
            label = current_text(self.form[f"bulk_{field_id}"])
            for option in model_field.get("options", []):
                if str(option["label"]) == label:
                    values[field_id] = option["value"]
                    break
        return values

    def _bulk_apply_fields(self) -> set[str]:
        field_ids = ["rotation", "visible", "library_ref", "label_prefix", "orientation", "bezel", "cap_width"]
        return {
            field_id
            for field_id in field_ids
            if hasattr(self.form[f"bulk_apply_{field_id}"], "isChecked")
            and self.form[f"bulk_apply_{field_id}"].isChecked()
        }

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
        self._bulk_model = None
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
        self._set_bulk_mode(False)
        self._set_widget_visible(self.form["selector_details"], False)
        self._set_widget_visible(self.form["selected_empty_state"], True)
        set_text(self.form["selected_empty_state"], "Select a component from the list to edit its placement and properties.")

    def _build_details_text(self, component: dict[str, Any], model: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"{component['id']} | {component['type']} | {component.get('library_ref', '-')}",
                f"Rotation {float(component.get('rotation', 0.0)):.2f} deg | Zone {component.get('zone_id') or '-'}",
                "Edit placement here. Re-run Validate after geometry changes.",
                model["details"],
            ]
        )

    def _set_widget_visible(self, widget: Any, visible: bool) -> None:
        if hasattr(widget, "setVisible"):
            widget.setVisible(visible)
            return
        try:
            widget.visible = bool(visible)
        except Exception:
            return


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    specific_editor = ParameterEditorWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "quick_add_section": FallbackLabel(),
            "selected_component_box": FallbackLabel(),
            "component_list_box": FallbackLabel(),
            "empty_state_box": FallbackLabel(),
            "bulk_section": FallbackLabel(),
            "selector_box": FallbackLabel(),
            "selector_details": FallbackLabel(),
            "quick_add_box": FallbackLabel(),
            "bulk_box": FallbackLabel(),
            "context_summary": FallbackText("No components yet. Start with Quick Add."),
            "component": FallbackCombo(),
            "selected_empty_state": FallbackLabel("Select a component from the list to edit its placement and properties."),
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
            "update_button": FallbackButton("Apply"),
            "arm_move_button": FallbackButton("Pick In 3D"),
            "snap_button": FallbackButton("Snap"),
            "reset_button": FallbackButton("Reset"),
            "bulk_count": FallbackLabel("Selected: 0"),
            "bulk_types": FallbackLabel("Types: -"),
            "bulk_summary": FallbackText(),
            "bulk_label_rotation": FallbackLabel("Rotation"),
            "bulk_apply_rotation": FallbackCheckBox(False),
            "bulk_rotation": FallbackValue(0.0),
            "bulk_label_visible": FallbackLabel("Visible"),
            "bulk_apply_visible": FallbackCheckBox(False),
            "bulk_visible": FallbackCheckBox(True),
            "bulk_label_library_ref": FallbackLabel("Variant"),
            "bulk_apply_library_ref": FallbackCheckBox(False),
            "bulk_library_ref": FallbackCombo(),
            "bulk_label_label_prefix": FallbackLabel("Label Prefix"),
            "bulk_apply_label_prefix": FallbackCheckBox(False),
            "bulk_label_prefix": FallbackText(),
            "bulk_label_orientation": FallbackLabel("Orientation"),
            "bulk_apply_orientation": FallbackCheckBox(False),
            "bulk_orientation": FallbackCombo(),
            "bulk_label_bezel": FallbackLabel("Bezel"),
            "bulk_apply_bezel": FallbackCheckBox(False),
            "bulk_bezel": FallbackCheckBox(True),
            "bulk_label_cap_width": FallbackLabel("Cap Width"),
            "bulk_apply_cap_width": FallbackCheckBox(False),
            "bulk_cap_width": FallbackValue(10.0),
            "bulk_update_button": FallbackButton("Apply Bulk Changes"),
            "bulk_reset_button": FallbackButton("Reset Bulk Changes"),
            "add_category": FallbackCombo(["all"]),
            "add_component": FallbackCombo(),
            "add_x": FallbackValue(10.0),
            "add_y": FallbackValue(10.0),
            "add_rotation": FallbackValue(0.0),
            "add_button": FallbackButton("Add"),
            "empty_state_cta": FallbackLabel("Add first component"),
            "details": FallbackText("No components yet. Use Quick Add to place the first one."),
            "status": FallbackLabel("Ready to add or edit components."),
        }

    content, layout = build_panel_container(qtwidgets)
    quick_add_section, quick_add_layout = create_form_section_widget(qtwidgets, "Quick Add", spacing=4)
    selected_component_box, selector_layout = create_form_section_widget(qtwidgets, "Selected Component", spacing=4)
    component_list_box, component_list_layout = create_form_section_widget(qtwidgets, "Components List", spacing=4)
    empty_state_box, empty_state_layout = create_section_widget(qtwidgets, "Components List", spacing=6)
    context_summary = create_status_label(qtwidgets, "No components yet. Start with Quick Add.")
    component = qtwidgets.QComboBox()
    configure_combo_box(component)
    list_hint = create_hint_label(qtwidgets, "Select a component from the list to edit it.")
    selected_id = qtwidgets.QLabel("ID: -")
    selected_type = qtwidgets.QLabel("Type: -")
    selected_library = qtwidgets.QLabel("Library: -")
    selector_details = create_compact_header_widget(
        qtwidgets,
        selected_id,
        secondary=create_status_label(qtwidgets, "Pick a component to inspect."),
        trailing=create_inline_status_widget(qtwidgets, selected_type, selected_library, spacing=8, stretch_index=1),
        spacing=8,
        detail_spacing=2,
    )
    x = qtwidgets.QDoubleSpinBox()
    y = qtwidgets.QDoubleSpinBox()
    rotation = qtwidgets.QDoubleSpinBox()
    library_ref = qtwidgets.QComboBox()
    label = qtwidgets.QLineEdit()
    tags = qtwidgets.QLineEdit()
    visible = qtwidgets.QCheckBox()
    visible.setChecked(True)
    update_button = set_button_role(qtwidgets.QPushButton("Apply"), "primary")
    arm_move_button = set_button_role(qtwidgets.QPushButton("Pick In 3D"), "secondary")
    snap_button = set_button_role(qtwidgets.QPushButton("Snap"), "ghost")
    reset_button = set_button_role(qtwidgets.QPushButton("Reset"), "ghost")
    configure_combo_box(library_ref)
    set_tooltip(component, "Select a component to inspect or edit.")
    set_tooltip(x, "Horizontal center position in millimeters.")
    set_tooltip(y, "Center Y position in millimeters.")
    set_tooltip(rotation, "Rotation in degrees.")
    set_tooltip(library_ref, "Choose a variant from the same library family.")
    set_tooltip(label, "Label used in exports and inspectors.")
    set_tooltip(tags, "Comma-separated tags for filtering or export workflows.")
    set_tooltip(visible, "Include this component as visible metadata.")
    set_tooltip(update_button, "Apply the current edits.")
    set_tooltip(arm_move_button, "Pick a new location directly in the 3D view.")
    set_tooltip(snap_button, "Snap the selected component to the grid.")
    set_tooltip(reset_button, "Discard unsaved edits.")
    for spinbox in (x, y, rotation):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    selector_summary = create_status_label(qtwidgets, "Edit only the selected component context.")
    selected_empty_state = create_hint_label(qtwidgets, "Select a component from the list to edit its placement and properties.")
    position_section, position_layout = create_form_section_widget(qtwidgets, "Position", spacing=4)
    meta_section, meta_layout = create_form_section_widget(qtwidgets, "Meta", spacing=4)
    type_specific_section, type_specific_layout = create_form_section_widget(qtwidgets, "Type-Specific", spacing=4)
    primary_actions = create_button_row_layout(qtwidgets, update_button, arm_move_button, spacing=6)
    secondary_actions = create_button_row_layout(qtwidgets, snap_button, reset_button, spacing=6)
    selector_layout.addRow("", selector_details)
    selector_layout.addRow("", selector_summary)
    selector_layout.addRow("", selected_empty_state)
    position_layout.addRow("X (mm)", x)
    position_layout.addRow("Y (mm)", y)
    position_layout.addRow("Rotation", rotation)
    position_layout.addRow("Variant", library_ref)
    meta_layout.addRow("Label", label)
    meta_layout.addRow("Tags", tags)
    meta_layout.addRow("Visible", visible)
    type_specific_layout.addRow("", specific_editor.widget)
    selector_layout.addRow("", position_section)
    selector_layout.addRow("", meta_section)
    selector_layout.addRow("", type_specific_section)
    selector_layout.addRow("", primary_actions)
    selector_layout.addRow("", secondary_actions)
    bulk_section, bulk_layout, _bulk_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Bulk Edit",
        expanded=False,
        spacing=6,
        margins=(0, 0, 0, 0),
    )
    bulk_box, bulk_form = create_form_section_widget(qtwidgets, "Selection Batch Tools", spacing=4)
    bulk_count = qtwidgets.QLabel("Selected: 0")
    bulk_types = qtwidgets.QLabel("Types: -")
    bulk_summary = create_status_label(qtwidgets, "Use for similar selected components.")
    bulk_label_rotation = qtwidgets.QLabel("Rotation")
    bulk_apply_rotation = qtwidgets.QCheckBox()
    bulk_rotation = qtwidgets.QDoubleSpinBox()
    bulk_label_visible = qtwidgets.QLabel("Visible")
    bulk_apply_visible = qtwidgets.QCheckBox()
    bulk_visible = qtwidgets.QCheckBox()
    bulk_visible.setChecked(True)
    bulk_label_library_ref = qtwidgets.QLabel("Variant")
    bulk_apply_library_ref = qtwidgets.QCheckBox()
    bulk_library_ref = qtwidgets.QComboBox()
    configure_combo_box(bulk_library_ref)
    bulk_label_label_prefix = qtwidgets.QLabel("Label Prefix")
    bulk_apply_label_prefix = qtwidgets.QCheckBox()
    bulk_label_prefix = qtwidgets.QLineEdit()
    bulk_label_orientation = qtwidgets.QLabel("Orientation")
    bulk_apply_orientation = qtwidgets.QCheckBox()
    bulk_orientation = qtwidgets.QComboBox()
    configure_combo_box(bulk_orientation)
    bulk_label_bezel = qtwidgets.QLabel("Bezel")
    bulk_apply_bezel = qtwidgets.QCheckBox()
    bulk_bezel = qtwidgets.QCheckBox()
    bulk_bezel.setChecked(True)
    bulk_label_cap_width = qtwidgets.QLabel("Cap Width")
    bulk_apply_cap_width = qtwidgets.QCheckBox()
    bulk_cap_width = qtwidgets.QDoubleSpinBox()
    for spinbox in (bulk_rotation, bulk_cap_width):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    bulk_update_button = set_button_role(qtwidgets.QPushButton("Apply Bulk Edit"), "primary")
    bulk_reset_button = set_button_role(qtwidgets.QPushButton("Reset Bulk Edit"), "ghost")
    bulk_actions = create_button_row_layout(qtwidgets, bulk_update_button, bulk_reset_button, spacing=6)
    bulk_form.addRow("", bulk_count)
    bulk_form.addRow("", bulk_types)
    bulk_form.addRow("", bulk_summary)
    bulk_form.addRow(bulk_label_rotation, _bulk_row_widget(qtwidgets, bulk_apply_rotation, bulk_rotation))
    bulk_form.addRow(bulk_label_visible, _bulk_row_widget(qtwidgets, bulk_apply_visible, bulk_visible))
    bulk_form.addRow(bulk_label_library_ref, _bulk_row_widget(qtwidgets, bulk_apply_library_ref, bulk_library_ref))
    bulk_form.addRow(bulk_label_label_prefix, _bulk_row_widget(qtwidgets, bulk_apply_label_prefix, bulk_label_prefix))
    bulk_form.addRow(bulk_label_orientation, _bulk_row_widget(qtwidgets, bulk_apply_orientation, bulk_orientation))
    bulk_form.addRow(bulk_label_bezel, _bulk_row_widget(qtwidgets, bulk_apply_bezel, bulk_bezel))
    bulk_form.addRow(bulk_label_cap_width, _bulk_row_widget(qtwidgets, bulk_apply_cap_width, bulk_cap_width))
    bulk_form.addRow("", bulk_actions)
    bulk_layout.addWidget(bulk_box)
    quick_add_hint = create_hint_label(qtwidgets, "Choose a category and library part, then add it to the controller.")
    add_box, add_layout = create_form_section_widget(qtwidgets, "Insert Component", spacing=4)
    add_category = qtwidgets.QComboBox()
    add_component = qtwidgets.QComboBox()
    configure_combo_box(add_category)
    configure_combo_box(add_component)
    add_x = qtwidgets.QDoubleSpinBox()
    add_y = qtwidgets.QDoubleSpinBox()
    add_rotation = qtwidgets.QDoubleSpinBox()
    add_button = set_button_role(qtwidgets.QPushButton("Add"), "primary")
    set_tooltip(add_category, "Filter the component library by category.")
    set_tooltip(add_component, "Choose a library part to add.")
    set_tooltip(add_x, "Initial X position.")
    set_tooltip(add_y, "Initial Y position.")
    set_tooltip(add_rotation, "Initial rotation.")
    set_tooltip(add_button, "Add the selected component.")
    for spinbox in (add_x, add_y, add_rotation):
        spinbox.setRange(-1000.0, 1000.0)
        spinbox.setDecimals(2)
        set_size_policy(spinbox, horizontal="expanding", vertical="preferred")
    add_x.setValue(10.0)
    add_y.setValue(10.0)
    add_layout.addRow("Category", add_category)
    add_layout.addRow("Library", add_component)
    placement_row = create_row_widget(qtwidgets, add_x, add_y, add_rotation, spacing=6)
    add_layout.addRow("Placement", placement_row)
    add_layout.addRow("", add_button)
    quick_add_layout.addRow(quick_add_hint)
    quick_add_layout.addRow(add_box)
    if hasattr(quick_add_section, "setObjectName"):
        quick_add_section.setObjectName("OCWQuickAddSection")
    empty_state = create_hint_label(
        qtwidgets,
        "No components placed yet. Start with Quick Add and place the first component into the controller.",
    )
    empty_state_cta = create_status_label(qtwidgets, "Add first component")
    empty_state_layout.addWidget(empty_state)
    empty_state_layout.addWidget(empty_state_cta)
    component_list_layout.addRow("", context_summary)
    component_list_layout.addRow("", list_hint)
    component_list_layout.addRow("Selection", component)
    details_box, details_layout = create_section_widget(qtwidgets, "Selection Details", spacing=6)
    details = create_text_panel(qtwidgets, max_height=72)
    details_layout.addWidget(details)
    status = create_status_label(qtwidgets, "Ready to add or edit components.")
    for child in (quick_add_section, selected_component_box, component_list_box, empty_state_box, bulk_box, bulk_section, add_box, component, add_category, add_component):
        set_size_policy(child, horizontal="expanding", vertical="preferred")
    layout.addWidget(quick_add_section)
    layout.addWidget(selected_component_box)
    layout.addWidget(component_list_box)
    layout.addWidget(empty_state_box)
    layout.addWidget(details_box)
    layout.addWidget(bulk_section)
    layout.addWidget(status)
    layout.addStretch(1)
    if hasattr(empty_state_box, "setVisible"):
        empty_state_box.setVisible(False)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "quick_add_section": quick_add_section,
        "selected_component_box": selected_component_box,
        "component_list_box": component_list_box,
        "empty_state_box": empty_state_box,
        "bulk_section": bulk_section,
        "selector_box": selected_component_box,
        "selector_details": selector_details,
        "quick_add_box": quick_add_section,
        "bulk_box": bulk_box,
        "context_summary": context_summary,
        "component": component,
        "selected_empty_state": selected_empty_state,
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
        "bulk_count": bulk_count,
        "bulk_types": bulk_types,
        "bulk_summary": bulk_summary,
        "bulk_label_rotation": bulk_label_rotation,
        "bulk_apply_rotation": bulk_apply_rotation,
        "bulk_rotation": bulk_rotation,
        "bulk_label_visible": bulk_label_visible,
        "bulk_apply_visible": bulk_apply_visible,
        "bulk_visible": bulk_visible,
        "bulk_label_library_ref": bulk_label_library_ref,
        "bulk_apply_library_ref": bulk_apply_library_ref,
        "bulk_library_ref": bulk_library_ref,
        "bulk_label_label_prefix": bulk_label_label_prefix,
        "bulk_apply_label_prefix": bulk_apply_label_prefix,
        "bulk_label_prefix": bulk_label_prefix,
        "bulk_label_orientation": bulk_label_orientation,
        "bulk_apply_orientation": bulk_apply_orientation,
        "bulk_orientation": bulk_orientation,
        "bulk_label_bezel": bulk_label_bezel,
        "bulk_apply_bezel": bulk_apply_bezel,
        "bulk_bezel": bulk_bezel,
        "bulk_label_cap_width": bulk_label_cap_width,
        "bulk_apply_cap_width": bulk_apply_cap_width,
        "bulk_cap_width": bulk_cap_width,
        "bulk_update_button": bulk_update_button,
        "bulk_reset_button": bulk_reset_button,
        "add_category": add_category,
        "add_component": add_component,
        "add_x": add_x,
        "add_y": add_y,
        "add_rotation": add_rotation,
        "add_button": add_button,
        "empty_state": empty_state,
        "empty_state_cta": empty_state_cta,
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


def _bulk_row_widget(qtwidgets: Any, apply_widget: Any, value_widget: Any) -> Any:
    return create_inline_status_widget(qtwidgets, apply_widget, value_widget, spacing=6, stretch_index=1)
