from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_kicad.board import create_board_outline, get_or_create_board, refresh_board
from ocw_kicad.keepout_renderer import render_keepouts
from ocw_kicad.loader import load_layout
from ocw_kicad.placer import place_footprint, place_mounting_holes


def import_layout(path: str, pcbnew_module: Any = None, board: Any = None) -> Any:
    if pcbnew_module is None:
        import pcbnew as pcbnew_module

    layout = load_layout(Path(path))
    active_board = get_or_create_board(pcbnew_module, board=board)

    create_board_outline(active_board, layout["board"], pcbnew_module)
    placed_holes = place_mounting_holes(active_board, layout["mounting_holes"], pcbnew_module)

    placed_footprints = 0
    for footprint_data in layout["footprints"]:
        if not isinstance(footprint_data, dict):
            raise ValueError(f"Invalid footprint entry: {footprint_data!r}")
        footprint = place_footprint(active_board, footprint_data, pcbnew_module)
        if footprint is not None:
            placed_footprints += 1

    rendered_keepouts = render_keepouts(active_board, layout["keepouts"], pcbnew_module)

    refresh_board(pcbnew_module)
    print(
        f"Imported {placed_footprints} footprint(s), {placed_holes} mounting hole(s), "
        f"and {rendered_keepouts} keepout(s) from {path}"
    )
    return active_board


def build_roundtrip_import_descriptor(path: str | Path) -> dict[str, Any]:
    layout = load_layout(Path(path))
    roundtrip = layout.get("roundtrip", {})
    stackup = layout.get("mechanical_stackup", {})
    return {
        "layout_path": str(path),
        "import_strategy": roundtrip.get("import_strategy", "kicad_stepup_board_import"),
        "component_reference_key": roundtrip.get("component_reference_key", "component_id"),
        "coordinate_system": roundtrip.get("coordinate_system", "ocw_top_left_mm"),
        "pcb_reference": stackup.get("pcb", {}).get("reference", {}),
    }
