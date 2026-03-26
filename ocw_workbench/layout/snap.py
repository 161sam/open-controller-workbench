from __future__ import annotations


def snap_value(value: float, grid_mm: float) -> float:
    if grid_mm <= 0:
        return float(value)
    return round(round(float(value) / grid_mm) * grid_mm, 6)


def snap_point(x: float, y: float, grid_mm: float) -> tuple[float, float]:
    return snap_value(x, grid_mm), snap_value(y, grid_mm)
