from __future__ import annotations

from pathlib import Path
from typing import Any

from ocf_freecad.templates.models import TemplateModel
from ocf_freecad.utils.yaml_io import load_yaml


class TemplateLoader:
    def load(self, path: str | Path) -> TemplateModel:
        payload = load_yaml(path)
        return self._parse_template(payload, Path(path))

    def _parse_template(self, payload: dict[str, Any], source: Path) -> TemplateModel:
        template_meta = payload.get("template")
        if not isinstance(template_meta, dict):
            raise ValueError(f"Missing required field 'template' in {source}")

        controller = payload.get("controller")
        components = payload.get("components")
        if not isinstance(controller, dict):
            raise ValueError(f"Missing required field 'controller' in {source}")
        if not isinstance(components, list):
            raise ValueError(f"Missing required field 'components' in {source}")

        template_id = template_meta.get("id")
        name = template_meta.get("name")
        description = template_meta.get("description")
        if not isinstance(template_id, str) or not template_id:
            raise ValueError(f"Template in {source} is missing a valid 'id'")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Template '{template_id}' in {source} is missing a valid 'name'")
        if not isinstance(description, str) or not description:
            raise ValueError(f"Template '{template_id}' in {source} is missing a valid 'description'")

        zones = payload.get("zones", [])
        layout = payload.get("layout", {})
        constraints = payload.get("constraints", {})
        defaults = payload.get("defaults", {})
        firmware = payload.get("firmware", {})
        ocf = payload.get("ocf", {})
        if not isinstance(zones, list):
            raise ValueError(f"Field 'zones' must be a list in {source}")
        if not isinstance(layout, dict):
            raise ValueError(f"Field 'layout' must be a mapping in {source}")
        if not isinstance(constraints, dict):
            raise ValueError(f"Field 'constraints' must be a mapping in {source}")
        if not isinstance(defaults, dict):
            raise ValueError(f"Field 'defaults' must be a mapping in {source}")
        if not isinstance(firmware, dict):
            raise ValueError(f"Field 'firmware' must be a mapping in {source}")
        if not isinstance(ocf, dict):
            raise ValueError(f"Field 'ocf' must be a mapping in {source}")

        for component in components:
            if not isinstance(component, dict):
                raise ValueError(f"Invalid component entry in {source}: {component!r}")
            if not isinstance(component.get("id"), str) or not component["id"]:
                raise ValueError(f"Template '{template_id}' has component without valid 'id' in {source}")
            if not isinstance(component.get("type"), str) or not component["type"]:
                raise ValueError(
                    f"Template '{template_id}' component '{component.get('id', '<unknown>')}' is missing a valid 'type'"
                )
            if not isinstance(component.get("library_ref"), str) or not component["library_ref"]:
                raise ValueError(
                    f"Template '{template_id}' component '{component['id']}' is missing a valid 'library_ref'"
                )

        return TemplateModel(
            id=template_id,
            name=name,
            description=description,
            controller=controller,
            zones=zones,
            components=components,
            layout=layout,
            constraints=constraints,
            defaults=defaults,
            firmware=firmware,
            ocf=ocf,
            category=template_meta.get("category"),
            tags=template_meta.get("tags"),
            version=template_meta.get("version"),
        )
