from __future__ import annotations

from dataclasses import dataclass

from ocw_workbench.layout.snap import snap_point


@dataclass(frozen=True)
class SnapConfig:
    grid_mm: float = 1.0
    enabled: bool = True

    def apply(self, x: float, y: float) -> tuple[float, float]:
        if not self.enabled:
            return float(x), float(y)
        return snap_point(float(x), float(y), float(self.grid_mm))
