from __future__ import annotations

from typing import Any

from ocw_kicad.utils import (
    add_board_item,
    clear_generated_items,
    get_optional_number,
    get_required_number,
    make_point,
    mark_generated,
    mm_to_iu,
    require_non_negative,
    require_positive,
)


def get_or_create_board(pcbnew_module: Any, board: Any = None) -> Any:
    if board is not None:
        return board

    if hasattr(pcbnew_module, "GetBoard"):
        existing = pcbnew_module.GetBoard()
        if existing is not None:
            return existing

    if hasattr(pcbnew_module, "BOARD"):
        return pcbnew_module.BOARD()

    raise RuntimeError("Unable to create or obtain pcbnew board instance")


def refresh_board(pcbnew_module: Any) -> None:
    if hasattr(pcbnew_module, "Refresh"):
        pcbnew_module.Refresh()


def create_board_outline(board: Any, board_data: dict[str, Any], pcbnew_module: Any) -> None:
    width_mm = require_positive(get_required_number(board_data, "width_mm"), "width_mm")
    height_mm = require_positive(get_required_number(board_data, "height_mm"), "height_mm")
    corner_radius_mm = get_optional_number(board_data, "corner_radius_mm", 0.0) or 0.0
    require_non_negative(corner_radius_mm, "corner_radius_mm")

    clear_generated_items(board, "outline")

    if corner_radius_mm > 0:
        radius_mm = min(corner_radius_mm, width_mm / 2.0, height_mm / 2.0)
        _create_rounded_rectangle_outline(board, width_mm, height_mm, radius_mm, pcbnew_module)
    else:
        _create_rectangle_outline(board, width_mm, height_mm, pcbnew_module)

    print("Board outline created")


def _create_rectangle_outline(board: Any, width_mm: float, height_mm: float, pcbnew_module: Any) -> None:
    points = [(0.0, 0.0), (width_mm, 0.0), (width_mm, height_mm), (0.0, height_mm)]
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        add_board_item(
            board,
            mark_generated(_new_segment(board, start, end, "Edge.Cuts", pcbnew_module), "outline"),
        )


def _create_rounded_rectangle_outline(
    board: Any,
    width_mm: float,
    height_mm: float,
    radius_mm: float,
    pcbnew_module: Any,
) -> None:
    segments = [
        ((radius_mm, 0.0), (width_mm - radius_mm, 0.0)),
        ((width_mm, radius_mm), (width_mm, height_mm - radius_mm)),
        ((width_mm - radius_mm, height_mm), (radius_mm, height_mm)),
        ((0.0, height_mm - radius_mm), (0.0, radius_mm)),
    ]
    for start, end in segments:
        add_board_item(
            board,
            mark_generated(_new_segment(board, start, end, "Edge.Cuts", pcbnew_module), "outline"),
        )

    if _supports_arcs(pcbnew_module):
        arcs = [
            ((width_mm - radius_mm, radius_mm), (width_mm, radius_mm), 90.0),
            ((width_mm - radius_mm, height_mm - radius_mm), (width_mm - radius_mm, height_mm), 90.0),
            ((radius_mm, height_mm - radius_mm), (0.0, height_mm - radius_mm), 90.0),
            ((radius_mm, radius_mm), (radius_mm, 0.0), 90.0),
        ]
        for center, start, angle_deg in arcs:
            add_board_item(
                board,
                mark_generated(_new_arc(board, center, start, angle_deg, "Edge.Cuts", pcbnew_module), "outline"),
            )
    else:
        corners = [
            ((width_mm - radius_mm, 0.0), (width_mm, radius_mm)),
            ((width_mm, height_mm - radius_mm), (width_mm - radius_mm, height_mm)),
            ((radius_mm, height_mm), (0.0, height_mm - radius_mm)),
            ((0.0, radius_mm), (radius_mm, 0.0)),
        ]
        for start, end in corners:
            add_board_item(
                board,
                mark_generated(_new_segment(board, start, end, "Edge.Cuts", pcbnew_module), "outline"),
            )


def _new_segment(
    board: Any,
    start_mm: tuple[float, float],
    end_mm: tuple[float, float],
    layer: str,
    pcbnew_module: Any,
) -> Any:
    shape = _new_shape(board, pcbnew_module)
    _set_shape_type(shape, "segment", pcbnew_module)
    _set_layer(shape, layer, pcbnew_module)
    shape.SetStart(make_point(mm_to_iu(start_mm[0], pcbnew_module), mm_to_iu(start_mm[1], pcbnew_module), pcbnew_module))
    shape.SetEnd(make_point(mm_to_iu(end_mm[0], pcbnew_module), mm_to_iu(end_mm[1], pcbnew_module), pcbnew_module))
    return shape


def _new_arc(
    board: Any,
    center_mm: tuple[float, float],
    start_mm: tuple[float, float],
    angle_deg: float,
    layer: str,
    pcbnew_module: Any,
) -> Any:
    shape = _new_shape(board, pcbnew_module)
    _set_shape_type(shape, "arc", pcbnew_module)
    _set_layer(shape, layer, pcbnew_module)
    if hasattr(shape, "SetCenter"):
        shape.SetCenter(
            make_point(mm_to_iu(center_mm[0], pcbnew_module), mm_to_iu(center_mm[1], pcbnew_module), pcbnew_module)
        )
    shape.SetStart(make_point(mm_to_iu(start_mm[0], pcbnew_module), mm_to_iu(start_mm[1], pcbnew_module), pcbnew_module))
    if hasattr(shape, "SetArcAngleAndEnd"):
        shape.SetArcAngleAndEnd(angle_deg)
    elif hasattr(shape, "SetAngle"):
        shape.SetAngle(angle_deg)
    return shape


def _new_shape(board: Any, pcbnew_module: Any) -> Any:
    if hasattr(pcbnew_module, "PCB_SHAPE"):
        return pcbnew_module.PCB_SHAPE(board)
    raise RuntimeError("pcbnew module does not provide PCB_SHAPE")


def _set_shape_type(shape: Any, shape_name: str, pcbnew_module: Any) -> None:
    mapping = {
        "segment": getattr(pcbnew_module, "SHAPE_T_SEGMENT", "segment"),
        "arc": getattr(pcbnew_module, "SHAPE_T_ARC", "arc"),
        "circle": getattr(pcbnew_module, "SHAPE_T_CIRCLE", "circle"),
        "rect": getattr(pcbnew_module, "SHAPE_T_RECT", "rect"),
    }
    if hasattr(shape, "SetShape"):
        shape.SetShape(mapping[shape_name])


def _set_layer(shape: Any, layer_name: str, pcbnew_module: Any) -> None:
    layer_mapping = {
        "Edge.Cuts": getattr(pcbnew_module, "Edge_Cuts", "Edge.Cuts"),
        "Dwgs.User": getattr(pcbnew_module, "Dwgs_User", "Dwgs.User"),
        "F.CrtYd": getattr(pcbnew_module, "F_CrtYd", "F.CrtYd"),
    }
    if hasattr(shape, "SetLayer"):
        shape.SetLayer(layer_mapping[layer_name])


def _supports_arcs(pcbnew_module: Any) -> bool:
    return hasattr(pcbnew_module, "SHAPE_T_ARC")
