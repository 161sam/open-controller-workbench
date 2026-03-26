from __future__ import annotations

from copy import deepcopy
from typing import Any


class Controller:
    def __init__(
        self,
        id,
        width,
        depth,
        height,
        top_thickness,
        wall_thickness: float = 3.0,
        bottom_thickness: float = 3.0,
        lid_inset: float = 1.5,
        inner_clearance: float = 0.35,
        surface: dict[str, Any] | None = None,
        mounting_holes: list[dict[str, Any]] | None = None,
        reserved_zones: list[dict[str, Any]] | None = None,
        layout_zones: list[dict[str, Any]] | None = None,
    ):
        self.id = id
        self.width = width
        self.depth = depth
        self.height = height
        self.top_thickness = top_thickness
        self.wall_thickness = wall_thickness
        self.bottom_thickness = bottom_thickness
        self.lid_inset = lid_inset
        self.inner_clearance = inner_clearance
        self.surface = deepcopy(surface) if surface is not None else None
        self.mounting_holes = deepcopy(mounting_holes) if mounting_holes is not None else []
        self.reserved_zones = deepcopy(reserved_zones) if reserved_zones is not None else []
        self.layout_zones = deepcopy(layout_zones) if layout_zones is not None else []
