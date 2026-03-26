from __future__ import annotations

from pathlib import Path

from ocf_freecad.commands.add_component import AddComponentCommand
from ocf_freecad.commands.apply_layout import ApplyLayoutCommand
from ocf_freecad.commands.create_from_template import CreateFromTemplateCommand
from ocf_freecad.commands.open_plugin_manager import OpenPluginManagerCommand
from ocf_freecad.commands.toggle_overlay import ToggleOverlayCommand
from ocf_freecad.commands.validate_constraints import ValidateConstraintsCommand
from ocf_freecad.workbench import OpenControllerWorkbench


def test_registered_command_resources_include_existing_pixmaps() -> None:
    commands = [
        CreateFromTemplateCommand(),
        AddComponentCommand(),
        ApplyLayoutCommand(),
        ValidateConstraintsCommand(),
        ToggleOverlayCommand(),
        OpenPluginManagerCommand(),
    ]

    for command in commands:
        resources = command.GetResources()
        assert resources["MenuText"]
        assert resources["ToolTip"]
        assert Path(resources["Pixmap"]).exists(), resources["Pixmap"]


def test_workbench_icon_exists() -> None:
    assert Path(OpenControllerWorkbench.Icon).exists()
