from __future__ import annotations
from copy import deepcopy
from typing import Any

from ocf_freecad.freecad_api import gui as freecad_gui
from ocf_freecad.freecad_api.metadata import get_document_data, set_document_data, update_document_data
from ocf_freecad.freecad_api.state import STATE_CONTAINER_LABEL, STATE_CONTAINER_NAME, read_state, write_state
from ocf_freecad.domain.component import Component
from ocf_freecad.domain.controller import Controller
from ocf_freecad.generator.controller_builder import ControllerBuilder
from ocf_freecad.layout.engine import LayoutEngine
from ocf_freecad.services.constraint_service import ConstraintService
from ocf_freecad.services.library_service import LibraryService
from ocf_freecad.services.template_service import TemplateService
from ocf_freecad.services.variant_service import VariantService


DEFAULT_CONTROLLER = {
    "id": "controller",
    "width": 160.0,
    "depth": 100.0,
    "height": 30.0,
    "top_thickness": 3.0,
    "surface": None,
    "mounting_holes": [],
    "reserved_zones": [],
    "layout_zones": [],
}

DEFAULT_META = {
    "template_id": None,
    "variant_id": None,
    "selection": None,
    "overrides": {},
    "layout": {},
    "validation": None,
    "ui": {
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
    },
}


def _log_to_console(message: str, level: str = "message") -> None:
    text = f"[OCF] {message}"
    if not text.endswith("\n"):
        text += "\n"
    try:
        import FreeCAD as App
    except ImportError:
        App = None
    console = getattr(App, "Console", None) if App is not None else None
    writer_name = {
        "error": "PrintError",
        "warning": "PrintWarning",
        "message": "PrintMessage",
    }.get(level, "PrintMessage")
    writer = getattr(console, writer_name, None) if console is not None else None
    if callable(writer):
        writer(text)
        return
    print(text, end="")


class ControllerService:
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
        _log_to_console(
            f"Creating controller in document '{getattr(doc, 'Name', '<unnamed>')}' "
            f"with size {state['controller']['width']} x {state['controller']['depth']} mm."
        )
        self.sync_document(doc)
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
        normalized = self._normalize_state(state)
        write_state(doc, normalized)

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
            "overrides": deepcopy(state["meta"].get("overrides", {})),
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
        self.save_state(doc, state)
        _log_to_console(
            f"Adding component '{component_id}' from '{library_ref}' "
            f"at ({float(x):.2f}, {float(y):.2f}) in document '{getattr(doc, 'Name', '<unnamed>')}'."
        )
        self.sync_document(doc)
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
                self.sync_document(doc)
                return deepcopy(state)
        raise KeyError(f"Unknown component id: {component_id}")

    def update_component(
        self,
        doc: Any,
        component_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(updates, dict):
            raise ValueError("Component updates must be a mapping")
        state = self.get_state(doc)
        for component in state["components"]:
            if component["id"] != component_id:
                continue
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
            state["meta"]["selection"] = component_id
            self.save_state(doc, state)
            self.sync_document(doc)
            return deepcopy(state)
        raise KeyError(f"Unknown component id: {component_id}")

    def select_component(self, doc: Any, component_id: str | None) -> dict[str, Any]:
        state = self.get_state(doc)
        if component_id is not None and component_id not in {component["id"] for component in state["components"]}:
            raise KeyError(f"Unknown component id: {component_id}")
        state["meta"]["selection"] = component_id
        self.save_state(doc, state)
        self.sync_document(doc)
        return deepcopy(state)

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
    ) -> dict[str, Any]:
        state = self.get_state(doc)
        state, result = self._apply_layout_to_state(state, strategy=strategy, config=config)
        self.save_state(doc, state)
        self.sync_document(doc)
        return result

    def validate_layout(self, doc: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.get_state(doc)
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        report = self.constraint_service.validate(controller, components, config=config)
        state["meta"]["validation"] = deepcopy(report)
        self.save_state(doc, state)
        return report

    def sync_document(self, doc: Any) -> None:
        state = self.get_state(doc)
        set_document_data(doc, "OCFLastSync", {
            "controller_id": state["controller"]["id"],
            "component_count": len(state["components"]),
            "template_id": state["meta"].get("template_id"),
            "variant_id": state["meta"].get("variant_id"),
            "selection": state["meta"].get("selection"),
        })
        _log_to_console(
            f"Syncing document '{getattr(doc, 'Name', '<unnamed>')}' "
            f"for controller '{state['controller']['id']}' with {len(state['components'])} components."
        )
        if not hasattr(doc, "addObject"):
            if hasattr(doc, "recompute"):
                doc.recompute()
            _log_to_console(
                f"Document '{getattr(doc, 'Name', '<unnamed>')}' has no FreeCAD object API; state-only sync complete.",
                level="warning",
            )
            return

        self._clear_generated_objects(doc)
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        builder = ControllerBuilder(doc=doc)
        body = builder.build_body(controller)
        self._set_generated_label(body, "OCF_ControllerBody")
        top = builder.build_top_plate(controller)
        self._set_generated_label(top, "OCF_TopPlate")
        top_cut = builder.apply_cutouts(top, components)
        self._set_generated_label(top_cut, "OCF_TopPlateCut")
        self._create_component_markers(doc, builder, components, controller.height)
        self._apply_selection_highlight(doc, state["meta"].get("selection"))
        if hasattr(doc, "recompute"):
            doc.recompute()
        generated_count = self._generated_object_count(doc)
        update_document_data(doc, "OCFLastSync", {"generated_object_count": generated_count})
        revealed = freecad_gui.reveal_generated_objects(doc)
        freecad_gui.activate_document(doc)
        freecad_gui.focus_view(doc, fit=True)
        _log_to_console(
            f"Document sync complete for '{getattr(doc, 'Name', '<unnamed>')}': "
            f"{generated_count} generated objects, {revealed} visible in the 3D view."
        )

    def _create_component_markers(self, doc: Any, builder: ControllerBuilder, components: list[Component], z_height: float) -> None:
        for keepout in builder.build_keepouts(components):
            name = f"OCF_{keepout['component_id']}_{keepout['feature']}"
            if keepout["shape"] == "circle":
                marker = __import__("ocf_freecad.freecad_api.shapes", fromlist=["create_cylinder"]).create_cylinder(
                    doc,
                    name,
                    radius=float(keepout["diameter"]) / 2.0,
                    height=1.0,
                    x=float(keepout["x"]),
                    y=float(keepout["y"]),
                    z=float(z_height),
                )
                self._set_generated_label(marker, name)
                continue
            if keepout["shape"] == "rect":
                marker = __import__("ocf_freecad.freecad_api.shapes", fromlist=["create_rect_prism"]).create_rect_prism(
                    doc,
                    name,
                    width=float(keepout["width"]),
                    depth=float(keepout["height"]),
                    height=1.0,
                    x=float(keepout["x"]) - (float(keepout["width"]) / 2.0),
                    y=float(keepout["y"]) - (float(keepout["height"]) / 2.0),
                    z=float(z_height),
                )
                self._set_generated_label(marker, name)

    def _clear_generated_objects(self, doc: Any) -> None:
        if not hasattr(doc, "Objects") or not hasattr(doc, "removeObject"):
            return
        for obj in list(doc.Objects):
            name = getattr(obj, "Name", "")
            label = getattr(obj, "Label", "")
            if name == STATE_CONTAINER_NAME or label == STATE_CONTAINER_LABEL:
                continue
            if (
                str(name).startswith("OCF_")
                or str(label).startswith("OCF_")
                or name in {"ControllerBody", "TopPlate"}
                or str(name).startswith("TopPlate_")
                or str(name).startswith("cutout_")
            ):
                doc.removeObject(name)

    def _build_controller(self, controller_data: dict[str, Any]) -> Controller:
        return Controller(**controller_data)

    def _build_component(self, component_data: dict[str, Any]) -> Component:
        return Component(**component_data)

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

    def _set_generated_label(self, obj: Any, label: str) -> None:
        if hasattr(obj, "Label"):
            obj.Label = label
        else:
            setattr(obj, "Name", label)

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
        if state["components"]:
            state["meta"]["selection"] = state["components"][0]["id"]
        _log_to_console(
            f"Generated project loaded for document '{getattr(doc, 'Name', '<unnamed>')}': "
            f"template={template_id or '-'} variant={variant_id or '-'} components={len(state['components'])}."
        )
        state = self._prepare_initial_layout_state(state, project)
        self.save_state(doc, state)
        self.sync_document(doc)
        return deepcopy(state)

    def _apply_layout_to_state(
        self,
        state: dict[str, Any],
        strategy: str,
        config: dict[str, Any] | None = None,
        source: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        config_copy = deepcopy(config) if config is not None else {}
        result = self.layout_engine.place(controller, components, strategy=strategy, config=config_copy)
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
            _log_to_console(
                f"Applying initial layout for template='{state['meta'].get('template_id') or '-'}' "
                f"variant='{state['meta'].get('variant_id') or '-'}' using strategy '{strategy}'."
            )
            state, result = self._apply_layout_to_state(state, strategy=strategy, config=config, source="template")
            if result["unplaced_component_ids"]:
                _log_to_console(
                    f"Initial layout left {len(result['unplaced_component_ids'])} components unplaced; "
                    "applying fallback grid positions.",
                    level="warning",
                )
                self._fill_unplaced_components(state, result["unplaced_component_ids"], config=config)
            return state

        if self._has_authored_positions(state["components"]):
            _log_to_console("No layout strategy provided; preserving authored component positions from template/variant.")
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
        _log_to_console(
            "No layout strategy provided and no authored positions found; applying fallback grid placement.",
            level="warning",
        )
        state, result = self._apply_layout_to_state(state, strategy="grid", config=fallback_config, source="fallback")
        if result["unplaced_component_ids"]:
            _log_to_console(
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
            normalized["meta"].update(deepcopy(state["meta"]))
        return normalized

    def _component_type_counts(self, components: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for component in components:
            component_type = str(component.get("type", "unknown"))
            counts[component_type] = counts.get(component_type, 0) + 1
        return counts

    def _apply_selection_highlight(self, doc: Any, selected_component_id: str | None) -> None:
        if not hasattr(doc, "Objects"):
            return
        for obj in getattr(doc, "Objects", []):
            label = str(getattr(obj, "Label", getattr(obj, "Name", "")))
            if not label.startswith("OCF_"):
                continue
            if label.startswith("OCF_OVERLAY_"):
                continue
            view = getattr(obj, "ViewObject", None)
            if view is None:
                continue
            is_selected = selected_component_id is not None and selected_component_id in label
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.9, 0.3, 0.2) if is_selected else (0.7, 0.7, 0.7)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.9, 0.3, 0.2) if is_selected else (0.2, 0.2, 0.2)

    def _generated_object_count(self, doc: Any) -> int:
        count = 0
        for obj in getattr(doc, "Objects", []):
            name = str(getattr(obj, "Name", ""))
            label = str(getattr(obj, "Label", ""))
            if name.startswith("OCF_") or label.startswith("OCF_"):
                count += 1
        return count
