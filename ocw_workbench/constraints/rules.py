from __future__ import annotations

from copy import deepcopy
from math import hypot
from typing import Any

from ocw_workbench.constraints.models import ComponentArea, ConstraintFinding
from ocw_workbench.geometry.planar import rotated_rect_bounding_box, rotated_rect_points
from ocw_workbench.geometry.primitives import SurfacePrimitive

DEFAULT_CONSTRAINTS = {
    "min_component_spacing_mm": 6.0,
    "min_keepout_spacing_mm": 2.0,
    "min_cutout_spacing_mm": 2.0,
    "default_edge_distance_mm": 4.0,
    "edge_distance_by_type_mm": {
        "encoder": 8.0,
        "fader": 10.0,
        "display": 6.0,
    },
    "mounting_hole_clearance_mm": 2.0,
    "ergonomic": {
        "min_control_spacing_mm": 18.0,
        "fader_button_spacing_mm": 25.0,
        "display_tall_control_spacing_mm": 20.0,
        "tall_control_types": ["encoder", "rgb_button", "fader"],
    },
}


def merge_constraint_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONSTRAINTS)
    if overrides is None:
        return config
    return _deep_merge(config, overrides)


def validate_inside_surface(
    surface: SurfacePrimitive,
    area: ComponentArea,
    rule_id: str,
    feature_name: str,
) -> ConstraintFinding | None:
    for point in _feature_points(area):
        if not point_inside_surface(surface, point[0], point[1]):
            return ConstraintFinding(
                severity="error",
                rule_id=rule_id,
                message=f"{feature_name} for component '{area.component_id}' leaves the controller surface",
                source_component=area.component_id,
                details={"feature": feature_name, "point": [point[0], point[1]]},
            )
    return None


def validate_edge_distance(
    surface: SurfacePrimitive,
    area: ComponentArea,
    min_distance_mm: float,
) -> ConstraintFinding | None:
    distance = min_distance_to_surface_edge(surface, area)
    if distance < min_distance_mm:
        return ConstraintFinding(
            severity="error",
            rule_id="edge_distance",
            message=(
                f"Component '{area.component_id}' is too close to the outer edge "
                f"({distance:.2f} mm < {min_distance_mm:.2f} mm)"
            ),
            source_component=area.component_id,
            details={"distance_mm": round(distance, 3), "required_mm": min_distance_mm},
        )
    return None


def validate_spacing(
    first: ComponentArea,
    second: ComponentArea,
    min_spacing_mm: float,
    rule_id: str,
    label: str,
) -> ConstraintFinding | None:
    gap = minimum_gap(first, second)
    if gap < min_spacing_mm:
        return ConstraintFinding(
            severity="error",
            rule_id=rule_id,
            message=(
                f"{label} for components '{first.component_id}' and '{second.component_id}' "
                f"violates minimum spacing ({gap:.2f} mm < {min_spacing_mm:.2f} mm)"
            ),
            source_component=first.component_id,
            affected_component=second.component_id,
            details={"gap_mm": round(gap, 3), "required_mm": min_spacing_mm},
        )
    return None


def validate_mounting_hole_overlap(
    area: ComponentArea,
    mounting_hole: dict[str, Any],
    clearance_mm: float,
) -> ConstraintFinding | None:
    hole_area = ComponentArea(
        component_id=str(mounting_hole.get("id", "mounting_hole")),
        component_type="mounting_hole",
        x=float(mounting_hole["x"]),
        y=float(mounting_hole["y"]),
        shape="circle",
        diameter=float(mounting_hole["diameter"]) + (2.0 * clearance_mm),
    )
    gap = minimum_gap(area, hole_area)
    if gap < 0:
        return ConstraintFinding(
            severity="error",
            rule_id="mounting_hole_clearance",
            message=f"Component '{area.component_id}' overlaps mounting hole '{hole_area.component_id}'",
            source_component=area.component_id,
            affected_component=hole_area.component_id,
            details={"gap_mm": round(gap, 3), "clearance_mm": clearance_mm},
        )
    return None


def point_inside_surface(surface: SurfacePrimitive, x: float, y: float) -> bool:
    if surface.shape == "rectangle":
        return 0 <= x <= surface.width and 0 <= y <= surface.height
    if surface.shape == "rounded_rect":
        if not (0 <= x <= surface.width and 0 <= y <= surface.height):
            return False
        radius = min(surface.corner_radius or 0.0, surface.width / 2.0, surface.height / 2.0)
        if radius <= 0:
            return True
        inner_x_min = radius
        inner_x_max = surface.width - radius
        inner_y_min = radius
        inner_y_max = surface.height - radius
        if inner_x_min <= x <= inner_x_max or inner_y_min <= y <= inner_y_max:
            return True
        centers = [
            (radius, radius),
            (surface.width - radius, radius),
            (radius, surface.height - radius),
            (surface.width - radius, surface.height - radius),
        ]
        return any(hypot(x - cx, y - cy) <= radius for cx, cy in centers)
    if surface.shape == "polygon":
        return _point_in_polygon(x, y, surface.points or ())
    raise ValueError(f"Unsupported controller surface shape: {surface.shape}")


def minimum_gap(first: ComponentArea, second: ComponentArea) -> float:
    first_box = _bounding_box(first)
    second_box = _bounding_box(second)
    dx = max(first_box["left"] - second_box["right"], second_box["left"] - first_box["right"], 0.0)
    dy = max(first_box["bottom"] - second_box["top"], second_box["bottom"] - first_box["top"], 0.0)
    if dx == 0.0 and dy == 0.0:
        overlap_x = min(first_box["right"], second_box["right"]) - max(first_box["left"], second_box["left"])
        overlap_y = min(first_box["top"], second_box["top"]) - max(first_box["bottom"], second_box["bottom"])
        return -min(overlap_x, overlap_y)
    return hypot(dx, dy)


def min_distance_to_surface_edge(surface: SurfacePrimitive, area: ComponentArea) -> float:
    points = _feature_points(area)
    if surface.shape in {"rectangle", "rounded_rect"}:
        distances = [
            min(point[0], point[1], surface.width - point[0], surface.height - point[1])
            for point in points
        ]
        return min(distances)
    if surface.shape == "polygon":
        return min(_distance_to_polygon_edges(point[0], point[1], surface.points or ()) for point in points)
    raise ValueError(f"Unsupported controller surface shape: {surface.shape}")


def _bounding_box(area: ComponentArea) -> dict[str, float]:
    if area.shape == "circle":
        radius = (area.diameter or 0.0) / 2.0
        return {
            "left": area.x - radius,
            "right": area.x + radius,
            "bottom": area.y - radius,
            "top": area.y + radius,
        }
    return rotated_rect_bounding_box(
        center_x=area.x,
        center_y=area.y,
        width=float(area.width or 0.0),
        height=float(area.height or 0.0),
        rotation_deg=area.rotation,
    )


def _feature_points(area: ComponentArea) -> list[tuple[float, float]]:
    if area.shape == "circle":
        box = _bounding_box(area)
        return [
            (box["left"], box["bottom"]),
            (box["left"], box["top"]),
            (box["right"], box["bottom"]),
            (box["right"], box["top"]),
        ]
    return rotated_rect_points(
        center_x=area.x,
        center_y=area.y,
        width=float(area.width or 0.0),
        height=float(area.height or 0.0),
        rotation_deg=area.rotation,
    )


def _distance_to_polygon_edges(x: float, y: float, points: tuple[tuple[float, float], ...]) -> float:
    if len(points) < 2:
        return 0.0
    distances = []
    point_list = list(points)
    if point_list[0] != point_list[-1]:
        point_list.append(point_list[0])
    for start, end in zip(point_list, point_list[1:]):
        distances.append(_distance_to_segment(x, y, start, end))
    return min(distances)


def _distance_to_segment(
    x: float,
    y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return hypot(x - sx, y - sy)
    t = max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / ((dx * dx) + (dy * dy))))
    px = sx + t * dx
    py = sy + t * dy
    return hypot(x - px, y - py)


def _point_in_polygon(x: float, y: float, points: tuple[tuple[float, float], ...]) -> bool:
    point_list = list(points)
    if len(point_list) < 3:
        return False
    inside = False
    j = len(point_list) - 1
    for i in range(len(point_list)):
        xi, yi = point_list[i]
        xj, yj = point_list[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
