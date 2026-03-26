from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.services.library_service import LibraryService


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class ElectricalResolver:
    def __init__(self, library_service: LibraryService | None = None) -> None:
        self.library_service = library_service or LibraryService()

    def resolve(self, component: Any) -> dict[str, Any]:
        component_data = _component_to_dict(component)
        component_id = _require_non_empty_str(component_data.get("id"), "Component is missing a valid 'id'")
        component_type = _require_non_empty_str(
            component_data.get("type"),
            f"Component '{component_id}' is missing a valid 'type'",
        )

        library_ref = component_data.get("library_ref")
        library_component: dict[str, Any] | None = None
        if library_ref is not None:
            if not isinstance(library_ref, str) or not library_ref:
                raise ValueError(f"Component '{component_id}' has an invalid library_ref")
            library_component = self.library_service.get(library_ref)

        instance_electrical = self._extract_instance_electrical(component_data)
        library_electrical = {}
        if library_component is not None:
            library_electrical = library_component.get("electrical", {})
            if not isinstance(library_electrical, dict):
                raise ValueError(f"Library component '{library_ref}' has invalid electrical defaults")

        if library_component is None and not instance_electrical:
            return {
                "component_id": component_id,
                "component_type": component_type,
                "library_ref": library_ref,
                "role": "mechanical_only",
                "electrical": {},
                "signals": [],
                "warnings": [
                    {
                        "code": "missing_electrical_definition",
                        "message": f"Component '{component_id}' has no electrical definition",
                    }
                ],
            }

        merged = _deep_merge(library_electrical, instance_electrical)
        role = self._derive_role(component_type, merged)
        signals = self._derive_signals(component_id, role, merged)
        warnings: list[dict[str, Any]] = []
        if role in {"mechanical_only", "unknown"}:
            warnings.append(
                {
                    "code": "missing_electrical_definition",
                    "message": f"Component '{component_id}' has no electrical definition",
                }
            )

        return {
            "component_id": component_id,
            "component_type": component_type,
            "library_ref": library_ref,
            "role": role,
            "electrical": merged,
            "signals": signals,
            "warnings": warnings,
        }

    def _extract_instance_electrical(self, component_data: dict[str, Any]) -> dict[str, Any]:
        electrical = component_data.get("electrical")
        if electrical is None:
            result: dict[str, Any] = {}
        elif isinstance(electrical, dict):
            result = deepcopy(electrical)
        else:
            raise ValueError(
                f"Electrical overrides for component '{component_data.get('id', '<unknown>')}' must be a mapping"
            )

        for field in ("io_strategy", "bus", "address", "row", "col", "pins"):
            value = component_data.get(field)
            if value is not None:
                result[field] = deepcopy(value)
        return result

    def _derive_role(self, component_type: str, electrical: dict[str, Any]) -> str:
        electrical_type = electrical.get("type")
        if electrical_type == "incremental_encoder":
            return "incremental_encoder"
        if electrical_type == "momentary_switch":
            return "momentary_switch"
        if electrical_type == "oled_display":
            return "oled_display"
        if electrical_type == "connector":
            return "connector"
        if electrical_type is None:
            if component_type in {"encoder", "button", "display"}:
                return "unknown"
            return "mechanical_only"
        return "unknown"

    def _derive_signals(self, component_id: str, role: str, electrical: dict[str, Any]) -> list[dict[str, Any]]:
        if role == "incremental_encoder":
            return [
                _signal(component_id, "a", "input"),
                _signal(component_id, "b", "input"),
                _signal(component_id, "common", "reference"),
            ]
        if role == "momentary_switch":
            return [
                _signal(component_id, "switch_a", "input"),
                _signal(component_id, "switch_b", "reference"),
            ]
        if role == "oled_display":
            signals = [
                _signal(component_id, "vcc", "power"),
                _signal(component_id, "gnd", "ground"),
                _signal(component_id, "sda", "bus"),
                _signal(component_id, "scl", "bus"),
            ]
            pins = electrical.get("pins", [])
            if isinstance(pins, list) and "RST" in pins:
                signals.append(_signal(component_id, "rst", "control"))
            return signals
        return []


def _signal(component_id: str, name: str, signal_type: str) -> dict[str, Any]:
    return {
        "id": f"{component_id}.{name}",
        "name": name,
        "signal_type": signal_type,
        "net_name": f"{component_id}.{name}",
    }


def _component_to_dict(component: Any) -> dict[str, Any]:
    if isinstance(component, dict):
        return deepcopy(component)
    if hasattr(component, "__dict__"):
        return deepcopy(vars(component))
    raise TypeError(f"Unsupported component representation: {type(component)!r}")


def _require_non_empty_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(message)
    return value
