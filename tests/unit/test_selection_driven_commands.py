from __future__ import annotations

import sys
import types

from ocw_workbench.commands.align_distribute import SelectionArrangeCommand
from ocw_workbench.commands.component_patterns import (
    _default_duplicate_values,
    _default_grid_array_values,
    _default_linear_array_values,
)
from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
from ocw_workbench.services.controller_service import ControllerService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0
        self.transactions = []

    def recompute(self) -> None:
        self.recompute_count += 1

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


def test_pattern_defaults_follow_selection_span_and_grid():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=40.0, y=25.0)
    state = service.get_state(doc)
    state["meta"]["ui"]["grid_mm"] = 5.0
    service.save_state(doc, state)
    service.set_selected_component_ids(doc, ["btn1", "btn2"], primary_id="btn1")

    duplicate = _default_duplicate_values(doc)
    linear = _default_linear_array_values(doc, "x")
    grid = _default_grid_array_values(doc)

    assert duplicate == {"offset_x": 50.0, "offset_y": 0.0}
    assert linear == {"count": 3, "spacing": 50.0}
    assert grid == {"rows": 2, "cols": 2, "spacing_x": 50.0, "spacing_y": 35.0}


def test_arrange_commands_require_real_multi_selection():
    align = SelectionArrangeCommand("align_left")
    distribute = SelectionArrangeCommand("distribute_horizontal")

    original_selection_count = SelectionArrangeCommand._selection_count
    SelectionArrangeCommand._selection_count = staticmethod(lambda: 2)
    try:
        assert align.IsActive() is True
        assert distribute.IsActive() is False
    finally:
        SelectionArrangeCommand._selection_count = original_selection_count

    SelectionArrangeCommand._selection_count = staticmethod(lambda: 3)
    try:
        assert distribute.IsActive() is True
    finally:
        SelectionArrangeCommand._selection_count = original_selection_count


def test_validate_constraints_makes_overlay_visible(monkeypatch):
    doc = FakeDocument()
    fake_app = types.ModuleType("FreeCAD")
    fake_app.ActiveDocument = doc
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    overlay_calls: list[tuple[object, bool]] = []
    refresh_calls: list[object] = []
    fake_workbench.ensure_constraint_overlay_visible_direct = lambda current_doc, visible=True: overlay_calls.append((current_doc, visible)) or {"show_constraints": visible}
    fake_workbench._refresh_active_workbench_if_open = lambda current_doc: refresh_calls.append(current_doc)

    class FakeControllerService:
        def validate_layout(self, current_doc):
            assert current_doc is doc
            return {"summary": {"error_count": 1, "warning_count": 2}}

    messages: list[tuple[str, str]] = []
    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerService", FakeControllerService)
    monkeypatch.setattr("ocw_workbench.commands.validate_constraints.show_info", lambda title, message: messages.append((title, message)))
    monkeypatch.setattr("ocw_workbench.commands.validate_constraints.show_error", lambda title, exc: (_ for _ in ()).throw(exc))
    original_app = sys.modules.get("FreeCAD")
    original_workbench = sys.modules.get("ocw_workbench.workbench")
    sys.modules["FreeCAD"] = fake_app
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        ValidateConstraintsCommand().Activated()
    finally:
        if original_app is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = original_app
        if original_workbench is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original_workbench

    assert overlay_calls == [(doc, True)]
    assert refresh_calls == [doc]
    assert messages == [("Validate Layout", "1 error(s), 2 warning(s). Issues are visible directly in the 3D overlay.")]
