from __future__ import annotations

from copy import deepcopy
from typing import Any


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class TemplateResolver:
    def resolve(self, template: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        if overrides is None:
            return deepcopy(template)
        if not isinstance(overrides, dict):
            raise ValueError("Template overrides must be a mapping")

        resolved = deepcopy(template)
        for field in ("template", "controller", "layout", "constraints", "defaults", "firmware", "ocf"):
            if field in overrides:
                if not isinstance(overrides[field], dict):
                    raise ValueError(f"Template override field '{field}' must be a mapping")
                resolved[field] = _deep_merge(resolved.get(field, {}), overrides[field])

        if "zones" in overrides:
            if not isinstance(overrides["zones"], list):
                raise ValueError("Template override field 'zones' must be a list")
            resolved["zones"] = deepcopy(overrides["zones"])

        if "components" in overrides:
            if not isinstance(overrides["components"], dict):
                raise ValueError("Template override field 'components' must be a mapping")
            resolved["components"] = self._merge_components(resolved["components"], overrides["components"])

        return resolved

    def _merge_components(
        self,
        base_components: list[dict[str, Any]],
        component_overrides: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = [deepcopy(component) for component in base_components]
        by_id = {component["id"]: component for component in result}

        remove_ids = component_overrides.get("remove_ids", [])
        if remove_ids:
            if not isinstance(remove_ids, list):
                raise ValueError("Template component override 'remove_ids' must be a list")
            result = [component for component in result if component["id"] not in remove_ids]
            by_id = {component["id"]: component for component in result}

        update_items = component_overrides.get("update", {})
        if update_items:
            if not isinstance(update_items, dict):
                raise ValueError("Template component override 'update' must be a mapping")
            for component_id, override in update_items.items():
                if component_id not in by_id:
                    raise ValueError(f"Cannot override unknown template component '{component_id}'")
                if not isinstance(override, dict):
                    raise ValueError(f"Override for template component '{component_id}' must be a mapping")
                merged = _deep_merge(by_id[component_id], override)
                index = next(i for i, item in enumerate(result) if item["id"] == component_id)
                result[index] = merged
                by_id[component_id] = merged

        add_items = component_overrides.get("add", [])
        if add_items:
            if not isinstance(add_items, list):
                raise ValueError("Template component override 'add' must be a list")
            for component in add_items:
                if not isinstance(component, dict):
                    raise ValueError(f"Invalid template component add entry: {component!r}")
                result.append(deepcopy(component))

        return result
