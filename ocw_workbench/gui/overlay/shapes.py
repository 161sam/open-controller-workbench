from __future__ import annotations

from typing import Any


def rect_item(
    item_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    style: dict[str, Any],
    rotation: float = 0.0,
    label: str | None = None,
    source_component_id: str | None = None,
    severity: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "rect",
        "geometry": {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "rotation": float(rotation),
        },
        "style": style,
        "label": label,
        "source_component_id": source_component_id,
        "source_ids": list(source_ids or ([] if source_component_id is None else [source_component_id])),
        "severity": severity,
    }


def slot_item(
    item_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    style: dict[str, Any],
    rotation: float = 0.0,
    label: str | None = None,
    source_component_id: str | None = None,
    severity: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "slot",
        "geometry": {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "rotation": float(rotation),
        },
        "style": style,
        "label": label,
        "source_component_id": source_component_id,
        "source_ids": list(source_ids or ([] if source_component_id is None else [source_component_id])),
        "severity": severity,
    }


def circle_item(
    item_id: str,
    x: float,
    y: float,
    diameter: float,
    style: dict[str, Any],
    label: str | None = None,
    source_component_id: str | None = None,
    severity: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "circle",
        "geometry": {"x": float(x), "y": float(y), "diameter": float(diameter)},
        "style": style,
        "label": label,
        "source_component_id": source_component_id,
        "source_ids": list(source_ids or ([] if source_component_id is None else [source_component_id])),
        "severity": severity,
    }


def text_item(
    item_id: str,
    x: float,
    y: float,
    text: str,
    style: dict[str, Any],
    source_component_id: str | None = None,
    severity: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "text_marker",
        "geometry": {"x": float(x), "y": float(y)},
        "style": style,
        "label": text,
        "source_component_id": source_component_id,
        "source_ids": list(source_ids or ([] if source_component_id is None else [source_component_id])),
        "severity": severity,
    }


def line_item(
    item_id: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    style: dict[str, Any],
    label: str | None = None,
    source_component_id: str | None = None,
    severity: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "line",
        "geometry": {
            "start_x": float(start_x),
            "start_y": float(start_y),
            "end_x": float(end_x),
            "end_y": float(end_y),
        },
        "style": style,
        "label": label,
        "source_component_id": source_component_id,
        "source_ids": list(source_ids or ([] if source_component_id is None else [source_component_id])),
        "severity": severity,
    }
