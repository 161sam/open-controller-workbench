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
        self.surface = deepcopy(surface) if surface is not None else None
        self.mounting_holes = deepcopy(mounting_holes) if mounting_holes is not None else []
        self.reserved_zones = deepcopy(reserved_zones) if reserved_zones is not None else []
        self.layout_zones = deepcopy(layout_zones) if layout_zones is not None else []
