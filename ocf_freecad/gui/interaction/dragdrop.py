from __future__ import annotations

from dataclasses import dataclass

from ocf_freecad.gui.interaction.snap import SnapConfig


@dataclass
class DragSession:
    component_id: str
    start_x: float
    start_y: float
    target_x: float
    target_y: float


def begin_drag(component_id: str, x: float, y: float) -> DragSession:
    return DragSession(component_id=component_id, start_x=float(x), start_y=float(y), target_x=float(x), target_y=float(y))


def update_drag(session: DragSession, x: float, y: float, snap_config: SnapConfig) -> DragSession:
    target_x, target_y = snap_config.apply(x, y)
    session.target_x = target_x
    session.target_y = target_y
    return session
