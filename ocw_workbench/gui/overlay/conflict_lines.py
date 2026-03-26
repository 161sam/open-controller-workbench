from __future__ import annotations

from typing import Any

from ocw_workbench.gui.overlay.shapes import line_item, text_item


def conflict_items(
    item_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str,
    style: dict[str, Any],
    label_style: dict[str, Any],
    source_ids: list[str],
    severity: str,
    include_label: bool = True,
) -> list[dict[str, Any]]:
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
            label=label,
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
                text=label,
                style=label_style,
                source_ids=source_ids,
                severity=severity,
            )
        )
    return items
