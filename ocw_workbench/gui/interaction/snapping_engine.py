from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class SnapResult:
    snapped_position: tuple[float, float]
    snap_type: str
    target_reference: str | None
    distance: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": self.snap_type,
            "x": float(self.snapped_position[0]),
            "y": float(self.snapped_position[1]),
            "target_reference": self.target_reference,
            "distance": round(float(self.distance), 6),
        }


@dataclass(frozen=True)
class SnapContext:
    overlay_items: tuple[dict[str, Any], ...] = ()
    max_snap_distance: float = 6.0


def compute_snap(position: tuple[float, float], context: SnapContext) -> SnapResult:
    x = float(position[0])
    y = float(position[1])
    point_candidate: SnapResult | None = None
    edge_candidate: SnapResult | None = None
    for item in context.overlay_items:
        item_id = str(item.get("id") or "")
        if item_id.startswith("preview_"):
            continue
        point_candidate = _pick_closer(point_candidate, _point_snap_for_item(x, y, item, context.max_snap_distance))
        edge_candidate = _pick_closer(edge_candidate, _edge_snap_for_item(x, y, item, context.max_snap_distance))
    if point_candidate is not None:
        return point_candidate
    if edge_candidate is not None:
        return edge_candidate
    return SnapResult(snapped_position=(x, y), snap_type="none", target_reference=None, distance=math.inf)


def _pick_closer(current: SnapResult | None, candidate: SnapResult | None) -> SnapResult | None:
    if candidate is None:
        return current
    if current is None or candidate.distance < current.distance:
        return candidate
    return current


def _point_snap_for_item(x: float, y: float, item: dict[str, Any], max_distance: float) -> SnapResult | None:
    best: SnapResult | None = None
    for point in _point_candidates(item):
        distance = math.dist((x, y), point)
        if distance > max_distance:
            continue
        candidate = SnapResult(
            snapped_position=point,
            snap_type="point",
            target_reference=str(item.get("id") or ""),
            distance=distance,
        )
        best = _pick_closer(best, candidate)
    return best


def _edge_snap_for_item(x: float, y: float, item: dict[str, Any], max_distance: float) -> SnapResult | None:
    best: SnapResult | None = None
    for start, end in _edge_candidates(item):
        projected = _project_point_to_segment((x, y), start, end)
        distance = math.dist((x, y), projected)
        if distance > max_distance:
            continue
        candidate = SnapResult(
            snapped_position=projected,
            snap_type="edge",
            target_reference=str(item.get("id") or ""),
            distance=distance,
        )
        best = _pick_closer(best, candidate)
    return best


def _point_candidates(item: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = item.get("geometry")
    if not isinstance(geometry, dict):
        return []
    item_type = str(item.get("type") or "")
    if item_type in {"rect", "slot"}:
        x = float(geometry.get("x", 0.0))
        y = float(geometry.get("y", 0.0))
        width = float(geometry.get("width", 0.0))
        height = float(geometry.get("height", 0.0))
        half_w = width / 2.0
        half_h = height / 2.0
        return [
            (x - half_w, y - half_h),
            (x + half_w, y - half_h),
            (x + half_w, y + half_h),
            (x - half_w, y + half_h),
            (x, y),
        ]
    if item_type == "circle":
        return [(float(geometry.get("x", 0.0)), float(geometry.get("y", 0.0)))]
    if item_type == "line":
        return [
            (float(geometry.get("start_x", 0.0)), float(geometry.get("start_y", 0.0))),
            (float(geometry.get("end_x", 0.0)), float(geometry.get("end_y", 0.0))),
        ]
    return []


def _edge_candidates(item: dict[str, Any]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    geometry = item.get("geometry")
    if not isinstance(geometry, dict):
        return []
    item_type = str(item.get("type") or "")
    if item_type in {"rect", "slot"}:
        x = float(geometry.get("x", 0.0))
        y = float(geometry.get("y", 0.0))
        width = float(geometry.get("width", 0.0))
        height = float(geometry.get("height", 0.0))
        half_w = width / 2.0
        half_h = height / 2.0
        top_left = (x - half_w, y + half_h)
        top_right = (x + half_w, y + half_h)
        bottom_left = (x - half_w, y - half_h)
        bottom_right = (x + half_w, y - half_h)
        return [
            (bottom_left, bottom_right),
            (bottom_right, top_right),
            (top_right, top_left),
            (top_left, bottom_left),
        ]
    if item_type == "line":
        return [
            (
                (float(geometry.get("start_x", 0.0)), float(geometry.get("start_y", 0.0))),
                (float(geometry.get("end_x", 0.0)), float(geometry.get("end_y", 0.0))),
            )
        ]
    return []


def _project_point_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return start
    t = ((px - sx) * dx + (py - sy) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return (sx + dx * t, sy + dy * t)
