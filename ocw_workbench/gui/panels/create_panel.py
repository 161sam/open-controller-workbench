from __future__ import annotations

from collections import Counter
from typing import Any

from ocw_workbench.gui.panels._common import (
    configure_combo_box,
    configure_text_panel,
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    current_text,
    load_qt,
    set_combo_items,
    set_enabled,
    set_label_text,
    set_size_policy,
    set_text,
    text_value,
    wrap_widget_in_scroll_area,
)
from ocw_workbench.gui.widgets.favorites_list import FavoritesListWidget
from ocw_workbench.gui.widgets.preset_list import PresetListWidget
from ocw_workbench.gui.widgets.recent_list import RecentListWidget
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.template_marketplace_service import TemplateMarketplaceService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.userdata_service import UserDataService
from ocw_workbench.services.variant_service import VariantService


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
        self.refresh_preview()
        self.refresh_marketplace()
        self._sync_selected_context()
        self._sync_active_project(context)
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
            self._publish_status(result["warnings"][0])
        return result["entries"]

    def create_controller(self) -> dict[str, Any]:
        template_id = self.selected_template_id()
        if not template_id:
            raise ValueError("No template selected")
        variant_id = self.selected_variant_id()
        if variant_id:
            state = self.controller_service.create_from_variant(self.doc, variant_id)
            recent_name = f"{self.userdata_service.resolve_template_name(template_id)} / {self.userdata_service.resolve_variant_name(variant_id)}"
            self.userdata_service.record_recent(template_id=template_id, variant_id=variant_id, name=recent_name)
            self._publish_status(
                f"Created '{variant_id}'. The controller is ready to review below. "
                "Check Controller Settings, then fine-tune components if needed."
            )
        else:
            state = self.controller_service.create_from_template(self.doc, template_id)
            recent_name = self.userdata_service.resolve_template_name(template_id)
            self.userdata_service.record_recent(template_id=template_id, variant_id=None, name=recent_name)
            self._publish_status(
                f"Created '{template_id}'. The controller is ready to review below. "
                "Check Controller Settings, then fine-tune components if needed."
            )
        self.refresh()
        if self.on_created is not None:
            self.on_created(state)
        return state

    def toggle_template_favorite(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            raise ValueError("No template selected")
        template = self.template_service.get_template(template_id)["template"]
        favorites = self.userdata_service.toggle_favorite("template", template_id, name=str(template["name"]))
        status = "favorite" if any(entry.reference_id == template_id and entry.type == "template" for entry in favorites) else "not favorite"
        self.refresh()
        self._publish_status(f"Template '{template_id}' is now {status}.")

    def toggle_variant_favorite(self) -> None:
        variant_id = self.selected_variant_id()
        if variant_id is None:
            raise ValueError("No variant selected")
        variant = self.variant_service.get_variant(variant_id)["variant"]
        favorites = self.userdata_service.toggle_favorite("variant", variant_id, name=str(variant["name"]))
        status = "favorite" if any(entry.reference_id == variant_id and entry.type == "variant" for entry in favorites) else "not favorite"
        self.refresh()
        self._publish_status(f"Variant '{variant_id}' is now {status}.")

    def load_selected_favorite(self) -> None:
        entry = self.form["favorites_widget"].selected()
        if entry is None:
            raise ValueError("No favorite selected")
        self._apply_selection(template_id=entry["template_id"], variant_id=entry.get("variant_id"))
        self._publish_status("Loaded favorite selection.")

    def load_selected_recent(self) -> None:
        entry = self.form["recents_widget"].selected()
        if entry is None:
            raise ValueError("No recent entry selected")
        self._apply_selection(template_id=entry["template_id"], variant_id=entry.get("variant_id"))
        self._publish_status("Loaded recent selection.")

    def load_selected_preset(self) -> None:
        entry = self.form["presets_widget"].selected()
        if entry is None:
            raise ValueError("No preset selected")
        preset = self.userdata_service.get_preset(entry["preset_id"])
        self._apply_selection(template_id=preset.template_id, variant_id=preset.variant_id)
        self._publish_status(f"Loaded preset '{preset.name}'.")

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
        self.refresh()
        self._publish_status(f"Saved preset '{preset.name}'.")

    def selected_marketplace_entry(self) -> dict[str, Any] | None:
        return self._marketplace_lookup.get(current_text(self.form["marketplace_list"]))

    def apply_selected_marketplace_template(self) -> dict[str, Any]:
        entry = self.selected_marketplace_entry()
        if entry is None:
            raise ValueError("No marketplace template selected")
        result = self.template_marketplace_service.apply_entry(entry)
        self._apply_selection(template_id=result["template_id"], variant_id=None)
        self._publish_status(f"Applied marketplace template '{result['template_id']}'.")
        return result

    def show_selected_marketplace_details(self) -> str:
        entry = self.selected_marketplace_entry()
        if entry is None:
            raise ValueError("No marketplace template selected")
        details = self.template_marketplace_service.details_text(entry)
        set_text(self.form["marketplace_details"], details)
        self._publish_status(f"Showing details for '{entry['name']}'.")
        return details

    def handle_template_changed(self, *_args: Any) -> None:
        self.refresh_variants()
        self.refresh_preview()
        self._sync_selected_context()
        self._update_actions()

    def handle_variant_changed(self, *_args: Any) -> None:
        self.refresh_preview()
        self._set_variant_summary()
        self._update_actions()

    def handle_create_clicked(self) -> None:
        try:
            self.create_controller()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not create controller", exc))

    def handle_toggle_template_favorite(self) -> None:
        try:
            self.toggle_template_favorite()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_toggle_variant_favorite(self) -> None:
        try:
            self.toggle_variant_favorite()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_load_favorite(self) -> None:
        try:
            self.load_selected_favorite()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_load_recent(self) -> None:
        try:
            self.load_selected_recent()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_load_preset(self) -> None:
        try:
            self.load_selected_preset()
        except Exception as exc:
            self._publish_status(str(exc))

    def handle_save_preset(self) -> None:
        try:
            self.save_current_preset()
        except Exception as exc:
            self._publish_status(str(exc))

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
            self._publish_status(_friendly_create_error("Could not refresh marketplace", exc))

    def handle_marketplace_apply(self) -> None:
        try:
            self.apply_selected_marketplace_template()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not apply marketplace template", exc))

    def handle_marketplace_details(self) -> None:
        try:
            self.show_selected_marketplace_details()
        except Exception as exc:
            self._publish_status(_friendly_create_error("Could not load marketplace details", exc))

    def accept(self) -> bool:
        self.create_controller()
        return True

    def _build_preview(self) -> str:
        template_id = self.selected_template_id()
        if not template_id:
            return "Start by choosing a template to preview the controller."
        variant_id = self.selected_variant_id()
        if variant_id:
            project = self.variant_service.generate_from_variant(variant_id)
            title = f"Variant: {variant_id}"
        else:
            project = self.template_service.generate_from_template(template_id)
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
        self.refresh_preview()
        self._sync_selected_context()
        self._update_actions()

    def _sync_selected_context(self) -> None:
        template_id = self.selected_template_id()
        template = next((item["template"] for item in self._templates if item["template"]["id"] == template_id), None)
        if template is None:
            set_label_text(self.form["template_summary"], "Choose a template to begin a new controller.")
            set_label_text(self.form["favorite_template_status"], "Favorite: no template selected")
            return
        description = template.get("description") or "No template description available."
        is_favorite = self.userdata_service.is_favorite("template", template_id)
        set_label_text(self.form["template_summary"], f"{template['name']}: {description}")
        set_label_text(
            self.form["favorite_template_status"],
            f"Favorite: {'yes' if is_favorite else 'no'}",
        )

    def _sync_active_project(self, context: dict[str, Any]) -> None:
        layout = context.get("layout") or {}
        validation = context.get("validation") or {}
        validation_summary = validation.get("summary", {}) if isinstance(validation, dict) else {}
        if not context.get("template_id") and not context.get("variant_id") and context.get("component_count", 0) == 0:
            set_label_text(self.form["active_project"], "No controller in the document yet. Choose a template, then create a new controller.")
            return
        layout_text = layout.get("strategy", "not placed")
        validation_text = (
            f"{validation_summary.get('error_count', 0)} errors / {validation_summary.get('warning_count', 0)} warnings"
            if validation_summary
            else "validation not run"
        )
        set_label_text(
            self.form["active_project"],
            "Current document: "
            f"template {context.get('template_id') or '-'} | "
            f"variant {context.get('variant_id') or 'template default'} | "
            f"{context.get('component_count', 0)} components | "
            f"layout {layout_text} | "
            f"{validation_text}"
        )

    def _set_variant_summary(self) -> None:
        variant_id = self.selected_variant_id()
        if not variant_id:
            set_label_text(self.form["variant_summary"], "Template defaults are active.")
            set_label_text(self.form["favorite_variant_status"], "Favorite: n/a")
            return
        variant = next((item["variant"] for item in self._variants if item["variant"]["id"] == variant_id), None)
        if variant is None:
            set_label_text(self.form["variant_summary"], "The selected variant is not available.")
            set_label_text(self.form["favorite_variant_status"], "Favorite: unavailable")
            return
        description = variant.get("description") or "No variant description available."
        is_favorite = self.userdata_service.is_favorite("variant", variant_id)
        set_label_text(self.form["variant_summary"], f"{variant['name']}: {description}")
        set_label_text(
            self.form["favorite_variant_status"],
            f"Favorite: {'yes' if is_favorite else 'no'}",
        )

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
            set_label_text(self.form["marketplace_summary"], "No marketplace template selected.")
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
        set_enabled(self.form["create_button"], template_selected)
        set_enabled(self.form["favorite_template_button"], template_selected)
        set_enabled(self.form["favorite_variant_button"], variant_selected)
        set_enabled(self.form["presets_widget"].parts["save_button"], template_selected)
        if template_selected:
            template_id = self.selected_template_id()
            variant_id = self.selected_variant_id()
            if variant_id:
                set_label_text(self.form["create_button"], f"Create From Variant ({variant_id})")
            elif template_id:
                set_label_text(self.form["create_button"], f"Create From Template ({template_id})")
        else:
            set_label_text(self.form["create_button"], "Create New Controller")

    def _publish_status(self, message: str) -> None:
        set_label_text(self.form["status"], message)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        template = self.form["template"]
        variant = self.form["variant"]
        if hasattr(template, "currentIndexChanged"):
            template.currentIndexChanged.connect(self.handle_template_changed)
        if hasattr(variant, "currentIndexChanged"):
            variant.currentIndexChanged.connect(self.handle_variant_changed)
        if hasattr(self.form["create_button"], "clicked"):
            self.form["create_button"].clicked.connect(self.handle_create_clicked)
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
    if qtwidgets is None:
        return {
            "widget": object(),
            "favorites_widget": favorites_widget,
            "recents_widget": recents_widget,
            "presets_widget": presets_widget,
            "active_project": FallbackLabel("No controller in the document yet."),
            "marketplace_registry_url": FallbackText(""),
            "marketplace_search": FallbackText(""),
            "marketplace_filter": FallbackCombo(["all", "local", "remote"]),
            "marketplace_refresh_button": FallbackButton("Refresh Marketplace"),
            "marketplace_list": FallbackCombo(),
            "marketplace_summary": FallbackLabel("No marketplace template selected."),
            "marketplace_details": FallbackText("Use search or filters to inspect local and remote templates."),
            "marketplace_apply_button": FallbackButton("Apply Template"),
            "marketplace_details_button": FallbackButton("Show Details"),
            "template": FallbackCombo(),
            "template_summary": FallbackLabel(),
            "favorite_template_status": FallbackLabel(),
            "favorite_template_button": FallbackButton("Toggle Template Favorite"),
            "variant": FallbackCombo(["Template Default"]),
            "variant_summary": FallbackLabel("Template defaults are active."),
            "favorite_variant_status": FallbackLabel(),
            "favorite_variant_button": FallbackButton("Toggle Variant Favorite"),
            "preview": FallbackText(),
            "create_button": FallbackButton("Create New Controller"),
            "status": FallbackLabel(),
        }

    content = qtwidgets.QWidget()
    root = qtwidgets.QVBoxLayout(content)
    header = qtwidgets.QLabel("1. Choose a template. 2. Optionally choose a variant. 3. Create the controller and continue with setup below.")
    header.setWordWrap(True)
    active_project = qtwidgets.QLabel("No controller in the document yet. Choose a template, then create a new controller.")
    active_project.setWordWrap(True)
    shortcuts = qtwidgets.QVBoxLayout()
    shortcuts.addWidget(favorites_widget.widget)
    shortcuts.addWidget(recents_widget.widget)
    marketplace_box = qtwidgets.QGroupBox("Template Browser")
    marketplace_layout = qtwidgets.QVBoxLayout(marketplace_box)
    marketplace_controls = qtwidgets.QFormLayout()
    marketplace_registry_url = qtwidgets.QLineEdit()
    marketplace_refresh_button = qtwidgets.QPushButton("Refresh")
    marketplace_search = qtwidgets.QLineEdit()
    marketplace_filter = qtwidgets.QComboBox()
    marketplace_filter.addItems(["all", "local", "remote"])
    marketplace_list = qtwidgets.QComboBox()
    marketplace_summary = qtwidgets.QLabel("No marketplace template selected.")
    marketplace_summary.setWordWrap(True)
    marketplace_details = qtwidgets.QPlainTextEdit()
    configure_text_panel(marketplace_details, max_height=120)
    marketplace_actions = qtwidgets.QGridLayout()
    marketplace_apply_button = qtwidgets.QPushButton("Use Template")
    marketplace_details_button = qtwidgets.QPushButton("Show Details")
    marketplace_actions.addWidget(marketplace_refresh_button, 0, 0)
    marketplace_actions.addWidget(marketplace_apply_button, 0, 1)
    marketplace_actions.addWidget(marketplace_details_button, 1, 0, 1, 2)
    marketplace_controls.addRow("Registry", marketplace_registry_url)
    marketplace_controls.addRow("Search", marketplace_search)
    marketplace_controls.addRow("Filter", marketplace_filter)
    marketplace_layout.addLayout(marketplace_controls)
    marketplace_layout.addWidget(marketplace_list)
    marketplace_layout.addWidget(marketplace_summary)
    marketplace_layout.addWidget(marketplace_details)
    marketplace_layout.addLayout(marketplace_actions)
    form = qtwidgets.QFormLayout()
    template = qtwidgets.QComboBox()
    template_summary = qtwidgets.QLabel()
    template_summary.setWordWrap(True)
    favorite_template_status = qtwidgets.QLabel()
    favorite_template_status.setWordWrap(True)
    favorite_template_button = qtwidgets.QPushButton("Toggle Favorite")
    variant = qtwidgets.QComboBox()
    variant_summary = qtwidgets.QLabel()
    variant_summary.setWordWrap(True)
    favorite_variant_status = qtwidgets.QLabel()
    favorite_variant_status.setWordWrap(True)
    favorite_variant_button = qtwidgets.QPushButton("Toggle Favorite")
    preview = qtwidgets.QPlainTextEdit()
    configure_text_panel(preview, max_height=140)
    create_button = qtwidgets.QPushButton("Create New Controller")
    status = qtwidgets.QLabel()
    status.setWordWrap(True)
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
    for child in (
        favorites_widget.widget,
        recents_widget.widget,
        presets_widget.widget,
        marketplace_box,
        template,
        variant,
        create_button,
    ):
        set_size_policy(child, horizontal="expanding", vertical="preferred")
    form.addRow("Template", template)
    form.addRow("", template_summary)
    form.addRow("", favorite_template_status)
    form.addRow("", favorite_template_button)
    form.addRow("Variant", variant)
    form.addRow("", variant_summary)
    form.addRow("", favorite_variant_status)
    form.addRow("", favorite_variant_button)
    root.addWidget(header)
    root.addWidget(active_project)
    root.addLayout(shortcuts)
    root.addWidget(marketplace_box)
    root.addLayout(form)
    root.addWidget(preview)
    root.addWidget(presets_widget.widget)
    root.addWidget(create_button)
    root.addWidget(status)
    root.addStretch(1)
    widget = wrap_widget_in_scroll_area(content)
    return {
        "widget": widget,
        "favorites_widget": favorites_widget,
        "recents_widget": recents_widget,
        "presets_widget": presets_widget,
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
        "favorite_template_status": favorite_template_status,
        "favorite_template_button": favorite_template_button,
        "variant": variant,
        "variant_summary": variant_summary,
        "favorite_variant_status": favorite_variant_status,
        "favorite_variant_button": favorite_variant_button,
        "preview": preview,
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
