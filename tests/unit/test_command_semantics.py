from __future__ import annotations

import sys
import types


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


def test_plugin_enable_disable_commands_use_direct_helpers_without_opening_dock(monkeypatch) -> None:
    doc = FakeDocument()
    ensure_called: list[bool] = []
    enable_calls: list[object] = []
    disable_calls: list[object] = []
    fake_app = _make_fake_freecad(doc)
    fake_wb = types.ModuleType("ocw_workbench.workbench")
    fake_wb.ensure_workbench_ui = lambda *a, **kw: ensure_called.append(True)
    fake_wb.has_selected_plugin_in_open_manager = lambda current_doc=None: True
    fake_wb.enable_selected_plugin_direct = lambda current_doc=None: enable_calls.append(current_doc) or {"id": "pack.alpha"}
    fake_wb.disable_selected_plugin_direct = lambda current_doc=None: disable_calls.append(current_doc) or {"id": "pack.alpha"}

    orig_app, orig_wb = _install_mocks(fake_app, fake_wb)
    try:
        import ocw_workbench.commands.enable_plugin as enable_plugin_module
        import ocw_workbench.commands.disable_plugin as disable_plugin_module

        enable_plugin_module.show_info = lambda title, message: None
        enable_plugin_module.show_error = lambda title, exc: (_ for _ in ()).throw(exc)
        disable_plugin_module.show_info = lambda title, message: None
        disable_plugin_module.show_error = lambda title, exc: (_ for _ in ()).throw(exc)

        assert enable_plugin_module.EnablePluginCommand().IsActive() is True
        assert disable_plugin_module.DisablePluginCommand().IsActive() is True

        enable_plugin_module.EnablePluginCommand().Activated()
        disable_plugin_module.DisablePluginCommand().Activated()
    finally:
        _restore_mocks(orig_app, orig_wb)

    assert not ensure_called
    assert enable_calls == [doc]
    assert disable_calls == [doc]


def test_plugin_enable_disable_commands_are_inactive_without_open_plugin_selection() -> None:
    doc = FakeDocument()
    fake_app = _make_fake_freecad(doc)
    fake_wb = types.ModuleType("ocw_workbench.workbench")
    fake_wb.has_selected_plugin_in_open_manager = lambda current_doc=None: False

    orig_app, orig_wb = _install_mocks(fake_app, fake_wb)
    try:
        from ocw_workbench.commands.enable_plugin import EnablePluginCommand
        from ocw_workbench.commands.disable_plugin import DisablePluginCommand

        assert EnablePluginCommand().IsActive() is False
        assert DisablePluginCommand().IsActive() is False
    finally:
        _restore_mocks(orig_app, orig_wb)


def test_navigation_commands_use_explicit_open_workbench_dock_helper() -> None:
    doc = FakeDocument()
    calls: list[tuple[object, str]] = []
    ensure_called: list[bool] = []
    fake_app = _make_fake_freecad(doc)
    fake_wb = types.ModuleType("ocw_workbench.workbench")
    fake_wb.ensure_workbench_ui = lambda *a, **kw: ensure_called.append(True)
    fake_wb.open_workbench_dock = lambda current_doc=None, focus="create": calls.append((current_doc, focus)) or object()

    orig_app, orig_wb = _install_mocks(fake_app, fake_wb)
    try:
        import ocw_workbench.commands.create_from_template as create_module
        import ocw_workbench.commands.open_plugin_manager as plugin_manager_module
        import ocw_workbench.commands.select_component as select_module

        create_module.show_error = lambda title, exc: (_ for _ in ()).throw(exc)
        plugin_manager_module.show_error = lambda title, exc: (_ for _ in ()).throw(exc)
        select_module.show_error = lambda title, exc: (_ for _ in ()).throw(exc)

        create_module.CreateFromTemplateCommand().Activated()
        plugin_manager_module.OpenPluginManagerCommand().Activated()
        select_module.SelectComponentCommand().Activated()
    finally:
        _restore_mocks(orig_app, orig_wb)

    assert not ensure_called
    assert calls == [
        (doc, "create"),
        (doc, "plugins"),
        (doc, "components"),
    ]
