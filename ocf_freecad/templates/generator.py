from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.services.library_service import LibraryService
from ocf_freecad.templates.registry import TemplateRegistry
from ocf_freecad.templates.resolver import TemplateResolver


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
        if resolved.get("variant"):
            project["variant"] = deepcopy(resolved["variant"])
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
            "mounting_holes": deepcopy(controller_data.get("mounting_holes", [])),
            "reserved_zones": deepcopy(controller_data.get("reserved_zones", [])),
            "layout_zones": deepcopy(template.get("zones", [])),
        }
        controller["surface"] = {
            "shape": surface_shape,
            "width": width,
            "height": height,
        }
        if "corner_radius" in surface:
            controller["surface"]["corner_radius"] = float(surface["corner_radius"])
        if "points" in surface:
            controller["surface"]["points"] = deepcopy(surface["points"])
        return controller

    def _build_components(self, template: dict[str, Any]) -> list[dict[str, Any]]:
        defaults = deepcopy(template.get("defaults", {}))
        components = []
        for component in template.get("components", []):
            library_ref = component.get("library_ref")
            if not isinstance(library_ref, str) or not library_ref:
                raise ValueError(f"Template component '{component.get('id', '<unknown>')}' is missing a valid 'library_ref'")
            self.library_service.get(library_ref)
            merged = deepcopy(component)
            if "io_strategy" not in merged and "io_strategy" in defaults:
                merged["io_strategy"] = defaults["io_strategy"]
            if "zone" in merged and "zone_id" not in merged:
                merged["zone_id"] = merged.pop("zone")
            merged.setdefault("x", 0.0)
            merged.setdefault("y", 0.0)
            merged.setdefault("rotation", 0.0)
            components.append(merged)
        return components
