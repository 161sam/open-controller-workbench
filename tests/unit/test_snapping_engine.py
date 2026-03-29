from __future__ import annotations

from ocw_workbench.gui.interaction.snapping_engine import SnapContext, compute_snap


def test_compute_snap_prefers_point_over_edge() -> None:
    context = SnapContext(
        overlay_items=(
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0},
            },
        ),
        max_snap_distance=8.0,
    )

    result = compute_snap((13.5, 13.4), context)

    assert result.snap_type == "point"
    assert result.snapped_position == (13.0, 13.0)
    assert result.target_reference == "component:btn1"


def test_compute_snap_uses_edge_when_no_point_is_close_enough() -> None:
    context = SnapContext(
        overlay_items=(
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0},
            },
        ),
        max_snap_distance=4.0,
    )

    result = compute_snap((20.2, 13.8), context)

    assert result.snap_type == "edge"
    assert result.snapped_position == (20.2, 13.0)
    assert result.target_reference == "component:btn1"


def test_compute_snap_returns_none_for_empty_scene() -> None:
    result = compute_snap((12.0, 18.0), SnapContext())

    assert result.snap_type == "none"
    assert result.snapped_position == (12.0, 18.0)
