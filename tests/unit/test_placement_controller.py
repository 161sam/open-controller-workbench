from __future__ import annotations

import sys
import types

from ocw_workbench.gui.interaction.placement_controller import PlacementController
from ocw_workbench.gui.interaction.tool_manager import reset_tool_manager


def test_placement_controller_uses_direct_place_helper() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    calls: list[tuple[object, str]] = []
    fake_workbench.start_place_mode_direct = lambda doc, template_id: calls.append((doc, template_id)) or True
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        controller = PlacementController()
        doc = object()
        assert controller.start_component_placement(doc, "generic_mpc_pad_30mm") is True
    finally:
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original

    assert calls == [(doc, "generic_mpc_pad_30mm")]


def test_placement_controller_uses_direct_move_helper() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    calls: list[object] = []
    fake_workbench.start_component_drag_mode_direct = lambda doc: calls.append(doc) or True
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        controller = PlacementController()
        doc = object()
        assert controller.start_move_mode(doc) is True
    finally:
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original

    assert calls == [doc]


def test_placement_controller_tracks_active_tool_for_direct_place() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    fake_workbench.start_place_mode_direct = lambda doc, template_id: True
    fake_workbench.cancel_active_tool = lambda doc=None: None
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        tools = reset_tool_manager()
        controller = PlacementController()
        doc = object()
        assert controller.start_component_placement(doc, "generic_mpc_pad_30mm") is True
        assert tools.current_tool == "place:generic_mpc_pad_30mm"
    finally:
        reset_tool_manager()
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original


def test_placement_controller_switches_tools_through_manager() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    cancel_calls: list[object] = []
    fake_workbench.start_place_mode_direct = lambda doc, template_id: True
    fake_workbench.start_component_drag_mode_direct = lambda doc: True
    fake_workbench.cancel_active_tool = lambda doc=None: cancel_calls.append(doc)
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        tools = reset_tool_manager()
        controller = PlacementController()
        doc = object()
        assert controller.start_component_placement(doc, "generic_mpc_pad_30mm") is True
        assert controller.start_move_mode(doc) is True
        assert cancel_calls == [doc]
        assert tools.current_tool == "drag"
    finally:
        reset_tool_manager()
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original


def test_placement_controller_exposes_current_tool_context() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    fake_workbench.start_place_mode_direct = lambda doc, template_id: True
    fake_workbench.cancel_active_tool = lambda doc=None: None
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        reset_tool_manager()
        controller = PlacementController()
        doc = object()
        assert controller.start_component_placement(doc, "generic_mpc_pad_30mm") is True
        assert controller.current_tool_context() == {
            "doc": doc,
            "template_id": "generic_mpc_pad_30mm",
        }
    finally:
        reset_tool_manager()
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original


def test_placement_controller_escape_cancels_active_tool() -> None:
    fake_workbench = types.ModuleType("ocw_workbench.workbench")
    cancel_calls: list[object] = []
    fake_workbench.start_place_mode_direct = lambda doc, template_id: True
    fake_workbench.cancel_active_tool = lambda doc=None: cancel_calls.append(doc)
    original = sys.modules.get("ocw_workbench.workbench")
    sys.modules["ocw_workbench.workbench"] = fake_workbench
    try:
        tools = reset_tool_manager()
        controller = PlacementController()
        doc = object()
        assert controller.start_component_placement(doc, "generic_mpc_pad_30mm") is True
        assert controller.handle_key("ESCAPE") is True
        assert cancel_calls == [doc]
        assert tools.current_tool is None
    finally:
        reset_tool_manager()
        if original is None:
            sys.modules.pop("ocw_workbench.workbench", None)
        else:
            sys.modules["ocw_workbench.workbench"] = original
