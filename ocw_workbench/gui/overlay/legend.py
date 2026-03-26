from __future__ import annotations

from typing import Any

from ocw_workbench.gui.overlay.shapes import text_item


def build_legend_items(
    settings: dict[str, Any],
    style: dict[str, Any],
    error_count: int,
    warning_count: int,
) -> list[dict[str, Any]]:
    lines = [
        f"Err {error_count} | Warn {warning_count}",
        f"Meas {'on' if settings.get('measurements_enabled', True) else 'off'}",
        f"Lines {'on' if settings.get('conflict_lines_enabled', True) else 'off'}",
        f"Labels {'on' if settings.get('constraint_labels_enabled', True) else 'off'}",
    ]
    items: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        items.append(
            text_item(
                item_id=f"legend:{index}",
                x=10.0,
                y=12.0 + (index * 4.0),
                text=line,
                style=style,
            )
        )
    return items
