from __future__ import annotations

import types


def test_workbench_primary_toolbars_prioritize_direct_actions(monkeypatch) -> None:
    from ocw_workbench import workbench as workbench_module

    added_commands: list[str] = []
    appended_toolbars: list[tuple[str, list[str]]] = []
    appended_menus: list[tuple[str, list[str]]] = []

    fake_gui = types.SimpleNamespace(
        addCommand=lambda command_id, command: added_commands.append(command_id),
    )
    monkeypatch.setattr(workbench_module, "Gui", fake_gui)

    workbench = workbench_module.OpenControllerWorkbench()
    monkeypatch.setattr(
        workbench,
        "appendToolbar",
        lambda name, commands: appended_toolbars.append((name, list(commands))),
        raising=False,
    )
    monkeypatch.setattr(
        workbench,
        "appendMenu",
        lambda name, commands: appended_menus.append((name, list(commands))),
        raising=False,
    )

    workbench.Initialize()

    toolbar_map = {name: commands for name, commands in appended_toolbars}
    menu_map = {name: commands for name, commands in appended_menus}

    assert "OCW Favorites" not in toolbar_map
    assert toolbar_map["OCW Project"] == ["OCW_ImportTemplateFromFCStd"]
    assert "OCW_CreateController" not in toolbar_map["OCW Project"]
    assert "OCW_PlaceButton" in toolbar_map["OCW Components"]
    assert "OCW_PlaceRgbButton" in toolbar_map["OCW Components"]
    assert menu_map["OCW/Create"] == ["OCW_CreateController", "OCW_ImportTemplateFromFCStd"]
    assert menu_map["OCW/Components/Favorites"][-1] == workbench_module._FAVORITE_MORE_COMMAND_ID
