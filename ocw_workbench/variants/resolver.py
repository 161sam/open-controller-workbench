from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.templates.registry import TemplateRegistry


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class VariantResolver:
    def __init__(self, template_registry: TemplateRegistry | None = None) -> None:
        self.template_registry = template_registry or TemplateRegistry()

    def resolve(
        self,
        variant: dict[str, Any],
        runtime_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        variant_meta = variant.get("variant", {})
        variant_id = variant_meta.get("id", "<unknown>")
        template_id = variant_meta.get("template_id")
        if not isinstance(template_id, str) or not template_id:
            raise ValueError(f"Variant '{variant_id}' is missing a valid 'template_id'")

        try:
            resolved = self.template_registry.get_template(template_id)
        except KeyError as exc:
            raise KeyError(f"Unknown template id for variant '{variant_id}': {template_id}") from exc

        resolved = self._apply_overrides(resolved, variant.get("overrides"), context=f"variant '{variant_id}'")
        resolved = self._apply_overrides(resolved, runtime_overrides, context=f"runtime overrides for '{variant_id}'")
        resolved["variant"] = deepcopy(variant_meta)
        return resolved

    def _apply_overrides(
        self,
        template: dict[str, Any],
        overrides: dict[str, Any] | None,
        context: str,
    ) -> dict[str, Any]:
        if overrides is None:
            return deepcopy(template)
        if not isinstance(overrides, dict):
            raise ValueError(f"{context} must be a mapping")

        resolved = deepcopy(template)
        for field in ("template", "controller", "layout", "constraints", "defaults", "firmware", "ocf"):
            if field in overrides:
                if not isinstance(overrides[field], dict):
                    raise ValueError(f"Override field '{field}' in {context} must be a mapping")
                resolved[field] = _deep_merge(resolved.get(field, {}), overrides[field])

        if "zones" in overrides:
            if not isinstance(overrides["zones"], list):
                raise ValueError(f"Override field 'zones' in {context} must be a list")
            resolved["zones"] = deepcopy(overrides["zones"])

        if "components" in overrides:
            if not isinstance(overrides["components"], dict):
                raise ValueError(f"Override field 'components' in {context} must be a mapping")
            resolved["components"] = self._merge_components(
                resolved.get("components", []),
                overrides["components"],
                context=context,
            )

        return resolved

    def _merge_components(
        self,
        base_components: list[dict[str, Any]],
        operations: dict[str, Any],
        context: str,
    ) -> list[dict[str, Any]]:
        result = [deepcopy(component) for component in base_components]
        by_id = {component["id"]: component for component in result}

        remove_ids = operations.get("remove_ids", [])
        if remove_ids:
            if not isinstance(remove_ids, list):
                raise ValueError(f"Component override 'remove_ids' in {context} must be a list")
            for component_id in remove_ids:
                if component_id not in by_id:
                    raise ValueError(f"Remove target not found: {component_id}")
                result = [component for component in result if component["id"] != component_id]
                by_id.pop(component_id, None)

        remove_items = operations.get("remove", [])
        if remove_items:
            if not isinstance(remove_items, list):
                raise ValueError(f"Component override 'remove' in {context} must be a list")
            for item in remove_items:
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid remove entry in {context}: {item!r}")
                match_id = item.get("match_id")
                if not isinstance(match_id, str) or not match_id:
                    raise ValueError(f"Remove entry in {context} is missing a valid 'match_id'")
                if match_id not in by_id:
                    raise ValueError(f"Remove target not found: {match_id}")
                result = [component for component in result if component["id"] != match_id]
                by_id.pop(match_id, None)

        replace_items = operations.get("replace", [])
        if replace_items:
            if not isinstance(replace_items, list):
                raise ValueError(f"Component override 'replace' in {context} must be a list")
            for item in replace_items:
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid replace entry in {context}: {item!r}")
                match_id = item.get("match_id")
                replacement = item.get("with")
                if not isinstance(match_id, str) or not match_id:
                    raise ValueError(f"Replace entry in {context} is missing a valid 'match_id'")
                if match_id not in by_id:
                    raise ValueError(f"Replace target not found: {match_id}")
                validated_replacement = self._validate_full_component(replacement, context=context)
                index = next(i for i, component in enumerate(result) if component["id"] == match_id)
                result[index] = validated_replacement
                by_id.pop(match_id, None)
                by_id[validated_replacement["id"]] = validated_replacement

        update_items = operations.get("update", {})
        if update_items:
            if not isinstance(update_items, dict):
                raise ValueError(f"Component override 'update' in {context} must be a mapping")
            for component_id, override in update_items.items():
                if component_id not in by_id:
                    raise ValueError(f"Update target not found: {component_id}")
                if not isinstance(override, dict):
                    raise ValueError(f"Component override for '{component_id}' in {context} must be a mapping")
                updated = _deep_merge(by_id[component_id], override)
                index = next(i for i, component in enumerate(result) if component["id"] == component_id)
                result[index] = updated
                by_id[component_id] = updated

        add_items = operations.get("add", [])
        if add_items:
            if not isinstance(add_items, list):
                raise ValueError(f"Component override 'add' in {context} must be a list")
            for item in add_items:
                component = self._validate_full_component(item, context=context)
                component_id = component["id"]
                if component_id in by_id:
                    raise ValueError(f"Component id already exists: {component_id}")
                result.append(component)
                by_id[component_id] = component

        return result

    def _validate_full_component(self, component: Any, context: str) -> dict[str, Any]:
        if not isinstance(component, dict):
            raise ValueError(f"Invalid component override in {context}: {component!r}")
        validated = deepcopy(component)
        for field in ("id", "type", "library_ref"):
            value = validated.get(field)
            if not isinstance(value, str) or not value:
                if field == "library_ref":
                    raise ValueError(f"Added component missing library_ref: {validated.get('id', '<unknown>')}")
                raise ValueError(f"Invalid component override missing '{field}' in {context}")
        return validated
