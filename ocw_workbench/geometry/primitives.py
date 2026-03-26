from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SurfacePrimitive:
    shape: str
    width: float
    height: float
    corner_radius: float | None = None
    points: tuple[tuple[float, float], ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "shape": self.shape,
            "width": self.width,
            "height": self.height,
        }
        if self.corner_radius is not None:
            data["corner_radius"] = self.corner_radius
        if self.points is not None:
            data["points"] = [[x, y] for x, y in self.points]
        return data


@dataclass(frozen=True)
class BoxPrimitive:
    width: float
    depth: float
    height: float


@dataclass(frozen=True)
class CylinderPrimitive:
    radius: float
    height: float


@dataclass(frozen=True)
class ShapePrimitive:
    shape: str
    width: float | None = None
    height: float | None = None
    diameter: float | None = None
    depth: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"shape": self.shape}
        if self.width is not None:
            data["width"] = self.width
        if self.height is not None:
            data["height"] = self.height
        if self.diameter is not None:
            data["diameter"] = self.diameter
        if self.depth is not None:
            data["depth"] = self.depth
        return data


@dataclass(frozen=True)
class ResolvedMechanical:
    cutout: ShapePrimitive
    keepout_top: ShapePrimitive
    keepout_bottom: ShapePrimitive
    mounting: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "cutout": self.cutout.to_dict(),
            "keepout_top": self.keepout_top.to_dict(),
            "keepout_bottom": self.keepout_bottom.to_dict(),
        }
        if self.mounting is not None:
            data["mounting"] = self.mounting
        return data


@dataclass(frozen=True)
class Cutout:
    x: float
    y: float
    shape: ShapePrimitive

    def to_dict(self) -> dict[str, Any]:
        data = {
            "x": self.x,
            "y": self.y,
        }
        data.update(self.shape.to_dict())
        return data
