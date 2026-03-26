from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_zone(controller: dict[str, Any], zone_id: str | None) -> dict[str, float]:
    surface = controller.get("surface")
    width = float(surface["width"]) if isinstance(surface, dict) and "width" in surface else float(controller["width"])
    height = float(surface["height"]) if isinstance(surface, dict) and "height" in surface else float(controller["depth"])

    if zone_id is None:
        return {"id": None, "x": 0.0, "y": 0.0, "width": width, "height": height}

    for zone in controller.get("layout_zones", []):
        if isinstance(zone, dict) and zone.get("id") == zone_id:
            return {
                "id": zone_id,
                "x": float(zone["x"]),
                "y": float(zone["y"]),
                "width": float(zone["width"]),
                "height": float(zone["height"]),
            }
    raise ValueError(f"Unknown layout zone: {zone_id}")


def inject_zone(controller: dict[str, Any], zone: dict[str, float]) -> dict[str, Any]:
    scoped = deepcopy(controller)
    scoped["mounting_holes"] = [
        hole
        for hole in scoped.get("mounting_holes", [])
        if _hole_inside_zone(hole, zone)
    ]
    return scoped


def _hole_inside_zone(hole: dict[str, Any], zone: dict[str, float]) -> bool:
    x = float(hole["x"])
    y = float(hole["y"])
    return zone["x"] <= x <= zone["x"] + zone["width"] and zone["y"] <= y <= zone["y"] + zone["height"]
