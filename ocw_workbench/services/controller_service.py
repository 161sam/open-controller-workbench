from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.freecad_api import gui as freecad_gui
from ocw_workbench.freecad_api.document import document_transaction
from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.layout.engine import LayoutEngine
from ocw_workbench.services.constraint_service import ConstraintService
from ocw_workbench.services.controller_state_service import (
    DEFAULT_CONTROLLER,
    DEFAULT_META,
    ControllerStateService,
)
from ocw_workbench.services.document_sync_service import DocumentSyncService, SyncMode
from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.variant_service import VariantService


class ControllerService:
    def __init__(
        self,
        library_service: LibraryService | None = None,
        template_service: TemplateService | None = None,
        variant_service: VariantService | None = None,
        layout_engine: LayoutEngine | None = None,
        constraint_service: ConstraintService | None = None,
        state_service: ControllerStateService | None = None,
        sync_service: DocumentSyncService | None = None,
    ) -> None:
        self.state_service = state_service or ControllerStateService(
            library_service=library_service,
            template_service=template_service,
            variant_service=variant_service,
            layout_engine=layout_engine,
            constraint_service=constraint_service,
        )
        self.sync_service = sync_service or DocumentSyncService(
            builder_factory=ControllerBuilder,
            gui_module=freecad_gui,
        )
        self.library_service = self.state_service.library_service
        self.template_service = self.state_service.template_service
        self.variant_service = self.state_service.variant_service
        self.layout_engine = self.state_service.layout_engine
        self.constraint_service = self.state_service.constraint_service

    def create_controller(self, doc: Any, controller_data: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.state_service.create_controller(doc, controller_data)
        self.update_document(doc, mode=SyncMode.FULL, state=state)
        return state

    def create_project(self, doc: Any, project_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generic alias for creating a generated project document."""
        return self.create_controller(doc, controller_data=project_data)

    def create_from_template(
        self,
        doc: Any,
        template_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.state_service.create_from_template(doc, template_id, overrides=overrides)
        self.update_document(doc, mode=SyncMode.FULL, state=state)
        return state

    def create_from_variant(
        self,
        doc: Any,
        variant_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.state_service.create_from_variant(doc, variant_id, overrides=overrides)
        self.update_document(doc, mode=SyncMode.FULL, state=state)
        return state

    def apply_template_parameters(
        self,
        doc: Any,
        *,
        template_id: str,
        variant_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if variant_id:
            mutator = lambda: self.state_service.create_from_variant(doc, variant_id, overrides=overrides)
        else:
            mutator = lambda: self.state_service.create_from_template(doc, template_id, overrides=overrides)
        return self._mutate_with_full_sync(
            doc,
            transaction_name="OCW Apply Parameters",
            mutator=mutator,
        )

    def get_state(self, doc: Any) -> dict[str, Any]:
        return self.state_service.get_state(doc)

    def save_state(self, doc: Any, state: dict[str, Any]) -> None:
        self.state_service.save_state(doc, state)

    def list_library_components(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.state_service.list_library_components(category=category)

    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.state_service.list_templates(category=category)

    def list_variants(
        self,
        template_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.state_service.list_variants(template_id=template_id, category=category, tag=tag)

    def get_ui_context(self, doc: Any) -> dict[str, Any]:
        return self.state_service.get_ui_context(doc)

    def add_component(
        self,
        doc: Any,
        library_ref: str,
        component_id: str | None = None,
        component_type: str | None = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        zone_id: str | None = None,
        ) -> dict[str, Any]:
        return self._mutate_with_full_sync(
            doc,
            transaction_name="OCW Place Component",
            mutator=lambda: self.state_service.add_component(
                doc,
                library_ref=library_ref,
                component_id=component_id,
                component_type=component_type,
                x=x,
                y=y,
                rotation=rotation,
                zone_id=zone_id,
            ),
        )

    def add_components(
        self,
        doc: Any,
        components: list[dict[str, Any]],
        *,
        primary_id: str | None = None,
        transaction_name: str = "OCW Add Components",
    ) -> dict[str, Any]:
        return self._mutate_with_full_sync(
            doc,
            transaction_name=transaction_name,
            mutator=lambda: self.state_service.add_components(doc, components, primary_id=primary_id),
        )

    def move_component(
        self,
        doc: Any,
        component_id: str,
        x: float,
        y: float,
        rotation: float | None = None,
    ) -> dict[str, Any]:
        return self._mutate_with_full_sync(
            doc,
            transaction_name="OCW Drag Move Component",
            mutator=lambda: self.state_service.move_component(doc, component_id, x=x, y=y, rotation=rotation),
        )

    def update_controller(self, doc: Any, updates: dict[str, Any]) -> dict[str, Any]:
        state = self.state_service.update_controller(doc, updates)
        self.update_document(doc, mode=SyncMode.FULL, state=state)
        return state

    def update_project(self, doc: Any, updates: dict[str, Any]) -> dict[str, Any]:
        """Generic alias for updating generated project geometry/state."""
        return self.update_controller(doc, updates)

    def update_component(self, doc: Any, component_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        current_component = self.state_service.get_component(doc, component_id)
        state = self.state_service.update_component(doc, component_id, updates)
        mode = self._resolve_component_update_sync_mode(updates, component=current_component)
        self.update_document(
            doc,
            mode=mode,
            state=state if mode in {SyncMode.FULL, SyncMode.PARTIAL_READY} else None,
            selection=state["meta"].get("selection"),
        )
        return state

    def bulk_update_components(
        self,
        doc: Any,
        updates_by_component: dict[str, dict[str, Any]],
        transaction_name: str = "OCW Bulk Edit Components",
    ) -> dict[str, Any]:
        previous_state = deepcopy(self.state_service.get_state(doc))
        combined_updates = [updates for updates in updates_by_component.values() if isinstance(updates, dict)]
        mode = SyncMode.STATE_ONLY
        component_lookup = {component["id"]: component for component in previous_state["components"]}
        if any(
            self._resolve_component_update_sync_mode(updates, component=component_lookup.get(component_id)) == SyncMode.FULL
            for component_id, updates in updates_by_component.items()
            if isinstance(updates, dict)
        ):
            mode = SyncMode.FULL
        try:
            with document_transaction(doc, transaction_name):
                state = self.state_service.bulk_update_components(doc, updates_by_component)
                self.update_document(
                    doc,
                    mode=mode,
                    state=state if mode in {SyncMode.FULL, SyncMode.PARTIAL_READY} else None,
                    selection=state["meta"].get("selection"),
                )
                return state
        except Exception:
            self.state_service.save_state(doc, previous_state)
            raise

    def select_component(self, doc: Any, component_id: str | None) -> dict[str, Any]:
        state = self.state_service.select_component(doc, component_id)
        self.update_document(
            doc,
            mode=SyncMode.VISUAL_ONLY,
            selection=state["meta"].get("selection"),
            recompute=False,
        )
        return state

    def get_selected_component_ids(self, doc: Any) -> list[str]:
        return self.state_service.get_selected_component_ids(doc)

    def set_selected_component_ids(
        self,
        doc: Any,
        component_ids: list[str],
        primary_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.state_service.set_selected_component_ids(doc, component_ids, primary_id=primary_id)
        self.update_document(
            doc,
            mode=SyncMode.VISUAL_ONLY,
            selection=state["meta"].get("selection"),
            recompute=False,
        )
        return state

    def clear_selection(self, doc: Any) -> dict[str, Any]:
        state = self.state_service.clear_selection(doc)
        self.update_document(
            doc,
            mode=SyncMode.VISUAL_ONLY,
            selection=state["meta"].get("selection"),
            recompute=False,
        )
        return state

    def toggle_selection(self, doc: Any, component_id: str, make_primary: bool = True) -> dict[str, Any]:
        state = self.state_service.toggle_selection(doc, component_id, make_primary=make_primary)
        self.update_document(
            doc,
            mode=SyncMode.VISUAL_ONLY,
            selection=state["meta"].get("selection"),
            recompute=False,
        )
        return state

    def get_component(self, doc: Any, component_id: str) -> dict[str, Any]:
        return self.state_service.get_component(doc, component_id)
    def auto_layout(
        self,
        doc: Any,
        strategy: str = "grid",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state, result = self.state_service.auto_layout(doc, strategy=strategy, config=config)
        self.update_document(doc, mode=SyncMode.FULL, state=state)
        return result

    def validate_layout(self, doc: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.state_service.validate_layout(doc, config=config)

    def sync_document(self, doc: Any, state: dict[str, Any] | None = None) -> None:
        self.update_document(doc, mode=SyncMode.FULL, state=state)

    def refresh_document_visuals(self, doc: Any, recompute: bool = False) -> None:
        self.update_document(doc, mode=SyncMode.VISUAL_ONLY, recompute=recompute)

    def update_document(
        self,
        doc: Any,
        mode: str = SyncMode.FULL,
        state: dict[str, Any] | None = None,
        selection: str | None = None,
        recompute: bool = False,
    ) -> None:
        resolved_state = state
        resolved_selection = selection
        if mode in {SyncMode.FULL, SyncMode.PARTIAL_READY} and resolved_state is None:
            resolved_state = self.state_service.get_state(doc)
        if mode == SyncMode.VISUAL_ONLY and resolved_selection is None:
            resolved_selection = self.state_service.get_ui_context(doc).get("selection")
        self.sync_service.update_document(
            doc,
            mode=mode,
            state=resolved_state,
            selection=resolved_selection,
            recompute=recompute,
        )

    def _mutate_with_full_sync(
        self,
        doc: Any,
        transaction_name: str,
        mutator: Any,
    ) -> dict[str, Any]:
        previous_state = deepcopy(self.state_service.get_state(doc))
        try:
            with document_transaction(doc, transaction_name):
                state = mutator()
                self.update_document(doc, mode=SyncMode.FULL, state=state)
                return state
        except Exception:
            self.state_service.save_state(doc, previous_state)
            raise

    def _resolve_component_update_sync_mode(self, updates: dict[str, Any], component: dict[str, Any] | None = None) -> str:
        geometry_fields = {"x", "y", "rotation", "library_ref", "zone_id", "type", "group_id", "group_role"}
        if any(field in geometry_fields for field in updates):
            return SyncMode.FULL
        if "properties" in updates and self._properties_affect_geometry(component, updates.get("properties")):
            return SyncMode.FULL
        return SyncMode.STATE_ONLY

    def _properties_affect_geometry(
        self,
        component: dict[str, Any] | None,
        properties: Any,
    ) -> bool:
        if not isinstance(properties, dict) or component is None:
            return False
        category = str(component.get("type") or "")
        geometry_properties_by_category = {
            "button": {"cap_width", "cap_depth", "cap_height"},
            "rgb_button": {"cap_width", "cap_depth", "cap_height"},
            "fader": {"cap_depth", "cap_height", "cap_length"},
        }
        relevant = geometry_properties_by_category.get(category, set())
        return any(key in relevant for key in properties)


ProjectService = ControllerService


ProjectService = ControllerService
