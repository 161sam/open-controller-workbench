from __future__ import annotations

from typing import Any

from ocw_workbench.gui.overlay.labels import constraint_detail_label, measurement_label
from ocw_workbench.gui.overlay.shapes import line_item, text_item


def measurement_items(
    item_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    current_mm: float,
    required_mm: float | None,
    style: dict[str, Any],
    label_style: dict[str, Any],
    source_ids: list[str],
    severity: str | None,
    title: str | None = None,
    include_label: bool = True,
) -> list[dict[str, Any]]:
    text = measurement_label(current_mm, required_mm) if title is None else constraint_detail_label(title, current_mm, required_mm)
    mid_x = (float(start[0]) + float(end[0])) / 2.0
    mid_y = (float(start[1]) + float(end[1])) / 2.0
    items = [
        line_item(
            item_id=item_id,
            start_x=float(start[0]),
            start_y=float(start[1]),
            end_x=float(end[0]),
            end_y=float(end[1]),
            style=style,
            label=text,
            source_ids=source_ids,
            severity=severity,
        ),
    ]
    if include_label:
        items.append(
            text_item(
                item_id=f"{item_id}:label",
                x=mid_x,
                y=mid_y,
                text=text,
                style=label_style,
                source_ids=source_ids,
                severity=severity,
            )
        )
    return items
