from __future__ import annotations

import sys
import types

import pytest


def _make_fake_freecad(doc=None):
    fake_app = types.ModuleType("FreeCAD")
    fake_app.ActiveDocument = doc or object()
    fake_app.newDocument = lambda name="Controller": doc or object()
    return fake_app


def _install_mocks(fake_app, fake_wb):
    orig_app = sys.modules.get("FreeCAD")
    orig_wb = sys.modules.get("ocw_workbench.workbench")
    sys.modules["FreeCAD"] = fake_app
    sys.modules["ocw_workbench.workbench"] = fake_wb
    return orig_app, orig_wb


def _restore_mocks(orig_app, orig_wb):
    if orig_app is None:
        sys.modules.pop("FreeCAD", None)
    else:
        sys.modules["FreeCAD"] = orig_app
    if orig_wb is None:
        sys.modules.pop("ocw_workbench.workbench", None)
    else:
        sys.modules["ocw_workbench.workbench"] = orig_wb


class FakeDocument:
    Objects: list[object] = []

    def recompute(self) -> None:
        pass


@pytest.fixture()
def env():
    doc = FakeDocument()
    ensure_called: list[bool] = []
    calls: dict[str, list[object]] = {
        "place": [],
        "drag": [],
        "snap": [],
        "arrange": [],
        "transform": [],
        "toggle_overlay": [],
        "pattern_duplicate": [],
        "pattern_linear": [],
        "pattern_grid": [],
    }

    fake_app = _make_fake_freecad(doc)
    fake_wb = types.ModuleType("ocw_workbench.workbench")
    fake_wb.ensure_workbench_ui = lambda *a, **kw: ensure_called.append(True)
    fake_wb.start_place_mode_direct = lambda d, template_id: calls["place"].append((d, template_id)) or True
    fake_wb.ensure_component_palette_ui = lambda d=None: object()
    fake_wb.start_component_drag_mode_direct = lambda d: calls["drag"].append(d) or True
    fake_wb.snap_selection_to_grid_direct = lambda d: calls["snap"].append(d) or {"component_id": "enc1"}
    fake_wb.apply_selection_arrangement_direct = (
        lambda d, op: calls["arrange"].append((d, op)) or {"selected_count": 2, "moved_count": 1}
    )
    fake_wb.apply_selection_transform_direct = (
        lambda d, op: calls["transform"].append((d, op)) or {"selected_count": 2, "moved_count": 1}
    )
    fake_wb.toggle_overlay_direct = lambda d: calls["toggle_overlay"].append(d) or {"overlay_enabled": True}
    fake_wb.duplicate_selection_once_direct = (
        lambda d, offset_x, offset_y: calls["pattern_duplicate"].append((d, offset_x, offset_y)) or {"created_count": 2}
    )
    fake_wb.array_selection_linear_direct = (
        lambda d, axis, count, spacing: calls["pattern_linear"].append((d, axis, count, spacing)) or {"created_count": 3}
    )
    fake_wb.array_selection_grid_direct = (
        lambda d, rows, cols, spacing_x, spacing_y: calls["pattern_grid"].append((d, rows, cols, spacing_x, spacing_y)) or {"created_count": 3}
    )

    orig_app, orig_wb = _install_mocks(fake_app, fake_wb)
    yield doc, ensure_called, calls
    _restore_mocks(orig_app, orig_wb)


def test_add_component_uses_direct_place_mode_without_workbench(monkeypatch, env) -> None:
    doc, ensure_called, calls = env

    class FakeInteractionService:
        def __init__(self, controller_service=None) -> None:
            pass

        def get_settings(self, doc):
            return {"active_component_template_id": "omron_b3f_1000"}

    monkeypatch.setattr("ocw_workbench.commands.add_component.InteractionService", FakeInteractionService)

    from ocw_workbench.commands.add_component import AddComponentCommand

    AddComponentCommand().Activated()

    assert not ensure_called
    assert calls["place"] == [(doc, "omron_b3f_1000")]


def test_drag_move_uses_direct_drag_mode_without_workbench(env) -> None:
    doc, ensure_called, calls = env
    from ocw_workbench.commands.drag_move_component import DragMoveComponentCommand

    DragMoveComponentCommand().Activated()

    assert not ensure_called
    assert calls["drag"] == [doc]


def test_snap_uses_direct_helper_without_workbench(env) -> None:
    doc, ensure_called, calls = env
    from ocw_workbench.commands.snap_to_grid import SnapToGridCommand

    SnapToGridCommand().Activated()

    assert not ensure_called
    assert calls["snap"] == [doc]


def test_arrange_and_transform_use_direct_helpers_without_workbench(env) -> None:
    doc, ensure_called, calls = env
    from ocw_workbench.commands.align_distribute import SelectionArrangeCommand
    from ocw_workbench.commands.selection_transform import SelectionTransformCommand

    SelectionArrangeCommand("align_left").Activated()
    SelectionTransformCommand("rotate_cw_90").Activated()

    assert not ensure_called
    assert calls["arrange"] == [(doc, "align_left")]
    assert calls["transform"] == [(doc, "rotate_cw_90")]


def test_toggle_overlay_and_duplicate_use_direct_helpers_without_workbench(monkeypatch, env) -> None:
    doc, ensure_called, calls = env
    from ocw_workbench.commands.component_patterns import DuplicateSelectionCommand
    from ocw_workbench.commands.toggle_overlay import ToggleOverlayCommand

    monkeypatch.setattr("ocw_workbench.commands.component_patterns._default_duplicate_values", lambda _doc: {"offset_x": 10.0, "offset_y": 0.0})

    ToggleOverlayCommand().Activated()
    DuplicateSelectionCommand().Activated()

    assert not ensure_called
    assert calls["toggle_overlay"] == [doc]
    assert calls["pattern_duplicate"] == [(doc, 10.0, 0.0)]


def test_linear_and_grid_array_use_direct_defaults_without_workbench(monkeypatch, env) -> None:
    doc, ensure_called, calls = env
    from ocw_workbench.commands.component_patterns import GridArrayCommand, LinearArrayCommand

    monkeypatch.setattr("ocw_workbench.commands.component_patterns._default_linear_array_values", lambda _doc, axis: {"count": 3, "spacing": 24.0 if axis == "x" else 18.0})
    monkeypatch.setattr("ocw_workbench.commands.component_patterns._default_grid_array_values", lambda _doc: {"rows": 2, "cols": 2, "spacing_x": 24.0, "spacing_y": 18.0})

    LinearArrayCommand("x").Activated()
    GridArrayCommand().Activated()

    assert not ensure_called
    assert calls["pattern_linear"] == [(doc, "x", 3, 24.0)]
    assert calls["pattern_grid"] == [(doc, 2, 2, 24.0, 18.0)]
