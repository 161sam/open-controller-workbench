from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.geometry.normalize import normalize_mechanical
from ocf_freecad.geometry.primitives import ResolvedMechanical
from ocf_freecad.services.library_service import LibraryService


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class MechanicalResolver:
    def __init__(self, library_service: LibraryService | None = None) -> None:
        self.library_service = library_service or LibraryService()

    def resolve(self, component: Any) -> ResolvedMechanical:
        component_data = _component_to_dict(component)
        component_id = _require_str(component_data.get("id"), "Component is missing a valid 'id'")
        component_type = _require_str(
            component_data.get("type"),
            f"Component '{component_id}' is missing a valid 'type'",
        )

        library_ref = component_data.get("library_ref")
        library_component: dict[str, Any] | None = None
        if library_ref is not None:
            if not isinstance(library_ref, str) or not library_ref:
                raise ValueError(f"Component '{component_id}' has an invalid library_ref")
            library_component = self.library_service.get(library_ref)

        instance_mechanical = self._extract_instance_mechanical(component_data)
        if library_component is None and not instance_mechanical:
            raise ValueError(
                f"Missing library_ref or mechanical overrides for component '{component_id}'"
            )

        base_mechanical = {}
        if library_component is not None:
            base_mechanical = deepcopy(library_component.get("mechanical", {}))
            if not isinstance(base_mechanical, dict):
                raise ValueError(
                    f"Library component '{library_ref}' has invalid mechanical defaults"
                )

        merged_mechanical = _deep_merge(base_mechanical, instance_mechanical)
        return normalize_mechanical(
            component_type=component_type,
            mechanical=merged_mechanical,
            component_id=component_id,
        )

    def _extract_instance_mechanical(self, component_data: dict[str, Any]) -> dict[str, Any]:
        mechanical = component_data.get("mechanical")
        if mechanical is None:
            result: dict[str, Any] = {}
        elif isinstance(mechanical, dict):
            result = deepcopy(mechanical)
        else:
            raise ValueError(
                f"Mechanical overrides for component '{component_data.get('id', '<unknown>')}' must be a mapping"
            )

        for field in ("cutout", "keepout_top", "keepout_bottom", "mounting"):
            value = component_data.get(field)
            if value is not None:
                result[field] = deepcopy(value)

        cutout_radius = component_data.get("cutout_radius")
        if cutout_radius is not None and "cutout" not in result:
            if not isinstance(cutout_radius, (int, float)) or cutout_radius <= 0:
                raise ValueError(
                    f"Component '{component_data.get('id', '<unknown>')}' has an invalid cutout_radius"
                )
            result["cutout"] = {
                "shape": "circle",
                "diameter": float(cutout_radius) * 2.0,
            }

        return result


def _component_to_dict(component: Any) -> dict[str, Any]:
    if isinstance(component, dict):
        return deepcopy(component)
    if hasattr(component, "__dict__"):
        return deepcopy(vars(component))
    raise TypeError(f"Unsupported component representation: {type(component)!r}")


def _require_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(message)
    return value
