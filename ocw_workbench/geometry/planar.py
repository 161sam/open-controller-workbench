from __future__ import annotations

from math import cos, radians, sin


def normalize_rotation(rotation_deg: float | None) -> float:
    return float(rotation_deg or 0.0) % 360.0


def rotate_point(
    x: float,
    y: float,
    center_x: float,
    center_y: float,
    rotation_deg: float | None,
) -> tuple[float, float]:
    angle = normalize_rotation(rotation_deg)
    if angle == 0.0:
        return float(x), float(y)
    theta = radians(angle)
    dx = float(x) - float(center_x)
    dy = float(y) - float(center_y)
    return (
        float(center_x) + (dx * cos(theta)) - (dy * sin(theta)),
        float(center_y) + (dx * sin(theta)) + (dy * cos(theta)),
    )


def rotated_rect_points(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    rotation_deg: float | None,
) -> list[tuple[float, float]]:
    half_width = float(width) / 2.0
    half_height = float(height) / 2.0
    corners = [
        (float(center_x) - half_width, float(center_y) - half_height),
        (float(center_x) - half_width, float(center_y) + half_height),
        (float(center_x) + half_width, float(center_y) - half_height),
        (float(center_x) + half_width, float(center_y) + half_height),
    ]
    return [
        rotate_point(corner_x, corner_y, center_x, center_y, rotation_deg)
        for corner_x, corner_y in corners
    ]


def rotated_rect_bounding_box(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    rotation_deg: float | None,
) -> dict[str, float]:
    points = rotated_rect_points(center_x, center_y, width, height, rotation_deg)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "left": min(xs),
        "right": max(xs),
        "bottom": min(ys),
        "top": max(ys),
    }


def point_in_rotated_rect(
    x: float,
    y: float,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    rotation_deg: float | None,
) -> bool:
    local_x, local_y = rotate_point(x, y, center_x, center_y, -(rotation_deg or 0.0))
    half_width = float(width) / 2.0
    half_height = float(height) / 2.0
    return (
        abs(local_x - float(center_x)) <= half_width
        and abs(local_y - float(center_y)) <= half_height
    )


def point_in_rotated_slot(
    x: float,
    y: float,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    rotation_deg: float | None,
) -> bool:
    local_x, local_y = rotate_point(x, y, center_x, center_y, -(rotation_deg or 0.0))
    dx = float(local_x) - float(center_x)
    dy = float(local_y) - float(center_y)
    major = max(float(width), float(height))
    minor = min(float(width), float(height))
    radius = minor / 2.0
    half_major = major / 2.0
    center_offset = max(0.0, half_major - radius)
    if abs(dy) <= radius and abs(dx) <= center_offset:
        return True
    left_dx = dx + center_offset
    right_dx = dx - center_offset
    return (left_dx * left_dx) + (dy * dy) <= radius * radius or (right_dx * right_dx) + (dy * dy) <= radius * radius
