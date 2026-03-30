from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.templates.resolver import TemplateResolver


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class TemplateGenerator:
    def __init__(
        self,
        registry: TemplateRegistry | None = None,
        resolver: TemplateResolver | None = None,
        library_service: LibraryService | None = None,
    ) -> None:
        self.registry = registry or TemplateRegistry()
        self.resolver = resolver or TemplateResolver()
        self.library_service = library_service or LibraryService()

    def generate_from_template(
        self,
        template_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template = self.registry.get_template(template_id)
        resolved = self.resolver.resolve(template, overrides=overrides)
        return self.build_project_from_resolved_template(resolved)

    def build_project_from_resolved_template(self, resolved: dict[str, Any]) -> dict[str, Any]:
        controller = self._build_controller(resolved)
        components = self._build_components(resolved)
        project = {
            "template": deepcopy(resolved["template"]),
            "controller": controller,
            "components": components,
            "layout": deepcopy(resolved.get("layout", {})),
            "constraints": deepcopy(resolved.get("constraints", {})),
            "defaults": deepcopy(resolved.get("defaults", {})),
            "zones": deepcopy(resolved.get("zones", [])),
        }
        if resolved.get("firmware"):
            project["firmware"] = deepcopy(resolved["firmware"])
        if resolved.get("ocf"):
            project["ocf"] = deepcopy(resolved["ocf"])
        if isinstance(resolved.get("metadata"), dict) and resolved["metadata"]:
            project["metadata"] = deepcopy(resolved["metadata"])
        if resolved.get("variant"):
            project["variant"] = deepcopy(resolved["variant"])
        if isinstance(resolved.get("resolved_parameters"), dict):
            project["parameters"] = deepcopy(resolved["resolved_parameters"])
        return project

    def _build_controller(self, template: dict[str, Any]) -> dict[str, Any]:
        controller_data = deepcopy(template["controller"])
        surface = controller_data.get("surface", {})
        if not isinstance(surface, dict):
            raise ValueError("Template controller surface must be a mapping")
        surface_shape = surface.get("type", surface.get("shape", "rectangle"))
        width = float(surface.get("width", controller_data.get("width", 160.0)))
        height = float(surface.get("height", controller_data.get("depth", 100.0)))
        controller = {
            "id": template["template"]["id"],
            "width": float(controller_data.get("width", width)),
            "depth": float(controller_data.get("depth", height)),
            "height": float(controller_data.get("height", 30.0)),
            "top_thickness": float(controller_data.get("top_thickness", 3.0)),
            "wall_thickness": float(controller_data.get("wall_thickness", 3.0)),
            "bottom_thickness": float(controller_data.get("bottom_thickness", 3.0)),
            "lid_inset": float(controller_data.get("lid_inset", 1.5)),
            "inner_clearance": float(controller_data.get("inner_clearance", 0.35)),
            "pcb_thickness": float(controller_data.get("pcb_thickness", 1.6)),
            "pcb_inset": float(controller_data.get("pcb_inset", 8.0)),
            "pcb_standoff_height": float(controller_data.get("pcb_standoff_height", 8.0)),
            "mounting": deepcopy(controller_data.get("mounting", {})),
            "mounting_holes": deepcopy(controller_data.get("mounting_holes", [])),
            "reserved_zones": deepcopy(controller_data.get("reserved_zones", [])),
            "layout_zones": deepcopy(template.get("zones", [])),
        }
        if isinstance(controller_data.get("geometry"), dict):
            controller["geometry"] = deepcopy(controller_data["geometry"])
        controller["surface"] = {
            "shape": surface_shape,
            "width": width,
            "height": height,
        }
        if "corner_radius" in surface:
            controller["surface"]["corner_radius"] = float(surface["corner_radius"])
        if "points" in surface:
            controller["surface"]["points"] = deepcopy(surface["points"])
        if "type" in surface:
            controller["surface"]["type"] = deepcopy(surface["type"])
        return controller

    def _build_components(self, template: dict[str, Any]) -> list[dict[str, Any]]:
        defaults = deepcopy(template.get("defaults", {}))
        component_defaults = self._resolve_component_defaults(defaults)
        components = []
        for component in template.get("components", []):
            library_ref = component.get("library_ref")
            if not isinstance(library_ref, str) or not library_ref:
                raise ValueError(f"Template component '{component.get('id', '<unknown>')}' is missing a valid 'library_ref'")
            library_component = self.library_service.get(library_ref)
            merged = self._apply_component_defaults(deepcopy(component), component_defaults)
            merged_type = merged.get("type")
            if not isinstance(merged_type, str) or not merged_type or merged_type == "component":
                merged["type"] = str(library_component["category"])
            else:
                merged["type"] = merged_type
            if "io_strategy" not in merged and "io_strategy" in defaults:
                merged["io_strategy"] = defaults["io_strategy"]
            if "zone" in merged and "zone_id" not in merged:
                merged["zone_id"] = merged.pop("zone")
            merged.setdefault("x", 0.0)
            merged.setdefault("y", 0.0)
            merged.setdefault("rotation", 0.0)
            components.append(merged)
        return components

    def _resolve_component_defaults(self, defaults: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = defaults.get("component_defaults", {})
        if not isinstance(raw, dict):
            return {"all": {}, "by_type": {}, "by_zone": {}}
        all_defaults = deepcopy(raw.get("all", {})) if isinstance(raw.get("all"), dict) else {}
        by_type_raw = raw.get("by_type", {})
        by_zone_raw = raw.get("by_zone", {})
        by_type = {
            str(key): deepcopy(value)
            for key, value in by_type_raw.items()
            if isinstance(key, str) and isinstance(value, dict)
        } if isinstance(by_type_raw, dict) else {}
        by_zone = {
            str(key): deepcopy(value)
            for key, value in by_zone_raw.items()
            if isinstance(key, str) and isinstance(value, dict)
        } if isinstance(by_zone_raw, dict) else {}
        return {"all": all_defaults, "by_type": by_type, "by_zone": by_zone}

    def _apply_component_defaults(
        self,
        component: dict[str, Any],
        component_defaults: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        merged = _deep_merge({}, component_defaults.get("all", {}))
        zone_id = component.get("zone_id")
        if not isinstance(zone_id, str) and isinstance(component.get("zone"), str):
            zone_id = str(component["zone"])
        if isinstance(zone_id, str) and zone_id:
            merged = _deep_merge(merged, component_defaults.get("by_zone", {}).get(zone_id, {}))
        component_type = component.get("type")
        if isinstance(component_type, str) and component_type:
            merged = _deep_merge(merged, component_defaults.get("by_type", {}).get(component_type, {}))
        return _deep_merge(merged, component)
