from __future__ import annotations

from typing import Any

from ocw_kicad.board import _new_segment, _new_shape, _set_layer, _set_shape_type
from ocw_kicad.utils import (
    add_board_item,
    clear_generated_items,
    get_required_number,
    make_point,
    mark_generated,
    mm_to_iu,
    require_positive,
)


def render_keepouts(board: Any, keepouts: list[dict[str, Any]], pcbnew_module: Any) -> int:
    clear_generated_items(board, "keepout")

    rendered = 0
    for keepout in keepouts:
        if not isinstance(keepout, dict):
            raise ValueError(f"Invalid keepout entry: {keepout!r}")

        shape_type = keepout.get("type")
        if shape_type == "circle":
            _render_circle_keepout(board, keepout, pcbnew_module)
            rendered += 1
            continue
        if shape_type == "rect":
            _render_rect_keepout(board, keepout, pcbnew_module)
            rendered += 1
            continue

        keepout_name = keepout.get("id") or keepout.get("component_id") or "<unknown>"
        print(f"Skipping keepout {keepout_name}: invalid shape '{shape_type}'")

    return rendered


def _render_circle_keepout(board: Any, keepout: dict[str, Any], pcbnew_module: Any) -> None:
    x_mm = get_required_number(keepout, "x_mm")
    y_mm = get_required_number(keepout, "y_mm")
    diameter_mm = require_positive(get_required_number(keepout, "diameter_mm"), "diameter_mm")
    radius_mm = diameter_mm / 2.0
    layer = _get_keepout_layer(keepout)

    shape = _new_shape(board, pcbnew_module)
    _set_shape_type(shape, "circle", pcbnew_module)
    _set_layer(shape, layer, pcbnew_module)
    center = make_point(mm_to_iu(x_mm, pcbnew_module), mm_to_iu(y_mm, pcbnew_module), pcbnew_module)
    edge = make_point(mm_to_iu(x_mm + radius_mm, pcbnew_module), mm_to_iu(y_mm, pcbnew_module), pcbnew_module)
    if hasattr(shape, "SetCenter"):
        shape.SetCenter(center)
    shape.SetStart(edge)
    add_board_item(board, mark_generated(shape, "keepout"))

    keepout_name = keepout.get("id") or keepout.get("component_id") or "<unknown>"
    print(f"Created keepout for component {keepout_name}")


def _render_rect_keepout(board: Any, keepout: dict[str, Any], pcbnew_module: Any) -> None:
    x_mm = get_required_number(keepout, "x_mm")
    y_mm = get_required_number(keepout, "y_mm")
    width_mm = require_positive(get_required_number(keepout, "width_mm"), "width_mm")
    height_mm = require_positive(get_required_number(keepout, "height_mm"), "height_mm")
    layer = _get_keepout_layer(keepout)
    half_width = width_mm / 2.0
    half_height = height_mm / 2.0

    points = [
        (x_mm - half_width, y_mm - half_height),
        (x_mm + half_width, y_mm - half_height),
        (x_mm + half_width, y_mm + half_height),
        (x_mm - half_width, y_mm + half_height),
    ]
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        add_board_item(
            board,
            mark_generated(_new_segment(board, start, end, layer, pcbnew_module), "keepout"),
        )

    keepout_name = keepout.get("id") or keepout.get("component_id") or "<unknown>"
    print(f"Created keepout for component {keepout_name}")


def _get_keepout_layer(keepout: dict[str, Any]) -> str:
    layer = keepout.get("layer")
    if layer in {"F.CrtYd", "Dwgs.User"}:
        return layer
    return "F.CrtYd"
