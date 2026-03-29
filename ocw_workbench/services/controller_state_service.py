from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.freecad_api.state import read_state, write_state
from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.layout.engine import LayoutEngine
from ocw_workbench.services._logging import log_to_console
from ocw_workbench.services.constraint_service import ConstraintService
from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.variant_service import VariantService

DEFAULT_CONTROLLER = {
    "id": "controller",
    "width": 160.0,
    "depth": 100.0,
    "height": 30.0,
    "top_thickness": 3.0,
    "wall_thickness": 3.0,
    "bottom_thickness": 3.0,
    "lid_inset": 1.5,
    "inner_clearance": 0.35,
    "pcb_thickness": 1.6,
    "pcb_inset": 8.0,
    "pcb_standoff_height": 8.0,
    "mounting": {},
    "surface": None,
    "mounting_holes": [],
    "reserved_zones": [],
    "layout_zones": [],
}

DEFAULT_META = {
    "template_id": None,
    "variant_id": None,
    "selection": None,
    "selected_ids": [],
    "overrides": {},
    "parameters": {
        "values": {},
        "sources": {},
        "preset_id": None,
    },
    "layout": {},
    "validation": None,
    "ui": {
        "active_interaction": None,
        "hovered_component_id": None,
        "overlay_enabled": True,
        "show_constraints": True,
        "grid_mm": 1.0,
        "snap_enabled": True,
        "move_component_id": None,
        "measurements_enabled": True,
        "conflict_lines_enabled": True,
        "constraint_labels_enabled": True,
        "show_warnings": True,
        "show_errors": True,
        "active_component_template_id": None,
    },
}


class ControllerStateService:
    def __init__(
        self,
        library_service: LibraryService | None = None,
        template_service: TemplateService | None = None,
        variant_service: VariantService | None = None,
        layout_engine: LayoutEngine | None = None,
        constraint_service: ConstraintService | None = None,
    ) -> None:
        self.library_service = library_service or LibraryService()
        self.template_service = template_service or TemplateService()
        self.variant_service = variant_service or VariantService()
        self.layout_engine = layout_engine or LayoutEngine()
        self.constraint_service = constraint_service or ConstraintService()

    def create_controller(self, doc: Any, controller_data: dict[str, Any] | None = None) -> dict[str, Any]:
        state = {
            "controller": deepcopy(DEFAULT_CONTROLLER),
            "components": [],
            "meta": deepcopy(DEFAULT_META),
        }
        if controller_data is not None:
            state["controller"].update(deepcopy(controller_data))
        self.save_state(doc, state)
        log_to_console(
            f"Creating controller in document '{getattr(doc, 'Name', '<unnamed>')}' "
            f"with size {state['controller']['width']} x {state['controller']['depth']} mm."
        )
        return deepcopy(state)

    def create_from_template(
        self,
        doc: Any,
        template_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self.template_service.generate_from_template(template_id, overrides=overrides)
        return self._apply_generated_project(
            doc,
            project,
            template_id=template_id,
            variant_id=None,
            overrides=overrides,
        )

    def create_from_variant(
        self,
        doc: Any,
        variant_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self.variant_service.generate_from_variant(variant_id, overrides=overrides)
        template_id = project.get("template", {}).get("id")
        return self._apply_generated_project(
            doc,
            project,
            template_id=template_id if isinstance(template_id, str) else None,
            variant_id=variant_id,
            overrides=overrides,
        )

    def get_state(self, doc: Any) -> dict[str, Any]:
        state = read_state(doc)
        if isinstance(state, dict):
            return self._normalize_state(state)
        return self._normalize_state({
            "controller": deepcopy(DEFAULT_CONTROLLER),
            "components": [],
        })

    def save_state(self, doc: Any, state: dict[str, Any]) -> None:
        write_state(doc, self._normalize_state(state))

    def list_library_components(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.library_service.list_by_category(category=category)

    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.template_service.list_templates(category=category)

    def list_variants(
        self,
        template_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.variant_service.list_variants(template_id=template_id, category=category, tag=tag)

    def get_ui_context(self, doc: Any) -> dict[str, Any]:
        state = self.get_state(doc)
        return {
            "template_id": state["meta"].get("template_id"),
            "variant_id": state["meta"].get("variant_id"),
            "selection": state["meta"].get("selection"),
            "selected_ids": deepcopy(state["meta"].get("selected_ids", [])),
            "selection_count": len(state["meta"].get("selected_ids", [])),
            "overrides": deepcopy(state["meta"].get("overrides", {})),
            "parameters": deepcopy(state["meta"].get("parameters", {})),
            "component_count": len(state["components"]),
            "component_types": self._component_type_counts(state["components"]),
            "layout": deepcopy(state["meta"].get("layout", {})),
            "validation": deepcopy(state["meta"].get("validation")),
            "ui": deepcopy(state["meta"].get("ui", {})),
        }

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
        state = self.get_state(doc)
        library_component = self.library_service.get(library_ref)
        component_type = component_type or library_component["category"]
        component_id = component_id or self._next_component_id(state["components"], component_type)
        state["components"].append(
            {
                "id": component_id,
                "type": component_type,
                "library_ref": library_ref,
                "x": float(x),
                "y": float(y),
                "rotation": float(rotation),
                "zone_id": zone_id,
            }
        )
        state["meta"]["selection"] = component_id
        state["meta"]["selected_ids"] = [component_id]
        self.save_state(doc, state)
        log_to_console(
            f"Adding component '{component_id}' from '{library_ref}' "
            f"at ({float(x):.2f}, {float(y):.2f}) in document '{getattr(doc, 'Name', '<unnamed>')}'."
        )
        return deepcopy(state)

    def move_component(
        self,
        doc: Any,
        component_id: str,
        x: float,
        y: float,
        rotation: float | None = None,
    ) -> dict[str, Any]:
        state = self.get_state(doc)
        for component in state["components"]:
            if component["id"] == component_id:
                component["x"] = float(x)
                component["y"] = float(y)
                if rotation is not None:
                    component["rotation"] = float(rotation)
                self.save_state(doc, state)
                return deepcopy(state)
        raise KeyError(f"Unknown component id: {component_id}")

    def update_controller(self, doc: Any, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict):
            raise ValueError("Controller updates must be a mapping")
        state = self.get_state(doc)
        controller = state["controller"]
        for field in ("width", "depth", "height", "top_thickness", "wall_thickness", "bottom_thickness", "pcb_thickness", "pcb_inset", "pcb_standoff_height"):
            if field in updates and updates[field] is not None:
                controller[field] = self._positive_float(updates[field], field)
        for field in ("lid_inset", "inner_clearance"):
            if field in updates and updates[field] is not None:
                controller[field] = self._non_negative_float(updates[field], field)
        surface_shape = updates.get("surface_shape")
        corner_radius = updates.get("corner_radius")
        if surface_shape is not None or corner_radius is not None:
            controller["surface"] = self._updated_surface(
                controller=controller,
                current_surface=controller.get("surface"),
                shape=surface_shape,
                corner_radius=corner_radius,
            )
        self.save_state(doc, state)
        log_to_console(
            f"Updated controller '{controller['id']}' to "
            f"{controller['width']} x {controller['depth']} x {controller['height']} mm."
        )
        return deepcopy(state)

    def update_component(self, doc: Any, component_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict):
            raise ValueError("Component updates must be a mapping")
        state = self.get_state(doc)
        for component in state["components"]:
            if component["id"] != component_id:
                continue
            self._apply_component_updates(component, component_id, updates)
            state["meta"]["selection"] = component_id
            state["meta"]["selected_ids"] = [component_id]
            self.save_state(doc, state)
            return deepcopy(state)
        raise KeyError(f"Unknown component id: {component_id}")

    def bulk_update_components(
        self,
        doc: Any,
        updates_by_component: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(updates_by_component, dict) or not updates_by_component:
            raise ValueError("Bulk component updates must be a non-empty mapping")
        state = self.get_state(doc)
        by_id = {component["id"]: component for component in state["components"]}
        for component_id, updates in updates_by_component.items():
            if component_id not in by_id:
                raise KeyError(f"Unknown component id: {component_id}")
            if not isinstance(updates, dict):
                raise ValueError(f"Bulk updates for component '{component_id}' must be a mapping")
            self._apply_component_updates(by_id[component_id], component_id, updates)
        self.save_state(doc, state)
        return deepcopy(state)

    def add_components(
        self,
        doc: Any,
        components: list[dict[str, Any]],
        *,
        primary_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(components, list) or not components:
            raise ValueError("Component additions must be a non-empty list")
        state = self.get_state(doc)
        existing_ids = {str(component["id"]) for component in state["components"]}
        added_ids: list[str] = []
        for raw_component in components:
            normalized = self._normalized_new_component(raw_component, existing_ids)
            existing_ids.add(str(normalized["id"]))
            added_ids.append(str(normalized["id"]))
            state["components"].append(normalized)
        resolved_primary = primary_id if primary_id in added_ids else added_ids[0]
        state["meta"]["selection"] = resolved_primary
        state["meta"]["selected_ids"] = [resolved_primary] + [component_id for component_id in added_ids if component_id != resolved_primary]
        self.save_state(doc, state)
        return deepcopy(state)

    def select_component(self, doc: Any, component_id: str | None) -> dict[str, Any]:
        return self.set_selected_component_ids(doc, [component_id] if component_id is not None else [], primary_id=component_id)

    def get_selected_component_ids(self, doc: Any) -> list[str]:
        state = self.get_state(doc)
        return list(state["meta"].get("selected_ids", []))

    def set_selected_component_ids(
        self,
        doc: Any,
        component_ids: list[str],
        primary_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_state(doc)
        available_ids = {component["id"] for component in state["components"]}
        normalized_ids: list[str] = []
        seen: set[str] = set()
        for component_id in component_ids:
            if component_id not in available_ids:
                raise KeyError(f"Unknown component id: {component_id}")
            if component_id in seen:
                continue
            seen.add(component_id)
            normalized_ids.append(component_id)
        if primary_id is not None and primary_id not in available_ids:
            raise KeyError(f"Unknown component id: {primary_id}")
        resolved_primary = primary_id if primary_id in normalized_ids else (normalized_ids[0] if normalized_ids else None)
        if resolved_primary is not None:
            normalized_ids = [resolved_primary] + [component_id for component_id in normalized_ids if component_id != resolved_primary]
        state["meta"]["selection"] = resolved_primary
        state["meta"]["selected_ids"] = normalized_ids
        self.save_state(doc, state)
        return deepcopy(state)

    def clear_selection(self, doc: Any) -> dict[str, Any]:
        return self.set_selected_component_ids(doc, [], primary_id=None)

    def toggle_selection(self, doc: Any, component_id: str, make_primary: bool = True) -> dict[str, Any]:
        state = self.get_state(doc)
        current_ids = list(state["meta"].get("selected_ids", []))
        if component_id in current_ids:
            remaining = [item for item in current_ids if item != component_id]
            next_primary = state["meta"].get("selection")
            if next_primary == component_id:
                next_primary = remaining[0] if remaining else None
            return self.set_selected_component_ids(doc, remaining, primary_id=next_primary)
        next_ids = current_ids + [component_id]
        primary_id = component_id if make_primary else state["meta"].get("selection")
        return self.set_selected_component_ids(doc, next_ids, primary_id=primary_id)

    def get_component(self, doc: Any, component_id: str) -> dict[str, Any]:
        state = self.get_state(doc)
        for component in state["components"]:
            if component["id"] == component_id:
                return deepcopy(component)
        raise KeyError(f"Unknown component id: {component_id}")

    def auto_layout(
        self,
        doc: Any,
        strategy: str = "grid",
        config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get_state(doc)
        state, result = self._apply_layout_to_state(state, strategy=strategy, config=config)
        self.save_state(doc, state)
        return deepcopy(state), result

    def validate_layout(self, doc: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.get_state(doc)
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        report = self.constraint_service.validate(controller, components, config=config)
        state["meta"]["validation"] = deepcopy(report)
        self.save_state(doc, state)
        return report

    def _build_controller(self, controller_data: dict[str, Any]) -> Controller:
        return Controller(**controller_data)

    def _build_component(self, component_data: dict[str, Any]) -> Component:
        return Component(**component_data)

    def _apply_component_updates(self, component: dict[str, Any], component_id: str, updates: dict[str, Any]) -> None:
        if "library_ref" in updates:
            library_ref = updates["library_ref"]
            if not isinstance(library_ref, str) or not library_ref:
                raise ValueError(f"Component '{component_id}' has invalid library_ref")
            library_component = self.library_service.get(library_ref)
            component["library_ref"] = library_ref
            component.setdefault("type", library_component["category"])
        for field in ("x", "y", "rotation"):
            if field in updates and updates[field] is not None:
                component[field] = float(updates[field])
        for field in ("zone_id", "type", "io_strategy", "bus", "address"):
            if field in updates:
                component[field] = updates[field]
        if "label" in updates:
            component["label"] = str(updates["label"] or "")
        if "visible" in updates:
            component["visible"] = bool(updates["visible"])
        if "tags" in updates:
            tags = updates["tags"]
            if not isinstance(tags, list):
                raise ValueError("Component tags must be a list")
            component["tags"] = [str(item) for item in tags if str(item).strip()]
        if "properties" in updates:
            properties = updates["properties"]
            if not isinstance(properties, dict):
                raise ValueError("Component properties must be a mapping")
            existing = component.get("properties", {})
            component["properties"] = deepcopy(existing) if isinstance(existing, dict) else {}
            component["properties"].update(deepcopy(properties))

    def _apply_generated_project(
        self,
        doc: Any,
        project: dict[str, Any],
        template_id: str | None,
        variant_id: str | None,
        overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        state = {
            "controller": deepcopy(project["controller"]),
            "components": deepcopy(project["components"]),
            "meta": deepcopy(DEFAULT_META),
        }
        state["meta"]["template_id"] = template_id
        state["meta"]["variant_id"] = variant_id
        state["meta"]["overrides"] = deepcopy(overrides) if overrides is not None else {}
        parameters = deepcopy(project.get("parameters", {})) if isinstance(project.get("parameters"), dict) else {}
        state["meta"]["parameters"] = {
            "values": deepcopy(parameters.get("values", {})) if isinstance(parameters.get("values"), dict) else {},
            "sources": deepcopy(parameters.get("sources", {})) if isinstance(parameters.get("sources"), dict) else {},
            "preset_id": parameters.get("preset_id"),
        }
        if state["components"]:
            state["meta"]["selection"] = state["components"][0]["id"]
            state["meta"]["selected_ids"] = [state["components"][0]["id"]]
        layout_spec = deepcopy(project.get("layout", {})) if isinstance(project.get("layout"), dict) else {}
        log_to_console(
            f"Generated project loaded for document '{getattr(doc, 'Name', '<unnamed>')}': "
            f"template={template_id or '-'} variant={variant_id or '-'} "
            f"components={len(state['components'])} layout_strategy={layout_spec.get('strategy') or '-'}."
        )
        state = self._prepare_initial_layout_state(state, project)
        self.save_state(doc, state)
        return deepcopy(state)

    def _normalized_new_component(self, component: dict[str, Any], existing_ids: set[str]) -> dict[str, Any]:
        if not isinstance(component, dict):
            raise ValueError("New component payloads must be mappings")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            raise ValueError("New components must define a non-empty id")
        if component_id in existing_ids:
            raise ValueError(f"New component id already exists: {component_id}")
        library_ref = component.get("library_ref")
        if not isinstance(library_ref, str) or not library_ref:
            raise ValueError(f"New component '{component_id}' is missing library_ref")
        library_component = self.library_service.get(library_ref)
        normalized = deepcopy(component)
        normalized["type"] = str(component.get("type") or library_component["category"])
        normalized["x"] = float(component.get("x", 0.0) or 0.0)
        normalized["y"] = float(component.get("y", 0.0) or 0.0)
        normalized["rotation"] = float(component.get("rotation", 0.0) or 0.0)
        if "label" in normalized:
            normalized["label"] = str(normalized.get("label") or "")
        if "visible" in normalized:
            normalized["visible"] = bool(normalized.get("visible"))
        if "tags" in normalized and isinstance(normalized.get("tags"), list):
            normalized["tags"] = [str(item) for item in normalized["tags"] if str(item).strip()]
        if "properties" in normalized and not isinstance(normalized.get("properties"), dict):
            raise ValueError("New component properties must be a mapping")
        return normalized

    def _apply_layout_to_state(
        self,
        state: dict[str, Any],
        strategy: str,
        config: dict[str, Any] | None = None,
        source: str | None = None,
        placement_blocking_mode: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        config_copy = self._resolved_layout_config(strategy, config)
        engine_config = deepcopy(config_copy)
        if placement_blocking_mode:
            engine_config["placement_blocking_mode"] = placement_blocking_mode
        result = self.layout_engine.place(controller, components, strategy=strategy, config=engine_config)
        placements = {placement["component_id"]: placement for placement in result["placements"]}
        for component in state["components"]:
            placement = placements.get(component["id"])
            if placement is None:
                continue
            component["x"] = placement["x"]
            component["y"] = placement["y"]
            component["rotation"] = placement["rotation"]
            if placement.get("zone_id") is not None:
                component["zone_id"] = placement["zone_id"]
        state["meta"]["layout"] = {
            "strategy": strategy,
            "config": config_copy,
            "source": source or "manual",
            "result_summary": {
                "placed_count": len(result["placed_components"]),
                "unplaced_count": len(result["unplaced_component_ids"]),
                "warning_count": len(result["warnings"]),
            },
        }
        return state, result

    def _prepare_initial_layout_state(self, state: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
        if not state["components"]:
            state["meta"]["layout"] = {
                "strategy": "none",
                "config": {},
                "source": "empty",
                "result_summary": {
                    "placed_count": 0,
                    "unplaced_count": 0,
                    "warning_count": 0,
                },
            }
            return state

        layout_spec = deepcopy(project.get("layout", {})) if isinstance(project.get("layout"), dict) else {}
        strategy = layout_spec.get("strategy")
        config = deepcopy(layout_spec.get("config", {})) if isinstance(layout_spec.get("config"), dict) else {}

        if isinstance(strategy, str) and strategy:
            resolved_config = self._resolved_layout_config(strategy, config)
            log_to_console(
                f"Applying initial layout for template='{state['meta'].get('template_id') or '-'}' "
                f"variant='{state['meta'].get('variant_id') or '-'}' using strategy '{strategy}' "
                f"with config={resolved_config}."
            )
            state, result = self._apply_layout_to_state(
                state,
                strategy=strategy,
                config=config,
                source="template",
                placement_blocking_mode="cutout_surface",
            )
            if result["unplaced_component_ids"]:
                log_to_console(
                    f"Initial layout left {len(result['unplaced_component_ids'])} components unplaced; "
                    "applying fallback grid positions.",
                    level="warning",
                )
                self._fill_unplaced_components(state, result["unplaced_component_ids"], config=config)
            return state

        if self._has_authored_positions(state["components"]):
            log_to_console("No layout strategy provided; preserving authored component positions from template/variant.")
            state["meta"]["layout"] = {
                "strategy": "authored_positions",
                "config": {},
                "source": "template_positions",
                "result_summary": {
                    "placed_count": len(state["components"]),
                    "unplaced_count": 0,
                    "warning_count": 0,
                },
            }
            return state

        fallback_config = self._fallback_layout_config(state["controller"], len(state["components"]))
        log_to_console(
            f"No layout strategy provided and no authored positions found; applying fallback grid placement "
            f"with config={fallback_config}.",
            level="warning",
        )
        state, result = self._apply_layout_to_state(state, strategy="grid", config=fallback_config, source="fallback")
        if result["unplaced_component_ids"]:
            log_to_console(
                f"Fallback grid left {len(result['unplaced_component_ids'])} components unplaced; "
                "applying defensive sequential placement.",
                level="warning",
            )
            self._fill_unplaced_components(state, result["unplaced_component_ids"], config=fallback_config)
        return state

    def _has_authored_positions(self, components: list[dict[str, Any]]) -> bool:
        return any(
            float(component.get("x", 0.0)) != 0.0 or float(component.get("y", 0.0)) != 0.0
            for component in components
        )

    def _fallback_layout_config(self, controller: dict[str, Any], component_count: int) -> dict[str, Any]:
        surface = controller.get("surface") or {}
        width = float(surface.get("width", controller.get("width", 160.0)))
        height = float(surface.get("height", controller.get("depth", 100.0)))
        columns = max(1, min(component_count, int(width // 24.0) or 1))
        rows = max(1, (component_count + columns - 1) // columns)
        spacing_x = max(18.0, min(32.0, (width - 20.0) / max(columns, 1)))
        spacing_y = max(18.0, min(28.0, (height - 20.0) / max(rows, 1)))
        return {
            "grid_mm": 1.0,
            "padding_mm": 10.0,
            "spacing_x_mm": spacing_x,
            "spacing_y_mm": spacing_y,
        }

    def _resolved_layout_config(self, strategy: str, config: dict[str, Any] | None) -> dict[str, Any]:
        resolved = deepcopy(config) if config is not None else {}
        resolved.setdefault("grid_mm", 1.0)
        resolved.setdefault("padding_mm", 10.0)
        spacing_mm = resolved.get("spacing_mm")
        if spacing_mm is not None:
            resolved.setdefault("spacing_x_mm", spacing_mm)
            resolved.setdefault("spacing_y_mm", spacing_mm)
        if strategy in {"row", "column", "grid", "zone"} and "spacing_mm" not in resolved:
            if resolved.get("spacing_x_mm") == resolved.get("spacing_y_mm") and resolved.get("spacing_x_mm") is not None:
                resolved["spacing_mm"] = resolved["spacing_x_mm"]
        return resolved

    def _fill_unplaced_components(
        self,
        state: dict[str, Any],
        component_ids: list[str],
        config: dict[str, Any] | None = None,
    ) -> None:
        controller = state["controller"]
        surface = controller.get("surface") or {}
        width = float(surface.get("width", controller.get("width", 160.0)))
        height = float(surface.get("height", controller.get("depth", 100.0)))
        config_data = deepcopy(config) if config is not None else {}
        padding = float(config_data.get("padding_mm", 10.0))
        spacing_x = float(config_data.get("spacing_x_mm", config_data.get("spacing_mm", 24.0)))
        spacing_y = float(config_data.get("spacing_y_mm", config_data.get("spacing_mm", 24.0)))
        columns = max(1, int(max(width - (2.0 * padding), spacing_x) // max(spacing_x, 1.0)))
        placed_lookup = {component["id"]: component for component in state["components"]}
        for index, component_id in enumerate(component_ids):
            component = placed_lookup.get(component_id)
            if component is None:
                continue
            column = index % columns
            row = index // columns
            component["x"] = padding + (column * spacing_x)
            component["y"] = padding + (row * spacing_y)
            component["rotation"] = float(component.get("rotation", 0.0) or 0.0)
            max_y = max(padding, height - padding)
            if component["y"] > max_y:
                component["y"] = max_y
        layout_meta = state["meta"].setdefault("layout", {})
        summary = layout_meta.setdefault("result_summary", {})
        summary["placed_count"] = len(state["components"])
        summary["unplaced_count"] = 0
        summary["warning_count"] = int(summary.get("warning_count", 0)) + len(component_ids)

    def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "controller": deepcopy(DEFAULT_CONTROLLER),
            "components": [],
            "meta": deepcopy(DEFAULT_META),
        }
        normalized["controller"].update(deepcopy(state.get("controller", {})))
        normalized["components"] = deepcopy(state.get("components", []))
        if isinstance(state.get("meta"), dict):
            meta = deepcopy(state["meta"])
            normalized["meta"].update({key: value for key, value in meta.items() if key not in {"parameters", "ui"}})
            parameters = meta.get("parameters")
            if isinstance(parameters, dict):
                normalized["meta"]["parameters"].update(deepcopy(parameters))
            overrides = normalized["meta"].get("overrides")
            if not isinstance(overrides, dict):
                normalized["meta"]["overrides"] = {}
            ui = meta.get("ui")
            if isinstance(ui, dict):
                normalized["meta"]["ui"].update(deepcopy(ui))
        selected_ids = normalized["meta"].get("selected_ids")
        if not isinstance(selected_ids, list):
            selected_ids = []
        available_ids = {str(component.get("id")) for component in normalized["components"] if component.get("id")}
        deduped_ids: list[str] = []
        seen_ids: set[str] = set()
        for component_id in selected_ids:
            component_key = str(component_id)
            if component_key not in available_ids or component_key in seen_ids:
                continue
            seen_ids.add(component_key)
            deduped_ids.append(component_key)
        primary_id = normalized["meta"].get("selection")
        if isinstance(primary_id, str) and primary_id in available_ids:
            if primary_id not in deduped_ids:
                deduped_ids.insert(0, primary_id)
            else:
                deduped_ids = [primary_id] + [component_id for component_id in deduped_ids if component_id != primary_id]
        elif deduped_ids:
            primary_id = deduped_ids[0]
        else:
            primary_id = None
        normalized["meta"]["selection"] = primary_id
        normalized["meta"]["selected_ids"] = deduped_ids
        return normalized

    def _positive_float(self, value: Any, field_name: str) -> float:
        number = float(value)
        if number <= 0.0:
            raise ValueError(f"Controller field '{field_name}' must be greater than zero")
        return number

    def _non_negative_float(self, value: Any, field_name: str) -> float:
        number = float(value)
        if number < 0.0:
            raise ValueError(f"Controller field '{field_name}' must not be negative")
        return number

    def _updated_surface(
        self,
        controller: dict[str, Any],
        current_surface: Any,
        shape: Any,
        corner_radius: Any,
    ) -> dict[str, Any] | None:
        shape_name = str(shape or (current_surface or {}).get("shape") or "rectangle")
        width = float(controller["width"])
        depth = float(controller["depth"])
        if shape_name in {"default", "none"}:
            return None
        if shape_name == "rectangle":
            return {
                "shape": "rectangle",
                "width": width,
                "height": depth,
            }
        if shape_name == "rounded_rect":
            radius_value = corner_radius
            if radius_value is None and isinstance(current_surface, dict):
                radius_value = current_surface.get("corner_radius", 0.0)
            radius = self._non_negative_float(radius_value or 0.0, "corner_radius")
            return {
                "shape": "rounded_rect",
                "width": width,
                "height": depth,
                "corner_radius": radius,
            }
        raise ValueError(f"Unsupported surface shape '{shape_name}'")

    def _next_component_id(self, components: list[dict[str, Any]], component_type: str) -> str:
        prefix = {
            "encoder": "enc",
            "button": "btn",
            "display": "disp",
            "fader": "fader",
            "pad": "pad",
            "rgb_button": "rgb",
        }.get(component_type, "comp")
        index = 1
        existing_ids = {component["id"] for component in components}
        while f"{prefix}{index}" in existing_ids:
            index += 1
        return f"{prefix}{index}"

    def _component_type_counts(self, components: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for component in components:
            component_type = str(component.get("type", "unknown"))
            counts[component_type] = counts.get(component_type, 0) + 1
        return counts
