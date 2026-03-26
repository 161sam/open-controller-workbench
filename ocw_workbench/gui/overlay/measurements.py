from __future__ import annotations

from math import hypot
from typing import Any


def bbox_from_shape(x: float, y: float, shape: dict[str, Any]) -> dict[str, float]:
    if shape.get("shape") == "circle":
        radius = float(shape["diameter"]) / 2.0
        return {
            "left": float(x) - radius,
            "right": float(x) + radius,
            "bottom": float(y) - radius,
            "top": float(y) + radius,
            "center_x": float(x),
            "center_y": float(y),
            "width": radius * 2.0,
            "height": radius * 2.0,
        }
    half_width = float(shape["width"]) / 2.0
    half_height = float(shape["height"]) / 2.0
    return {
        "left": float(x) - half_width,
        "right": float(x) + half_width,
        "bottom": float(y) - half_height,
        "top": float(y) + half_height,
        "center_x": float(x),
        "center_y": float(y),
        "width": half_width * 2.0,
        "height": half_height * 2.0,
    }


def nearest_points_between_boxes(first: dict[str, float], second: dict[str, float]) -> tuple[tuple[float, float], tuple[float, float], float]:
    dx = 0.0
    start_x = first["center_x"]
    end_x = second["center_x"]
    if first["right"] < second["left"]:
        start_x = first["right"]
        end_x = second["left"]
        dx = second["left"] - first["right"]
    elif second["right"] < first["left"]:
        start_x = first["left"]
        end_x = second["right"]
        dx = first["left"] - second["right"]
    else:
        overlap_left = max(first["left"], second["left"])
        overlap_right = min(first["right"], second["right"])
        shared_x = (overlap_left + overlap_right) / 2.0
        start_x = shared_x
        end_x = shared_x
        dx = -min(first["right"], second["right"]) + max(first["left"], second["left"])

    dy = 0.0
    start_y = first["center_y"]
    end_y = second["center_y"]
    if first["top"] < second["bottom"]:
        start_y = first["top"]
        end_y = second["bottom"]
        dy = second["bottom"] - first["top"]
    elif second["top"] < first["bottom"]:
        start_y = first["bottom"]
        end_y = second["top"]
        dy = first["bottom"] - second["top"]
    else:
        overlap_bottom = max(first["bottom"], second["bottom"])
        overlap_top = min(first["top"], second["top"])
        shared_y = (overlap_bottom + overlap_top) / 2.0
        start_y = shared_y
        end_y = shared_y
        dy = -min(first["top"], second["top"]) + max(first["bottom"], second["bottom"])

    if dx <= 0.0 and dy <= 0.0:
        overlap_x = min(first["right"], second["right"]) - max(first["left"], second["left"])
        overlap_y = min(first["top"], second["top"]) - max(first["bottom"], second["bottom"])
        gap = -min(overlap_x, overlap_y)
    else:
        gap = hypot(max(dx, 0.0), max(dy, 0.0))
    return (start_x, start_y), (end_x, end_y), round(gap, 3)


def nearest_edge_measurement(surface: dict[str, Any], bbox: dict[str, float]) -> dict[str, float | str]:
    distances = {
        "left": bbox["left"],
        "right": float(surface["width"]) - bbox["right"],
        "bottom": bbox["bottom"],
        "top": float(surface["height"]) - bbox["top"],
    }
    edge = min(distances, key=distances.get)
    if edge == "left":
        return {
            "edge": edge,
            "distance": distances[edge],
            "start_x": bbox["left"],
            "start_y": bbox["center_y"],
            "end_x": 0.0,
            "end_y": bbox["center_y"],
        }
    if edge == "right":
        return {
            "edge": edge,
            "distance": distances[edge],
            "start_x": bbox["right"],
            "start_y": bbox["center_y"],
            "end_x": float(surface["width"]),
            "end_y": bbox["center_y"],
        }
    if edge == "bottom":
        return {
            "edge": edge,
            "distance": distances[edge],
            "start_x": bbox["center_x"],
            "start_y": bbox["bottom"],
            "end_x": bbox["center_x"],
            "end_y": 0.0,
        }
    return {
        "edge": edge,
        "distance": distances[edge],
        "start_x": bbox["center_x"],
        "start_y": bbox["top"],
        "end_x": bbox["center_x"],
        "end_y": float(surface["height"]),
    }


def expanded_shape(shape: dict[str, Any], clearance_mm: float) -> dict[str, Any]:
    if shape.get("shape") == "circle":
        return {"shape": "circle", "diameter": float(shape["diameter"]) + (2.0 * clearance_mm)}
    return {
        "shape": "rect",
        "width": float(shape["width"]) + (2.0 * clearance_mm),
        "height": float(shape["height"]) + (2.0 * clearance_mm),
    }


def midpoint(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    return ((float(start[0]) + float(end[0])) / 2.0, (float(start[1]) + float(end[1])) / 2.0)
