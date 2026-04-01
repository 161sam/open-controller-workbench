from __future__ import annotations

from math import hypot
from typing import Any

from ocw_workbench.geometry.planar import point_in_rotated_rect, point_in_rotated_slot


def hit_test_item(item: dict[str, Any], x: float, y: float) -> bool:
    geometry = item.get("geometry", {})
    if item.get("type") == "rect":
        return point_in_rotated_rect(
            float(x),
            float(y),
            center_x=float(geometry["x"]),
            center_y=float(geometry["y"]),
            width=float(geometry["width"]),
            height=float(geometry["height"]),
            rotation_deg=float(geometry.get("rotation", 0.0) or 0.0),
        )
    if item.get("type") == "slot":
        return point_in_rotated_slot(
            float(x),
            float(y),
            center_x=float(geometry["x"]),
            center_y=float(geometry["y"]),
            width=float(geometry["width"]),
            height=float(geometry["height"]),
            rotation_deg=float(geometry.get("rotation", 0.0) or 0.0),
        )
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


def hit_test_inline_handle(items: list[dict[str, Any]], x: float, y: float) -> dict[str, Any] | None:
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id.startswith("inline_handle:"):
            continue
        if hit_test_item(item, x, y):
            return item
    return None


def hit_test_inline_action(items: list[dict[str, Any]], x: float, y: float) -> dict[str, Any] | None:
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id.startswith("inline_action:"):
            continue
        if hit_test_item(item, x, y):
            return item
    return None
