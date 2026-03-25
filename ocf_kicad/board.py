from __future__ import annotations

from typing import Any


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
