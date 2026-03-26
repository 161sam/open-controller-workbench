from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.generator.mechanical_resolver import MechanicalResolver


class ComponentResolver:
    def __init__(self, mechanical_resolver: MechanicalResolver | None = None) -> None:
        self.mechanical_resolver = mechanical_resolver or MechanicalResolver()

    def resolve(self, component: Any) -> dict[str, Any]:
        component_data = _component_to_dict(component)
        resolved_mechanical = self.mechanical_resolver.resolve(component)
        return {
            "id": component_data["id"],
            "type": component_data["type"],
            "x": component_data["x"],
            "y": component_data["y"],
            "rotation": float(component_data.get("rotation", 0.0) or 0.0),
            "library_ref": component_data.get("library_ref"),
            "mechanical": resolved_mechanical.to_dict(),
            "resolved_mechanical": resolved_mechanical,
        }

    def resolve_many(self, components: list[Any]) -> list[dict[str, Any]]:
        return [self.resolve(component) for component in components]


def _component_to_dict(component: Any) -> dict[str, Any]:
    if isinstance(component, dict):
        return deepcopy(component)
    if hasattr(component, "__dict__"):
        return deepcopy(vars(component))
    raise TypeError(f"Unsupported component representation: {type(component)!r}")
