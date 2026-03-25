from __future__ import annotations

from math import hypot
from typing import Any


def hit_test_item(item: dict[str, Any], x: float, y: float) -> bool:
    geometry = item.get("geometry", {})
    if item.get("type") == "rect":
        half_width = float(geometry["width"]) / 2.0
        half_height = float(geometry["height"]) / 2.0
        return abs(float(x) - float(geometry["x"])) <= half_width and abs(float(y) - float(geometry["y"])) <= half_height
    if item.get("type") == "circle":
        radius = float(geometry["diameter"]) / 2.0
        return hypot(float(x) - float(geometry["x"]), float(y) - float(geometry["y"])) <= radius
    return False


def hit_test_components(items: list[dict[str, Any]], x: float, y: float) -> str | None:
    for item in items:
        if item.get("source_component_id") is None:
            continue
        if item.get("id", "").startswith("component:") and hit_test_item(item, x, y):
            return item["source_component_id"]
    return None
