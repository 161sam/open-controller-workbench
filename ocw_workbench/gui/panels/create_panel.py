from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from ocw_workbench.gui.panels._common import (
    build_scroll_content_root,
    configure_combo_box,
    create_button_row_layout,
    create_collapsible_section_widget,
    create_form_layout,
    create_form_section_widget,
    create_hint_label,
    create_row_widget,
    create_status_label,
    create_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    current_text,
    load_qt,
    set_combo_items,
    set_enabled,
    set_label_text,
    set_button_role,
    set_size_policy,
    set_text,
    text_value,
    wrap_layout_in_widget,
    wrap_widget_in_scroll_area,
)
from ocw_workbench.gui.widgets.parameter_editor import ParameterEditorWidget
from ocw_workbench.gui.widgets.favorites_list import FavoritesListWidget
from ocw_workbench.gui.widgets.preset_list import PresetListWidget
from ocw_workbench.gui.widgets.recent_list import RecentListWidget
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.project_parameter_service import ProjectParameterService
from ocw_workbench.services.template_marketplace_service import TemplateMarketplaceService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.userdata_service import UserDataService
from ocw_workbench.services.variant_service import VariantService
from ocw_workbench.templates.parameters import TemplateParameterResolver


class CreatePanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        template_service: TemplateService | None = None,
        template_marketplace_service: TemplateMarketplaceService | None = None,
        variant_service: VariantService | None = None,
        userdata_service: UserDataService | None = None,
        on_created: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.template_service = template_service or TemplateService()
        self.variant_service = variant_service or VariantService()
        self.template_marketplace_service = template_marketplace_service or TemplateMarketplaceService(
            template_service=self.template_service
        )
        self.userdata_service = userdata_service or UserDataService(
            template_service=self.template_service,
            variant_service=self.variant_service,
            controller_service=self.controller_service,
        )
        self.on_created = on_created
        self.on_status = on_status
        self._templates: list[dict[str, Any]] = []
        self._variants: list[dict[str, Any]] = []
        self._template_lookup: dict[str, dict[str, Any]] = {}
        self._variant_lookup: dict[str, dict[str, Any]] = {}
        self._marketplace_entries: list[dict[str, Any]] = []
        self._marketplace_lookup: dict[str, dict[str, Any]] = {}
        self.parameter_resolver = TemplateParameterResolver()
        self.project_parameter_service = ProjectParameterService(
            template_service=self.template_service,
            variant_service=self.variant_service,
            parameter_resolver=self.parameter_resolver,
        )
        self._parameter_template: dict[str, Any] | None = None
        self._parameter_values: dict[str, Any] = {}
        self._parameter_sources: dict[str, str] = {}
        self._parameter_preset_id: str | None = None
        self._project_parameter_status: str = "unlinked"
        self.form = _build_form()
        self.widget = self.form["widget"]
        marketplace_url = self.template_marketplace_service.last_registry_url()
        if marketplace_url:
            set_text(self.form["marketplace_registry_url"], marketplace_url)
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        context = self.controller_service.get_ui_context(self.doc)
        active_template_id = context.get("template_id")
        active_variant_id = context.get("variant_id")
        previous_template = active_template_id or self.selected_template_id()
        previous_variant = active_variant_id or self.selected_variant_id()
        favorites = self.userdata_service.list_favorites()
        recents = self.userdata_service.list_recents()
        presets = self.userdata_service.list_presets()
        favorite_templates = {entry.reference_id for entry in favorites if entry.type == "template" and entry.reference_id}
        recent_templates = {entry.template_id for entry in recents}
        self._templates = self.template_service.list_templates()
        self._templates = sorted(
            self._templates,
            key=lambda item: (
                0 if item["template"]["id"] in favorite_templates else 1,
                0 if item["template"]["id"] in recent_templates else 1,
                str(item["template"]["name"]).lower(),
            ),
        )
        labels = [_template_label(item, favorite=item["template"]["id"] in favorite_templates) for item in self._templates]
        self._template_lookup = {label: item for label, item in zip(labels, self._templates)}
        set_combo_items(self.form["template"], labels)
        if previous_template:
            self._set_selected_template(previous_template)
        self.refresh_variants(active_variant_id=previous_variant)
        self._refresh_shortcuts()
        self.refresh_parameters()
        self.refresh_preview()
        self.refresh_marketplace()
        self._sync_selected_context()
        self._sync_active_project(context)
        self._sync_geometry_summary()
        self._update_actions()

    def refresh_variants(self, active_variant_id: str | None = None) -> None:
        template_id = self.selected_template_id()
        favorites = self.userdata_service.list_favorites()
        favorite_variants = {entry.reference_id for entry in favorites if entry.type == "variant" and entry.reference_id}
        self._variants = self.variant_service.list_variants(template_id=template_id) if template_id else []
        self._variants = sorted(
            self._variants,
            key=lambda item: (
                0 if item["variant"]["id"] in favorite_variants else 1,
                str(item["variant"]["name"]).lower(),
            ),
        )
        labels = ["Template Default"] + [
            _variant_label(item, favorite=item["variant"]["id"] in favorite_variants) for item in self._variants
        ]
        self._variant_lookup = {label: item for label, item in zip(labels[1:], self._variants)}
        set_combo_items(self.form["variant"], labels)
        if active_variant_id:
            self._set_selected_variant(active_variant_id)
        self._set_variant_summary()

    def selected_template_id(self) -> str | None:
        item = self._template_lookup.get(current_text(self.form["template"]))
        if item is None:
            return None
        return item["template"]["id"]

    def selected_variant_id(self) -> str | None:
        label = current_text(self.form["variant"])
        if label in {"", "Template Default"}:
            return None
        item = self._variant_lookup.get(label)
        if item is None:
            return None
        return item["variant"]["id"]

    def refresh_preview(self) -> str:
        preview = self._build_preview()
        set_text(self.form["preview"], preview)
        self._sync_geometry_summary()
        return preview

    def refresh_marketplace(self, refresh_remote: bool = False) -> list[dict[str, Any]]:
        registry_url = text_value(self.form["marketplace_registry_url"]).strip()
        search = text_value(self.form["marketplace_search"]).strip()
        filter_by = current_text(self.form["marketplace_filter"]) or "all"
        result = self.template_marketplace_service.list_entries(
            search=search,
            filter_by=filter_by,
            remote_registry_url=registry_url,
            refresh_remote=refresh_remote,
        )
        labels = [_marketplace_label(item) for item in result["entries"]]
        self._marketplace_entries = result["entries"]
        self._marketplace_lookup = {label: item for label, item in zip(labels, result["entries"])}
        set_combo_items(self.form["marketplace_list"], labels)
        if result["remote_url"] and result["remote_url"] != registry_url:
            set_text(self.form["marketplace_registry_url"], result["remote_url"])
        self._sync_marketplace_selection()
        if result["warnings"]:
            self._publish_status(result["warnings"][0], level="warning")
        return result["entries"]

    def create_controller(self) -> dict[str, Any]:
        template_id = self.selected_template_id()
        if not template_id:
            raise ValueError("No template selected")
        variant_id = self.selected_variant_id()
        runtime_overrides = self._runtime_overrides()
        if variant_id:
            state = self.controller_service.create_from_variant(self.doc, variant_id, overrides=runtime_overrides)
            recent_name = f"{self.userdata_service.resolve_template_name(template_id)} / {self.userdata_service.resolve_variant_name(variant_id)}"
            self.userdata_service.record_recent(template_id=template_id, variant_id=variant_id, name=recent_name)
            self._publish_status(f"Created '{variant_id}'. Review geometry, then refine the layout.", level="success")
        else:
            state = self.controller_service.create_from_template(self.doc, template_id, overrides=runtime_overrides)
            recent_name = self.userdata_service.resolve_template_name(template_id)
            self.userdata_service.record_recent(template_id=template_id, variant_id=None, name=recent_name)
            self._publish_status(f"Created '{template_id}'. Review geometry, then refine the layout.", level="success")
        self.refresh()
        if self.on_created is not None:
            self.on_created(state)
        return state

    def apply_parameters(self) -> dict[str, Any]:
        template_id = self.selected_template_id()
        if not template_id:
            raise ValueError("No template selected")
        state = self.controller_service.apply_template_parameters(
            self.doc,
            template_id=template_id,
            variant_id=self.selected_variant_id(),
            overrides=self._runtime_overrides(),
        )
        self.refresh()
        self._publish_status("Parameters applied.", level="success")
        return state

    def toggle_template_favorite(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            raise ValueError("No template selected")
        template = self.template_service.get_template(template_id)["template"]
        favorites = self.userdata_service.toggle_favorite("template", template_id, name=str(template["name"]))
        status = "saved to favorites" if any(entry.reference_id == template_id and entry.type == "template" for entry in favorites) else "removed from favorites"
        self.refresh()
        self._publish_status(f"Template '{template_id}' {status}.", level="success")

    def toggle_variant_favorite(self) -> None:
        variant_id = self.selected_variant_id()
        if variant_id is None:
            raise ValueError("No variant selected")
        variant = self.variant_service.get_variant(variant_id)["variant"]
        favorites = self.userdata_service.toggle_favorite("variant", variant_id, name=str(variant["name"]))
        status = "saved to favorites" if any(entry.reference_id == variant_id and entry.type == "variant" for entry in favorites) else "removed from favorites"
        self.refresh()
        self._publish_status(f"Variant '{variant_id}' {status}.", level="success")

    def load_selected_favorite(self) -> None:
        entry = self.form["favorites_widget"].selected()
        if entry is None:
            raise ValueError("No favorite selected")
        self._apply_selection(template_id=entry["template_id"], variant_id=entry.get("variant_id"))
        self._publish_status("Favorite loaded.", level="success")

    def load_selected_recent(self) -> None:
        entry = self.form["recents_widget"].selected()
        if entry is None:
            raise ValueError("No recent entry selected")
        self._apply_selection(template_id=entry["template_id"], variant_id=entry.get("variant_id"))
        self._publish_status("Recent item loaded.", level="success")

    def load_selected_preset(self) -> None:
        entry = self.form["presets_widget"].selected()
        if entry is None:
            raise ValueError("No preset selected")
        preset = self.userdata_service.get_preset(entry["preset_id"])
        self._apply_selection(template_id=preset.template_id, variant_id=preset.variant_id)
        overrides = preset.overrides if isinstance(preset.overrides, dict) else {}
        self._parameter_values = deepcopy(overrides.get("parameters", {})) if isinstance(overrides.get("parameters"), dict) else {}
        self._parameter_preset_id = str(overrides.get("parameter_preset_id")) if overrides.get("parameter_preset_id") else None
        self.refresh_parameters()
        self._publish_status(f"Preset '{preset.name}' loaded.", level="success")

    def save_current_preset(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            raise ValueError("Select a template before saving a preset")
        name = text_value(self.form["presets_widget"].parts["name"]).strip()
        if not name:
            raise ValueError("Preset name is required")
        preset = self.userdata_service.preset_from_document(
            self.doc,
            name=name,
            template_id=template_id,
            variant_id=self.selected_variant_id(),
        )
        self.userdata_service.save_preset(
            name=name,
            template_id=template_id,
            variant_id=self.selected_variant_id(),
            grid_mm=preset.grid_mm,
            layout_strategy=preset.layout_strategy,
            description=preset.description,
            overrides=self._runtime_overrides(),
        )
        self.refresh()
        self._publish_status(f"Preset '{preset.name}' saved.", level="success")

    def selected_marketplace_entry(self) -> dict[str, Any] | None:
        return self._marketplace_lookup.get(current_text(self.form["marketplace_list"]))

    def apply_selected_marketplace_template(self) -> dict[str, Any]:
        entry = self.selected_marketplace_entry()
        if entry is None:
            raise ValueError("No marketplace template selected")
        result = self.template_marketplace_service.apply_entry(entry)
        self._apply_selection(template_id=result["template_id"], variant_id=None)
        self._publish_status(f"Template '{result['template_id']}' applied.", level="success")
        return result

    def show_selected_marketplace_details(self) -> str:
        entry = self.selected_marketplace_entry()
        if entry is None:
            raise ValueError("No marketplace template selected")
        details = self.template_marketplace_service.details_text(entry)
        set_text(self.form["marketplace_details"], details)
        self._publish_status(f"Showing details for '{entry['name']}'.", level="info")
        return details

    def handle_template_changed(self, *_args: Any) -> None:
        self.refresh_variants()
        self.refresh_parameters()
        self.refresh_preview()
        self._sync_selected_context()
        self._update_actions()

    def handle_variant_changed(self, *_args: Any) -> None:
        self.refresh_parameters()
        self.refresh_preview()
        self._set_variant_summary()
        self._update_actions()

    def handle_create_clicked(self) -> None:
        try:
            self.create_controller()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not create controller", exc), level="error")

    def handle_toggle_template_favorite(self) -> None:
        try:
            self.toggle_template_favorite()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_toggle_variant_favorite(self) -> None:
        try:
            self.toggle_variant_favorite()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_load_favorite(self) -> None:
        try:
            self.load_selected_favorite()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_load_recent(self) -> None:
        try:
            self.load_selected_recent()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_load_preset(self) -> None:
        try:
            self.load_selected_preset()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_save_preset(self) -> None:
        try:
            self.save_current_preset()
        except Exception as exc:
            self._publish_status(str(exc), level="error")

    def handle_apply_parameters_clicked(self) -> None:
        try:
            self.apply_parameters()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not apply parameters", exc), level="error")

    def handle_parameter_widget_changed(self, *_args: Any) -> None:
        self._parameter_values = self.form["parameter_editor"].values()
        self._parameter_sources = {parameter_id: "user" for parameter_id in self._parameter_values}
        self._parameter_preset_id = self.form["parameter_editor"].selected_preset_id()
        self.refresh_preview()
        self._update_actions()

    def handle_apply_template_preset(self) -> None:
        self.form["parameter_editor"].apply_selected_preset()
        self._parameter_values = self.form["parameter_editor"].values()
        self._parameter_preset_id = self.form["parameter_editor"].selected_preset_id()
        self._parameter_sources = {
            parameter_id: ("preset" if self._parameter_preset_id is not None else "user")
            for parameter_id in self._parameter_values
        }
        self.refresh_preview()
        self._update_actions()
        self._publish_status("Preset applied.", level="success")

    def handle_marketplace_search_changed(self, *_args: Any) -> None:
        self.refresh_marketplace()

    def handle_marketplace_filter_changed(self, *_args: Any) -> None:
        self.refresh_marketplace()

    def handle_marketplace_selection_changed(self, *_args: Any) -> None:
        self._sync_marketplace_selection()

    def handle_marketplace_refresh(self) -> None:
        try:
            self.refresh_marketplace(refresh_remote=True)
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not refresh marketplace", exc), level="error")

    def handle_marketplace_apply(self) -> None:
        try:
            self.apply_selected_marketplace_template()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not apply marketplace template", exc), level="error")

    def handle_marketplace_details(self) -> None:
        try:
            self.show_selected_marketplace_details()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not load marketplace details", exc), level="error")

    def accept(self) -> bool:
        self.create_controller()
        return True

    def _build_preview(self) -> str:
        template_id = self.selected_template_id()
        if not template_id:
            return "Start by choosing a template to preview the controller."
        variant_id = self.selected_variant_id()
        runtime_overrides = self._runtime_overrides()
        if variant_id:
            project = self.variant_service.generate_from_variant(variant_id, overrides=runtime_overrides)
            title = f"Variant: {variant_id}"
        else:
            project = self.template_service.generate_from_template(template_id, overrides=runtime_overrides)
            title = f"Template: {template_id}"
        counts = Counter(component["type"] for component in project["components"])
        summary = ", ".join(f"{component_type} x{count}" for component_type, count in sorted(counts.items()))
        controller = project["controller"]
        surface = controller.get("surface") or {}
        shape = surface.get("shape") or surface.get("type") or "rectangle"
        width = surface.get("width", controller.get("width", "-"))
        height = surface.get("height", controller.get("depth", "-"))
        return "\n".join(
            [
                title,
                f"Surface: {shape} {width} x {height} mm",
                f"Components: {len(project['components'])}",
                f"Types: {summary or 'none'}",
                _parameter_preview_line(project.get("parameters")),
                _layout_preview_line(project.get("layout")),
            ]
        )

    def _set_selected_template(self, template_id: str) -> None:
        for index, item in enumerate(self._templates):
            if item["template"]["id"] == template_id:
                self.form["template"].setCurrentIndex(index)
                return

    def _set_selected_variant(self, variant_id: str) -> None:
        for index, item in enumerate(self._variants, start=1):
            if item["variant"]["id"] == variant_id:
                self.form["variant"].setCurrentIndex(index)
                return
        self.form["variant"].setCurrentIndex(0)

    def _apply_selection(self, template_id: str | None, variant_id: str | None) -> None:
        if template_id:
            self._set_selected_template(template_id)
        self.refresh_variants(active_variant_id=variant_id)
        self.refresh_parameters()
        self.refresh_preview()
        self._sync_selected_context()
        self._update_actions()

    def refresh_parameters(self) -> None:
        context = self.controller_service.get_ui_context(self.doc)
        project_parameter_model = self.project_parameter_service.inspect_project_parameters(context)
        self._project_parameter_status = project_parameter_model["status"]
        set_label_text(self.form["parameter_status"], project_parameter_model["message"])
        template_id = self.selected_template_id()
        if template_id is None:
            self._parameter_template = None
            self._parameter_values = {}
            self._parameter_sources = {}
            self._parameter_preset_id = None
            self.form["parameter_editor"].clear()
            self._sync_geometry_summary()
            return
        variant_id = self.selected_variant_id()
        active_project_matches_selection = (
            context.get("template_id") == template_id
            and context.get("variant_id") == variant_id
        )
        if active_project_matches_selection and project_parameter_model["reparameterizable"]:
            self._parameter_template = project_parameter_model["template"]
            ui_model = project_parameter_model["ui_model"]
            assert ui_model is not None
        else:
            template = self.variant_service.resolve_variant(variant_id) if variant_id else self.template_service.resolve_template(template_id)
            self._parameter_template = template
            seeded_values = deepcopy(self._parameter_values)
            seeded_preset_id = self._parameter_preset_id
            try:
                ui_model = self.parameter_resolver.build_ui_model(template, values=seeded_values, preset_id=seeded_preset_id)
            except KeyError:
                ui_model = self.parameter_resolver.build_ui_model(template, values=seeded_values, preset_id=None)
        try:
            self._parameter_values = deepcopy(ui_model["values"])
        except KeyError:
            self._parameter_values = {}
        self._parameter_sources = deepcopy(ui_model["sources"])
        self._parameter_preset_id = ui_model["preset_id"]
        self.form["parameter_editor"].set_schema(
            ui_model["definitions"],
            ui_model["presets"],
            ui_model["values"],
            sources=ui_model["sources"],
            preset_id=ui_model["preset_id"],
        )
        self._sync_geometry_summary()

    def _runtime_overrides(self) -> dict[str, Any]:
        if self._parameter_template is None:
            return {}
        return {
            "parameters": deepcopy(self._parameter_values),
            "parameter_preset_id": self._parameter_preset_id,
        }

    def _sync_selected_context(self) -> None:
        template_id = self.selected_template_id()
        template = next((item["template"] for item in self._templates if item["template"]["id"] == template_id), None)
        if template is None:
            set_label_text(self.form["template_summary"], "Choose a template to load its default controller setup.")
            return
        description = template.get("description") or "No template description available."
        summary = description if len(description) <= 88 else f"{description[:85].rstrip()}..."
        set_label_text(self.form["template_summary"], summary)

    def _sync_active_project(self, context: dict[str, Any]) -> None:
        project_parameter_model = self.project_parameter_service.inspect_project_parameters(context)
        layout = context.get("layout") or {}
        validation = context.get("validation") or {}
        validation_summary = validation.get("summary", {}) if isinstance(validation, dict) else {}
        if not context.get("template_id") and not context.get("variant_id") and context.get("component_count", 0) == 0:
            set_label_text(self.form["active_project"], "No controller loaded yet. Choose a template, review geometry, then create the controller.")
            return
        layout_text = layout.get("strategy", "not placed")
        validation_text = (
            f"{validation_summary.get('error_count', 0)} errors / {validation_summary.get('warning_count', 0)} warnings"
            if validation_summary
            else "validation not run"
        )
        set_label_text(
            self.form["active_project"],
            "Current document | "
            f"template {context.get('template_id') or '-'} | "
            f"variant {context.get('variant_id') or 'template default'} | "
            f"{context.get('component_count', 0)} components | "
            f"layout {layout_text} | "
            f"{validation_text} | "
            f"parameters {project_parameter_model['status']}"
        )

    def _set_variant_summary(self) -> None:
        variant_id = self.selected_variant_id()
        if not variant_id:
            set_label_text(self.form["variant_summary"], "Use the base template defaults.")
            return
        variant = next((item["variant"] for item in self._variants if item["variant"]["id"] == variant_id), None)
        if variant is None:
            set_label_text(self.form["variant_summary"], "The selected variant is not available.")
            return
        description = variant.get("description") or "No variant description available."
        summary = description if len(description) <= 76 else f"{description[:73].rstrip()}..."
        set_label_text(self.form["variant_summary"], summary)

    def _sync_geometry_summary(self) -> None:
        label = self.form.get("geometry_summary")
        if label is None:
            return
        template_id = self.selected_template_id()
        if template_id is None:
            set_label_text(
                label,
                "Geometry follows the selected template. Width, depth, height, and construction settings appear here after selection.",
            )
            return
        variant_id = self.selected_variant_id()
        runtime_overrides = self._runtime_overrides()
        if variant_id:
            project = self.variant_service.generate_from_variant(variant_id, overrides=runtime_overrides)
        else:
            project = self.template_service.generate_from_template(template_id, overrides=runtime_overrides)
        controller = project.get("controller", {})
        surface = controller.get("surface") or {}
        width = surface.get("width", controller.get("width", "-"))
        depth = surface.get("height", controller.get("depth", "-"))
        height = controller.get("height", "-")
        geometry_fields = self._geometry_parameter_labels()
        geometry_hint = ", ".join(geometry_fields[:4]) if geometry_fields else "template defaults"
        set_label_text(
            label,
            f"Width {width} mm | Depth {depth} mm | Height {height} mm | Controls: {geometry_hint}",
        )

    def _geometry_parameter_labels(self) -> list[str]:
        if self._parameter_template is None:
            return []
        labels: list[str] = []
        for definition in self.parameter_resolver.normalize_definitions(self._parameter_template):
            parameter_id = str(definition.get("id") or "").lower()
            label = str(definition.get("label") or parameter_id).strip()
            if any(token in parameter_id for token in ("width", "depth", "height", "wall", "bottom", "top")):
                labels.append(label)
        return labels

    def _refresh_shortcuts(self) -> None:
        favorites = []
        for entry in self.userdata_service.list_favorites():
            if entry.type == "template" and entry.reference_id:
                favorites.append(
                    {
                        "label": f"Template: {entry.name or entry.reference_id}",
                        "template_id": entry.reference_id,
                        "variant_id": None,
                    }
                )
            elif entry.type == "variant" and entry.reference_id:
                try:
                    variant = self.variant_service.get_variant(entry.reference_id)["variant"]
                    favorites.append(
                        {
                            "label": f"Variant: {entry.name or entry.reference_id}",
                            "template_id": str(variant["template_id"]),
                            "variant_id": entry.reference_id,
                        }
                    )
                except Exception:
                    continue
        recents = [
            {
                "label": entry.name or entry.id,
                "template_id": entry.template_id,
                "variant_id": entry.variant_id,
            }
            for entry in self.userdata_service.list_recents()
        ]
        presets = [
            {
                "label": entry.name,
                "preset_id": entry.id,
            }
            for entry in self.userdata_service.list_presets()
        ]
        self.form["favorites_widget"].set_entries(favorites)
        self.form["recents_widget"].set_entries(recents)
        self.form["presets_widget"].set_entries(presets)

    def _sync_marketplace_selection(self) -> None:
        entry = self.selected_marketplace_entry()
        if entry is None:
            set_label_text(self.form["marketplace_summary"], "No template selected.")
            set_text(self.form["marketplace_details"], "Browse local and remote templates to compare options before you create.")
            set_enabled(self.form["marketplace_apply_button"], False)
            set_enabled(self.form["marketplace_details_button"], False)
            return
        set_label_text(
            self.form["marketplace_summary"],
            f"{entry['name']} | {entry['component_count']} components | {entry.get('plugin_name') or entry.get('plugin_id') or '-'}",
        )
        set_text(self.form["marketplace_details"], self.template_marketplace_service.details_text(entry))
        set_enabled(self.form["marketplace_apply_button"], self.template_marketplace_service.can_apply(entry))
        set_enabled(self.form["marketplace_details_button"], True)

    def _update_actions(self) -> None:
        template_selected = self.selected_template_id() is not None
        variant_selected = self.selected_variant_id() is not None
        context = self.controller_service.get_ui_context(self.doc)
        active_project_matches_selection = (
            template_selected
            and context.get("template_id") == self.selected_template_id()
            and context.get("variant_id") == self.selected_variant_id()
        )
        project_parameter_model = self.project_parameter_service.inspect_project_parameters(context)
        set_enabled(self.form["create_button"], template_selected)
        set_enabled(
            self.form["apply_parameters_button"],
            bool(active_project_matches_selection and project_parameter_model["reparameterizable"]),
        )
        set_enabled(self.form["favorite_template_button"], template_selected)
        set_enabled(self.form["favorite_variant_button"], variant_selected)
        set_enabled(self.form["presets_widget"].parts["save_button"], template_selected)
        set_label_text(self.form["create_button"], "Create Controller")
        set_label_text(self.form["apply_parameters_button"], "Apply Geometry")

    def _publish_status(self, message: str, level: str = "info") -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message, level)

    def _connect_events(self) -> None:
        template = self.form["template"]
        variant = self.form["variant"]
        if hasattr(template, "currentIndexChanged"):
            template.currentIndexChanged.connect(self.handle_template_changed)
        if hasattr(variant, "currentIndexChanged"):
            variant.currentIndexChanged.connect(self.handle_variant_changed)
        if hasattr(self.form["create_button"], "clicked"):
            self.form["create_button"].clicked.connect(self.handle_create_clicked)
        if hasattr(self.form["apply_parameters_button"], "clicked"):
            self.form["apply_parameters_button"].clicked.connect(self.handle_apply_parameters_clicked)
        if hasattr(self.form["favorite_template_button"], "clicked"):
            self.form["favorite_template_button"].clicked.connect(self.handle_toggle_template_favorite)
        if hasattr(self.form["favorite_variant_button"], "clicked"):
            self.form["favorite_variant_button"].clicked.connect(self.handle_toggle_variant_favorite)
        if hasattr(self.form["favorites_widget"].parts["apply_button"], "clicked"):
            self.form["favorites_widget"].parts["apply_button"].clicked.connect(self.handle_load_favorite)
        if hasattr(self.form["recents_widget"].parts["apply_button"], "clicked"):
            self.form["recents_widget"].parts["apply_button"].clicked.connect(self.handle_load_recent)
        if hasattr(self.form["presets_widget"].parts["load_button"], "clicked"):
            self.form["presets_widget"].parts["load_button"].clicked.connect(self.handle_load_preset)
        if hasattr(self.form["presets_widget"].parts["save_button"], "clicked"):
            self.form["presets_widget"].parts["save_button"].clicked.connect(self.handle_save_preset)
        self.form["parameter_editor"].changed.connect(self.handle_parameter_widget_changed)
        if hasattr(self.form["parameter_editor"].parts["apply_preset_button"], "clicked"):
            self.form["parameter_editor"].parts["apply_preset_button"].clicked.connect(self.handle_apply_template_preset)
        if hasattr(self.form["marketplace_filter"], "currentIndexChanged"):
            self.form["marketplace_filter"].currentIndexChanged.connect(self.handle_marketplace_filter_changed)
        if hasattr(self.form["marketplace_list"], "currentIndexChanged"):
            self.form["marketplace_list"].currentIndexChanged.connect(self.handle_marketplace_selection_changed)
        if hasattr(self.form["marketplace_refresh_button"], "clicked"):
            self.form["marketplace_refresh_button"].clicked.connect(self.handle_marketplace_refresh)
        if hasattr(self.form["marketplace_apply_button"], "clicked"):
            self.form["marketplace_apply_button"].clicked.connect(self.handle_marketplace_apply)
        if hasattr(self.form["marketplace_details_button"], "clicked"):
            self.form["marketplace_details_button"].clicked.connect(self.handle_marketplace_details)
        search_widget = self.form["marketplace_search"]
        if hasattr(search_widget, "textChanged"):
            search_widget.textChanged.connect(self.handle_marketplace_search_changed)


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    favorites_widget = FavoritesListWidget()
    recents_widget = RecentListWidget()
    presets_widget = PresetListWidget()
    parameter_editor = ParameterEditorWidget()
    if qtwidgets is None:
        return {
            "widget": object(),
            "header": FallbackLabel("Select a template, then create the controller."),
            "template_section": object(),
            "geometry_section": object(),
            "action_section": object(),
            "quick_access_section": object(),
            "library_section": object(),
            "document_actions_section": object(),
            "presets_section": object(),
            "favorites_widget": favorites_widget,
            "recents_widget": recents_widget,
            "presets_widget": presets_widget,
            "parameter_editor": parameter_editor,
            "active_project": FallbackLabel("No controller loaded yet. Choose a template, review geometry, then create the controller."),
            "marketplace_registry_url": FallbackText(""),
            "marketplace_search": FallbackText(""),
            "marketplace_filter": FallbackCombo(["all", "local", "remote"]),
            "marketplace_refresh_button": FallbackButton("Reload"),
            "marketplace_list": FallbackCombo(),
            "marketplace_summary": FallbackLabel("No marketplace template selected."),
            "marketplace_details": FallbackText("Use search or filters to inspect local and remote templates."),
            "marketplace_apply_button": FallbackButton("Use"),
            "marketplace_details_button": FallbackButton("Details"),
            "template": FallbackCombo(),
            "template_summary": FallbackLabel("Choose a template to load its default controller setup."),
            "favorite_template_button": FallbackButton("Favorite"),
            "variant": FallbackCombo(["Template Default"]),
            "variant_summary": FallbackLabel("Use the base template defaults."),
            "favorite_variant_button": FallbackButton("Favorite"),
            "geometry_summary": FallbackLabel("Geometry follows the selected template. Width, depth, height, and construction settings appear here after selection."),
            "parameter_status": FallbackLabel("Choose a template to unlock geometry controls."),
            "preview": FallbackText("Controller summary will appear here once a template is selected."),
            "apply_parameters_button": FallbackButton("Apply Geometry"),
            "create_button": FallbackButton("Create Controller"),
            "status": FallbackLabel("Ready to create a new controller."),
        }

    content, root = build_scroll_content_root(qtwidgets)
    header = create_hint_label(qtwidgets, "Select a template, then create the controller.")
    active_project = create_status_label(qtwidgets, "No controller loaded yet. Choose a template, review geometry, then create the controller.")
    template_section, template_layout = create_form_section_widget(qtwidgets, "Template Selection")
    geometry_section, geometry_layout, _geometry_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Geometry",
        expanded=False,
        spacing=4,
        margins=(0, 0, 0, 0),
    )
    action_section, action_layout = create_form_section_widget(qtwidgets, "Primary Action")
    library_section, marketplace_layout, _library_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Template Library",
        expanded=False,
        spacing=6,
        margins=(8, 8, 8, 8),
    )
    marketplace_controls = create_form_layout(qtwidgets, spacing=4)
    marketplace_registry_url = qtwidgets.QLineEdit()
    marketplace_refresh_button = qtwidgets.QPushButton("Reload")
    marketplace_search = qtwidgets.QLineEdit()
    marketplace_filter = qtwidgets.QComboBox()
    marketplace_filter.addItems(["all", "local", "remote"])
    marketplace_list = qtwidgets.QComboBox()
    marketplace_summary = create_status_label(qtwidgets, "No template selected.")
    marketplace_details = create_text_panel(qtwidgets, max_height=54)
    marketplace_apply_button = qtwidgets.QPushButton("Use")
    marketplace_details_button = qtwidgets.QPushButton("Details")
    marketplace_actions = create_button_row_layout(
        qtwidgets,
        set_button_role(marketplace_refresh_button, "ghost"),
        set_button_role(marketplace_apply_button, "primary"),
        marketplace_details_button,
        spacing=6,
    )
    marketplace_controls.addRow("Registry", marketplace_registry_url)
    marketplace_controls.addRow("Search", marketplace_search)
    marketplace_controls.addRow("Filter", marketplace_filter)
    marketplace_layout.addLayout(marketplace_controls)
    marketplace_layout.addWidget(marketplace_list)
    marketplace_layout.addWidget(marketplace_summary)
    marketplace_layout.addWidget(marketplace_details)
    marketplace_layout.addLayout(marketplace_actions)
    selection_form = create_form_layout(qtwidgets, spacing=4)
    template = qtwidgets.QComboBox()
    template_summary = create_status_label(qtwidgets)
    favorite_template_button = set_button_role(qtwidgets.QPushButton("Favorite"), "ghost")
    variant = qtwidgets.QComboBox()
    variant_summary = create_status_label(qtwidgets)
    favorite_variant_button = set_button_role(qtwidgets.QPushButton("Favorite"), "ghost")
    geometry_summary = create_status_label(
        qtwidgets,
        "Geometry follows the selected template. Width, depth, height, and construction settings appear here after selection.",
    )
    parameter_status = create_status_label(qtwidgets, "Choose a template to unlock geometry controls.")
    preview = create_text_panel(qtwidgets, max_height=48)
    set_text(preview, "Controller summary will appear here once a template is selected.")
    apply_parameters_button = set_button_role(qtwidgets.QPushButton("Apply Geometry"), "ghost")
    create_button = set_button_role(qtwidgets.QPushButton("Create Controller"), "primary")
    status = create_status_label(qtwidgets, "Ready to create a new controller.")
    for combo in (
        favorites_widget.parts["combo"],
        recents_widget.parts["combo"],
        presets_widget.parts["combo"],
        marketplace_filter,
        marketplace_list,
        template,
        variant,
    ):
        configure_combo_box(combo)
    quick_access_section, quick_access_layout, _quick_access_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Quick Access",
        expanded=False,
        spacing=4,
        margins=(0, 0, 0, 0),
    )
    shortcuts_row = qtwidgets.QHBoxLayout()
    shortcuts_row.setSpacing(6)
    shortcuts_row.addWidget(favorites_widget.widget, 1)
    shortcuts_row.addWidget(recents_widget.widget, 1)
    quick_access_layout.addLayout(shortcuts_row)

    template_fav_row = create_row_widget(qtwidgets, template, favorite_template_button, stretch_index=0)
    variant_fav_row = create_row_widget(qtwidgets, variant, favorite_variant_button, stretch_index=0)
    for child in (
        favorites_widget.widget,
        recents_widget.widget,
        presets_widget.widget,
        parameter_editor.widget,
        library_section,
        quick_access_section,
        template_section,
        geometry_section,
        action_section,
        template_fav_row,
        variant_fav_row,
        apply_parameters_button,
        create_button,
    ):
        set_size_policy(child, horizontal="expanding", vertical="preferred")
    selection_form.addRow("Template", template_fav_row)
    selection_form.addRow(template_summary)
    selection_form.addRow("Variant", variant_fav_row)
    selection_form.addRow(variant_summary)
    template_layout.addRow(wrap_layout_in_widget(qtwidgets, selection_form))
    template_layout.addRow(quick_access_section)
    template_layout.addRow(library_section)

    presets_section, presets_layout, _presets_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Presets",
        expanded=False,
        spacing=4,
        margins=(0, 0, 0, 0),
    )
    document_actions_section, document_actions_layout, _document_actions_toggle = create_collapsible_section_widget(
        qtwidgets,
        "Current Document",
        expanded=False,
        spacing=4,
        margins=(0, 0, 0, 0),
    )
    presets_layout.addWidget(presets_widget.widget)
    geometry_layout.addWidget(geometry_summary)
    geometry_layout.addWidget(parameter_status)
    geometry_layout.addWidget(parameter_editor.widget)
    geometry_layout.addWidget(presets_section)

    create_only_row = create_button_row_layout(qtwidgets, create_button)
    document_actions_layout.addWidget(preview)
    document_actions_layout.addWidget(apply_parameters_button)
    document_actions_layout.addWidget(status)
    action_layout.addRow(active_project)
    action_layout.addRow(wrap_layout_in_widget(qtwidgets, create_only_row))
    action_layout.addRow(document_actions_section)

    root.addWidget(header)
    root.addWidget(template_section)
    root.addWidget(geometry_section)
    root.addWidget(action_section)
    root.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "header": header,
        "template_section": template_section,
        "geometry_section": geometry_section,
        "action_section": action_section,
        "quick_access_section": quick_access_section,
        "library_section": library_section,
        "document_actions_section": document_actions_section,
        "presets_section": presets_section,
        "favorites_widget": favorites_widget,
        "recents_widget": recents_widget,
        "presets_widget": presets_widget,
        "parameter_editor": parameter_editor,
        "active_project": active_project,
        "marketplace_registry_url": marketplace_registry_url,
        "marketplace_search": marketplace_search,
        "marketplace_filter": marketplace_filter,
        "marketplace_refresh_button": marketplace_refresh_button,
        "marketplace_list": marketplace_list,
        "marketplace_summary": marketplace_summary,
        "marketplace_details": marketplace_details,
        "marketplace_apply_button": marketplace_apply_button,
        "marketplace_details_button": marketplace_details_button,
        "template": template,
        "template_summary": template_summary,
        "favorite_template_button": favorite_template_button,
        "variant": variant,
        "variant_summary": variant_summary,
        "favorite_variant_button": favorite_variant_button,
        "geometry_summary": geometry_summary,
        "parameter_status": parameter_status,
        "preview": preview,
        "apply_parameters_button": apply_parameters_button,
        "create_button": create_button,
        "status": status,
    }


def _template_label(item: dict[str, Any], favorite: bool = False) -> str:
    template = item["template"]
    prefix = "★ " if favorite else ""
    return f"{prefix}{template['name']} ({template['id']})"


def _variant_label(item: dict[str, Any], favorite: bool = False) -> str:
    variant = item["variant"]
    prefix = "★ " if favorite else ""
    return f"{prefix}{variant['name']} ({variant['id']})"


def _marketplace_label(item: dict[str, Any]) -> str:
    source = "remote" if item.get("source") == "remote" else "local"
    return f"[{source}] {item['name']} ({item.get('template_id') or item['entry_id']})"


def _layout_preview_line(layout: dict[str, Any] | None) -> str:
    if not isinstance(layout, dict) or not layout:
        return "Layout: template default"
    strategy = layout.get("strategy") or "template default"
    config = layout.get("config") or {}
    spacing = config.get("spacing_mm", config.get("spacing_x_mm", "-"))
    padding = config.get("padding_mm", "-")
    return f"Layout: {strategy} | spacing {spacing} mm | padding {padding} mm"


def _parameter_preview_line(parameters: dict[str, Any] | None) -> str:
    if not isinstance(parameters, dict):
        return "Parameters: template default"
    values = parameters.get("values") or {}
    if not isinstance(values, dict) or not values:
        return "Parameters: template default"
    summary = ", ".join(f"{key}={value}" for key, value in sorted(values.items()))
    preset_id = parameters.get("preset_id")
    if preset_id:
        return f"Parameters: {summary} | preset {preset_id}"
    return f"Parameters: {summary}"


def _friendly_create_error(prefix: str, exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "no template selected" in lowered:
        return f"{prefix}. Choose a template first."
    if "variant" in lowered and "no variant selected" in lowered:
        return f"{prefix}. Choose a variant or switch back to Template Default."
    if "registry" in lowered or "marketplace" in lowered:
        return f"{prefix}. Check the registry URL or filter settings, then try again."
    if "shape" in lowered or "cutout" in lowered or "part::" in lowered:
        return f"{prefix}. The template data produced invalid geometry. Try the template default or review the controller settings after creation."
    return f"{prefix}. {message}"
