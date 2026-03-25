from __future__ import annotations

from copy import deepcopy
from typing import Any


class Component:
    def __init__(
        self,
        id: str,
        type: str,
        x: float,
        y: float,
        library_ref: str | None = None,
        mechanical: dict[str, Any] | None = None,
        electrical: dict[str, Any] | None = None,
        cutout: dict[str, Any] | None = None,
        keepout_top: dict[str, Any] | None = None,
        keepout_bottom: dict[str, Any] | None = None,
        mounting: dict[str, Any] | None = None,
        io_strategy: str | None = None,
        bus: str | None = None,
        address: str | None = None,
        row: int | None = None,
        col: int | None = None,
        pins: dict[str, Any] | None = None,
        rotation: float | None = None,
        zone_id: str | None = None,
        cutout_radius: float | None = None,
    ) -> None:
        self.id = id
        self.type = type
        self.x = x
        self.y = y
        self.library_ref = library_ref
        self.mechanical = deepcopy(mechanical) if mechanical is not None else {}
        self.electrical = deepcopy(electrical) if electrical is not None else {}
        self.cutout = deepcopy(cutout)
        self.keepout_top = deepcopy(keepout_top)
        self.keepout_bottom = deepcopy(keepout_bottom)
        self.mounting = deepcopy(mounting)
        self.io_strategy = io_strategy
        self.bus = bus
        self.address = address
        self.row = row
        self.col = col
        self.pins = deepcopy(pins) if pins is not None else None
        self.rotation = rotation
        self.zone_id = zone_id
        self.cutout_radius = cutout_radius
