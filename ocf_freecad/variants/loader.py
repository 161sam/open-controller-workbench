from __future__ import annotations

from pathlib import Path
from typing import Any

from ocf_freecad.utils.yaml_io import load_yaml
from ocf_freecad.variants.models import VariantModel

_COMPONENT_OVERRIDE_OPERATIONS = {"add", "replace", "remove", "update", "remove_ids"}


class VariantLoader:
    def load(self, path: str | Path) -> VariantModel:
        payload = load_yaml(path)
        return self._parse_variant(payload, Path(path))

    def _parse_variant(self, payload: dict[str, Any], source: Path) -> VariantModel:
        variant_meta = payload.get("variant")
        overrides = payload.get("overrides", {})
        if not isinstance(variant_meta, dict):
            raise ValueError(f"Missing required field 'variant' in {source}")
        if not isinstance(overrides, dict):
            raise ValueError(f"Field 'overrides' must be a mapping in {source}")

        variant_id = variant_meta.get("id")
        name = variant_meta.get("name")
        description = variant_meta.get("description")
        template_id = variant_meta.get("template_id")

        if not isinstance(variant_id, str) or not variant_id:
            raise ValueError(f"Variant in {source} is missing a valid 'id'")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Variant '{variant_id}' in {source} is missing a valid 'name'")
        if not isinstance(description, str) or not description:
            raise ValueError(f"Variant '{variant_id}' in {source} is missing a valid 'description'")
        if not isinstance(template_id, str) or not template_id:
            raise ValueError(f"Variant '{variant_id}' in {source} is missing a valid 'template_id'")

        self._validate_overrides(variant_id, overrides, source)

        return VariantModel(
            id=variant_id,
            name=name,
            description=description,
            template_id=template_id,
            overrides=overrides,
            category=variant_meta.get("category"),
            tags=variant_meta.get("tags"),
            version=variant_meta.get("version"),
        )

    def _validate_overrides(self, variant_id: str, overrides: dict[str, Any], source: Path) -> None:
        mapping_fields = {"controller", "layout", "constraints", "defaults", "firmware", "ocf"}
        for field in mapping_fields:
            if field in overrides and not isinstance(overrides[field], dict):
                raise ValueError(f"Variant '{variant_id}' override field '{field}' must be a mapping in {source}")

        zones = overrides.get("zones")
        if zones is not None and not isinstance(zones, list):
            raise ValueError(f"Variant '{variant_id}' override field 'zones' must be a list in {source}")

        components = overrides.get("components")
        if components is None:
            return
        if not isinstance(components, dict):
            raise ValueError(f"Variant '{variant_id}' override field 'components' must be a mapping in {source}")

        unknown_operations = sorted(set(components) - _COMPONENT_OVERRIDE_OPERATIONS)
        if unknown_operations:
            raise ValueError(
                f"Variant '{variant_id}' in {source} has unknown component override operations: {', '.join(unknown_operations)}"
            )

        add_items = components.get("add", [])
        if add_items:
            if not isinstance(add_items, list):
                raise ValueError(f"Variant '{variant_id}' component override 'add' must be a list in {source}")
            for component in add_items:
                self._validate_full_component(variant_id, component, source, context="add")

        replace_items = components.get("replace", [])
        if replace_items:
            if not isinstance(replace_items, list):
                raise ValueError(f"Variant '{variant_id}' component override 'replace' must be a list in {source}")
            for item in replace_items:
                if not isinstance(item, dict):
                    raise ValueError(f"Variant '{variant_id}' has invalid replace entry in {source}: {item!r}")
                match_id = item.get("match_id")
                replacement = item.get("with")
                if not isinstance(match_id, str) or not match_id:
                    raise ValueError(f"Variant '{variant_id}' replace entry is missing a valid 'match_id' in {source}")
                self._validate_full_component(variant_id, replacement, source, context=f"replace '{match_id}'")

        remove_items = components.get("remove", [])
        if remove_items:
            if not isinstance(remove_items, list):
                raise ValueError(f"Variant '{variant_id}' component override 'remove' must be a list in {source}")
            for item in remove_items:
                if not isinstance(item, dict):
                    raise ValueError(f"Variant '{variant_id}' has invalid remove entry in {source}: {item!r}")
                match_id = item.get("match_id")
                if not isinstance(match_id, str) or not match_id:
                    raise ValueError(f"Variant '{variant_id}' remove entry is missing a valid 'match_id' in {source}")

        update_items = components.get("update", {})
        if update_items:
            if not isinstance(update_items, dict):
                raise ValueError(f"Variant '{variant_id}' component override 'update' must be a mapping in {source}")
            for component_id, override in update_items.items():
                if not isinstance(component_id, str) or not component_id:
                    raise ValueError(f"Variant '{variant_id}' has invalid component id in 'update' in {source}")
                if not isinstance(override, dict):
                    raise ValueError(
                        f"Variant '{variant_id}' component override for '{component_id}' must be a mapping in {source}"
                    )

        remove_ids = components.get("remove_ids", [])
        if remove_ids:
            if not isinstance(remove_ids, list) or any(not isinstance(item, str) or not item for item in remove_ids):
                raise ValueError(f"Variant '{variant_id}' component override 'remove_ids' must be a list of ids in {source}")

    def _validate_full_component(
        self,
        variant_id: str,
        component: Any,
        source: Path,
        context: str,
    ) -> None:
        if not isinstance(component, dict):
            raise ValueError(f"Variant '{variant_id}' has invalid component override in {context} in {source}: {component!r}")
        for field in ("id", "type", "library_ref"):
            value = component.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"Variant '{variant_id}' component override in {context} is missing a valid '{field}' in {source}"
                )
