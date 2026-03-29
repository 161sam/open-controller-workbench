"""Package B: ApplyLayout and ValidateConstraints call services directly.

These tests verify that neither command calls ensure_workbench_ui() and that
both delegate to ControllerService without requiring an open dock.
"""
from __future__ import annotations

import sys
import types

import pytest

from ocw_workbench.services.controller_service import ControllerService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_fake_freecad(doc=None):
    fake_app = types.ModuleType("FreeCAD")
    fake_app.ActiveDocument = doc or object()
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.transactions: list[tuple] = []

    def recompute(self) -> None:
        pass

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


@pytest.fixture()
def real_doc():
    return FakeDocument()


@pytest.fixture()
def env(real_doc):
    """Patch FreeCAD + workbench module; track ensure_workbench_ui calls."""
    ensure_called: list[bool] = []
    refresh_called: list[bool] = []

    fake_app = _make_fake_freecad(real_doc)
    fake_wb = types.ModuleType("ocw_workbench.workbench")
    fake_wb.ensure_workbench_ui = lambda *a, **kw: ensure_called.append(True)
    fake_wb._refresh_active_workbench_if_open = lambda doc: refresh_called.append(True)

    orig_app, orig_wb = _install_mocks(fake_app, fake_wb)
    yield real_doc, ensure_called, refresh_called
    _restore_mocks(orig_app, orig_wb)


# ---------------------------------------------------------------------------
# ApplyLayoutCommand
# ---------------------------------------------------------------------------

class TestApplyLayoutCommandDirect:
    def test_does_not_call_ensure_workbench_ui(self, env) -> None:
        doc, ensure_called, _ = env
        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        cmd = ApplyLayoutCommand()
        cmd.Activated()
        assert not ensure_called, "ApplyLayoutCommand must NOT call ensure_workbench_ui"

    def test_calls_refresh_after_layout(self, env) -> None:
        doc, _, refresh_called = env
        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        cmd = ApplyLayoutCommand()
        cmd.Activated()
        assert refresh_called, "ApplyLayoutCommand must call _refresh_active_workbench_if_open"

    def test_calls_auto_layout_on_service(self, env, monkeypatch) -> None:
        doc, _, _ = env
        calls: list[dict] = []

        def fake_auto_layout(self_svc, d, strategy="grid", config=None):
            calls.append({"doc": d, "strategy": strategy, "config": config})
            return {"placed_components": [], "unplaced_component_ids": [], "warnings": []}

        monkeypatch.setattr(ControllerService, "auto_layout", fake_auto_layout)

        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        cmd = ApplyLayoutCommand()
        cmd.Activated()

        assert len(calls) == 1
        assert calls[0]["doc"] is doc
        assert calls[0]["strategy"] in {"grid", "row", "column", "zone"}

    def test_uses_stored_strategy_from_context(self, env, monkeypatch) -> None:
        doc, _, _ = env
        calls: list[str] = []

        def fake_get_ui_context(self_svc, d):
            return {"layout": {"strategy": "row", "config": {}}}

        def fake_auto_layout(self_svc, d, strategy="grid", config=None):
            calls.append(strategy)
            return {"placed_components": [], "unplaced_component_ids": [], "warnings": []}

        monkeypatch.setattr(ControllerService, "get_ui_context", fake_get_ui_context)
        monkeypatch.setattr(ControllerService, "auto_layout", fake_auto_layout)

        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        cmd = ApplyLayoutCommand()
        cmd.Activated()

        assert calls and calls[0] == "row", f"Expected strategy 'row', got {calls}"


# ---------------------------------------------------------------------------
# ValidateConstraintsCommand
# ---------------------------------------------------------------------------

class TestValidateConstraintsCommandDirect:
    def test_does_not_call_ensure_workbench_ui(self, env) -> None:
        _, ensure_called, _ = env
        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
        cmd = ValidateConstraintsCommand()
        cmd.Activated()
        assert not ensure_called, "ValidateConstraintsCommand must NOT call ensure_workbench_ui"

    def test_calls_refresh_after_validation(self, env) -> None:
        _, _, refresh_called = env
        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
        cmd = ValidateConstraintsCommand()
        cmd.Activated()
        assert refresh_called, "ValidateConstraintsCommand must call _refresh_active_workbench_if_open"

    def test_calls_validate_layout_on_service(self, env, monkeypatch) -> None:
        doc, _, _ = env
        calls: list[Any] = []

        def fake_validate(self_svc, d, config=None):
            calls.append(d)
            return {"summary": {"error_count": 0, "warning_count": 0}, "messages": []}

        monkeypatch.setattr(ControllerService, "validate_layout", fake_validate)

        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
        cmd = ValidateConstraintsCommand()
        cmd.Activated()

        assert len(calls) == 1
        assert calls[0] is doc

    def test_handles_validation_with_errors(self, env, monkeypatch) -> None:
        """Command must not raise even when validation finds errors."""
        _, _, _ = env

        def fake_validate(self_svc, d, config=None):
            return {
                "summary": {"error_count": 3, "warning_count": 1},
                "messages": [{"level": "error", "message": "too close"}],
            }

        monkeypatch.setattr(ControllerService, "validate_layout", fake_validate)

        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
        cmd = ValidateConstraintsCommand()
        cmd.Activated()  # must not raise
