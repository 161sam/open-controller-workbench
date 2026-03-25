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
        cutout: dict[str, Any] | None = None,
        keepout_top: dict[str, Any] | None = None,
        keepout_bottom: dict[str, Any] | None = None,
        mounting: dict[str, Any] | None = None,
        cutout_radius: float | None = None,
    ) -> None:
        self.id = id
        self.type = type
        self.x = x
        self.y = y
        self.library_ref = library_ref
        self.mechanical = deepcopy(mechanical) if mechanical is not None else {}
        self.cutout = deepcopy(cutout)
        self.keepout_top = deepcopy(keepout_top)
        self.keepout_bottom = deepcopy(keepout_bottom)
        self.mounting = deepcopy(mounting)
        self.cutout_radius = cutout_radius
