from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.plugins.data import normalize_template_payload
from ocw_workbench.templates.models import TemplateModel
from ocw_workbench.utils.yaml_io import load_yaml


class TemplateLoader:
    def load(self, path: str | Path, plugin_id: str | None = None) -> TemplateModel:
        payload = load_yaml(path)
        return self.load_payload(payload, source=Path(path), plugin_id=plugin_id)

    def load_payload(
        self,
        payload: dict[str, Any],
        source: str | Path,
        plugin_id: str | None = None,
    ) -> TemplateModel:
        return self._parse_template(payload, Path(source), plugin_id=plugin_id)

    def _parse_template(self, payload: dict[str, Any], source: Path, plugin_id: str | None = None) -> TemplateModel:
        if "template" not in payload:
            if plugin_id is None:
                raise ValueError(f"Missing required field 'template' in {source}")
            payload = normalize_template_payload(payload, source, plugin_id)
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
        metadata = payload.get("metadata", {})
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
        if not isinstance(metadata, dict):
            raise ValueError(f"Field 'metadata' must be a mapping in {source}")
        geometry = controller.get("geometry", {})
        if geometry is not None and not isinstance(geometry, dict):
            raise ValueError(f"Field 'controller.geometry' must be a mapping in {source}")
        if isinstance(geometry, dict):
            self._validate_geometry(geometry, source)

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
            metadata=metadata,
            category=template_meta.get("category"),
            tags=template_meta.get("tags"),
            version=template_meta.get("version"),
        )

    def _validate_geometry(self, geometry: dict[str, Any], source: Path) -> None:
        base = geometry.get("base")
        if base is None:
            return
        if not isinstance(base, dict):
            raise ValueError(f"Field 'controller.geometry.base' must be a mapping in {source}")
        base_type = base.get("type")
        if base_type != "custom_fcstd":
            raise ValueError(f"Unsupported controller.geometry.base type '{base_type}' in {source}")
        for field in ("filename", "target_ref"):
            value = base.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"custom_fcstd base geometry is missing a valid '{field}' in {source}")
        if "origin" in base and not isinstance(base.get("origin"), dict):
            raise ValueError(f"custom_fcstd base geometry origin must be a mapping in {source}")
