from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Placement:
    component_id: str
    x: float
    y: float
    rotation: float = 0.0
    zone_id: str | None = None

    def to_dict(self) -> dict:
        data = {
            "component_id": self.component_id,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
        }
        if self.zone_id is not None:
            data["zone_id"] = self.zone_id
        return data
