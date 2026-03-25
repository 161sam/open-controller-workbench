from __future__ import annotations

from pathlib import Path
from typing import Any

from ocf_kicad.board import get_or_create_board, refresh_board
from ocf_kicad.loader import load_layout
from ocf_kicad.placer import place_footprint


def import_layout(path: str, pcbnew_module: Any = None, board: Any = None) -> Any:
    if pcbnew_module is None:
        import pcbnew as pcbnew_module

    layout = load_layout(Path(path))
    active_board = get_or_create_board(pcbnew_module, board=board)

    placed_count = 0
    for footprint_data in layout["footprints"]:
        if not isinstance(footprint_data, dict):
            raise ValueError(f"Invalid footprint entry: {footprint_data!r}")
        footprint = place_footprint(active_board, footprint_data, pcbnew_module)
        if footprint is not None:
            placed_count += 1

    refresh_board(pcbnew_module)
    print(f"Imported {placed_count} footprint(s) from {path}")
    return active_board
