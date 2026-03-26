from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConstraintFinding:
    severity: str
    rule_id: str
    message: str
    source_component: str | None = None
    affected_component: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "severity": self.severity,
            "rule_id": self.rule_id,
            "message": self.message,
            "source_component": self.source_component,
            "affected_component": self.affected_component,
        }
        if self.details is not None:
            data["details"] = self.details
        return data


@dataclass(frozen=True)
class ComponentArea:
    component_id: str
    component_type: str
    x: float
    y: float
    shape: str
    rotation: float = 0.0
    width: float | None = None
    height: float | None = None
    diameter: float | None = None
    depth: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "x": self.x,
            "y": self.y,
            "shape": self.shape,
            "rotation": self.rotation,
        }
        if self.width is not None:
            data["width"] = self.width
        if self.height is not None:
            data["height"] = self.height
        if self.diameter is not None:
            data["diameter"] = self.diameter
        if self.depth is not None:
            data["depth"] = self.depth
        return data
