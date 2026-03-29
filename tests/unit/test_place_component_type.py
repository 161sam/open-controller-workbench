from __future__ import annotations

import sys
import types

import pytest

from ocw_workbench.commands.place_component_type import (
    PlaceComponentTypeCommand,
    _TYPE_DEFAULTS,
    _TYPE_ICONS,
    _TYPE_LABELS,
)

_ALL_TYPES = ("button", "encoder", "fader", "pad", "display", "rgb_button")


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

def test_all_types_have_defaults() -> None:
    for ctype in _ALL_TYPES:
        assert ctype in _TYPE_DEFAULTS, f"No default for {ctype}"
        assert _TYPE_DEFAULTS[ctype], f"Empty default for {ctype}"


def test_all_types_have_icons() -> None:
    for ctype in _ALL_TYPES:
        assert ctype in _TYPE_ICONS, f"No icon for {ctype}"
        assert _TYPE_ICONS[ctype].endswith(".svg"), f"Icon not svg for {ctype}"


def test_all_types_have_labels() -> None:
    for ctype in _ALL_TYPES:
        assert ctype in _TYPE_LABELS, f"No label for {ctype}"
        assert _TYPE_LABELS[ctype], f"Empty label for {ctype}"


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------

def test_command_stores_type_and_default_ref() -> None:
    cmd = PlaceComponentTypeCommand("button")
    assert cmd.component_type == "button"
    assert cmd.default_library_ref == _TYPE_DEFAULTS["button"]


def test_command_unknown_type_falls_back_to_type_string() -> None:
    cmd = PlaceComponentTypeCommand("mystery_widget")
    assert cmd.default_library_ref == "mystery_widget"


# ---------------------------------------------------------------------------
# GetResources
# ---------------------------------------------------------------------------

def test_get_resources_has_required_keys() -> None:
    for ctype in _ALL_TYPES:
        cmd = PlaceComponentTypeCommand(ctype)
        res = cmd.GetResources()
        assert "MenuText" in res
        assert "ToolTip" in res
        assert "Pixmap" in res


def test_get_resources_menu_text_contains_label() -> None:
    for ctype in _ALL_TYPES:
        cmd = PlaceComponentTypeCommand(ctype)
        res = cmd.GetResources()
        label = _TYPE_LABELS[ctype]
        assert label in res["MenuText"], f"{ctype}: label '{label}' not in '{res['MenuText']}'"


def test_get_resources_tooltip_references_label() -> None:
    for ctype in _ALL_TYPES:
        cmd = PlaceComponentTypeCommand(ctype)
        res = cmd.GetResources()
        label = _TYPE_LABELS[ctype]
        assert label in res["ToolTip"], f"{ctype}: label '{label}' not in '{res['ToolTip']}'"


# ---------------------------------------------------------------------------
# IsActive: no dock required — only _has_controller()
# ---------------------------------------------------------------------------

def test_is_active_false_without_controller(monkeypatch) -> None:
    cmd = PlaceComponentTypeCommand("button")
    monkeypatch.setattr(cmd, "_has_controller", lambda: False)
    assert cmd.IsActive() is False


def test_is_active_true_with_controller(monkeypatch) -> None:
    cmd = PlaceComponentTypeCommand("encoder")
    monkeypatch.setattr(cmd, "_has_controller", lambda: True)
    assert cmd.IsActive() is True


# ---------------------------------------------------------------------------
# Activated: calls start_place_mode_direct with correct template_id
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_freecad_env():
    """Inject fake FreeCAD and ocw_workbench.workbench into sys.modules."""
    fake_doc = object()

    fake_app = types.ModuleType("FreeCAD")
    fake_app.ActiveDocument = fake_doc

    fake_wb = types.ModuleType("ocw_workbench.workbench")
    calls: list[tuple] = []

    def fake_start(doc, template_id):
        calls.append((doc, template_id))
        return True

    fake_wb.start_place_mode_direct = fake_start

    orig_app = sys.modules.get("FreeCAD")
    orig_wb = sys.modules.get("ocw_workbench.workbench")
    sys.modules["FreeCAD"] = fake_app
    sys.modules["ocw_workbench.workbench"] = fake_wb

    yield fake_doc, calls

    # Restore
    if orig_app is None:
        sys.modules.pop("FreeCAD", None)
    else:
        sys.modules["FreeCAD"] = orig_app
    if orig_wb is None:
        sys.modules.pop("ocw_workbench.workbench", None)
    else:
        sys.modules["ocw_workbench.workbench"] = orig_wb


def test_activated_calls_start_place_mode_direct(fake_freecad_env) -> None:
    fake_doc, calls = fake_freecad_env
    cmd = PlaceComponentTypeCommand("fader")
    cmd.Activated()
    assert len(calls) == 1
    assert calls[0][0] is fake_doc
    assert calls[0][1] == _TYPE_DEFAULTS["fader"]


def test_activated_uses_correct_default_per_type(fake_freecad_env) -> None:
    _, calls = fake_freecad_env
    for ctype in _ALL_TYPES:
        calls.clear()
        cmd = PlaceComponentTypeCommand(ctype)
        cmd.Activated()
        assert calls, f"No call for {ctype}"
        assert calls[0][1] == _TYPE_DEFAULTS[ctype], f"{ctype}: wrong template_id"


def test_activated_does_not_call_ensure_workbench_ui(fake_freecad_env) -> None:
    ensure_called: list[bool] = []
    fake_doc, _ = fake_freecad_env
    sys.modules["ocw_workbench.workbench"].ensure_workbench_ui = (  # type: ignore[attr-defined]
        lambda *a, **kw: ensure_called.append(True)
    )

    cmd = PlaceComponentTypeCommand("pad")
    cmd.Activated()
    assert not ensure_called, "ensure_workbench_ui must NOT be called by PlaceComponentTypeCommand"
