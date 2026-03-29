from __future__ import annotations

from pathlib import Path

from ocw_workbench.commands.add_component import AddComponentCommand
from ocw_workbench.commands.align_distribute import SelectionArrangeCommand
from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
from ocw_workbench.commands.component_patterns import DuplicateSelectionCommand, GridArrayCommand, LinearArrayCommand
from ocw_workbench.commands.create_from_template import CreateFromTemplateCommand
from ocw_workbench.commands.disable_plugin import DisablePluginCommand
from ocw_workbench.commands.drag_move_component import DragMoveComponentCommand
from ocw_workbench.commands.enable_plugin import EnablePluginCommand
from ocw_workbench.commands.import_template_from_fcstd import ImportTemplateFromFCStdCommand
from ocw_workbench.commands.open_component_palette import OpenComponentPaletteCommand
from ocw_workbench.commands.open_plugin_manager import OpenPluginManagerCommand
from ocw_workbench.commands.place_component_type import PlaceComponentTypeCommand
from ocw_workbench.commands.reload_plugins import ReloadPluginsCommand
from ocw_workbench.commands.select_component import SelectComponentCommand
from ocw_workbench.commands.selection_transform import SelectionTransformCommand
from ocw_workbench.commands.show_constraint_overlay import ShowConstraintOverlayCommand
from ocw_workbench.commands.snap_to_grid import SnapToGridCommand
from ocw_workbench.commands.toggle_conflict_lines import ToggleConflictLinesCommand
from ocw_workbench.commands.toggle_constraint_labels import ToggleConstraintLabelsCommand
from ocw_workbench.commands.toggle_measurements import ToggleMeasurementsCommand
from ocw_workbench.commands.toggle_overlay import ToggleOverlayCommand
from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
from ocw_workbench.gui.runtime import component_icon_path, icon_path
from ocw_workbench.workbench import OpenControllerWorkbench


def test_registered_command_resources_include_existing_pixmaps() -> None:
    commands = [
        CreateFromTemplateCommand(),
        AddComponentCommand(),
        ApplyLayoutCommand(),
        ValidateConstraintsCommand(),
        ToggleOverlayCommand(),
        ShowConstraintOverlayCommand(),
        ToggleMeasurementsCommand(),
        ToggleConflictLinesCommand(),
        ToggleConstraintLabelsCommand(),
        OpenPluginManagerCommand(),
        OpenComponentPaletteCommand(),
        DragMoveComponentCommand(),
        SnapToGridCommand(),
        SelectComponentCommand(),
        SelectionArrangeCommand("align_left"),
        SelectionArrangeCommand("distribute_horizontal"),
        DuplicateSelectionCommand(),
        LinearArrayCommand("x"),
        GridArrayCommand(),
        SelectionTransformCommand("rotate_cw_90"),
        SelectionTransformCommand("mirror_vertical"),
        ImportTemplateFromFCStdCommand(),
        EnablePluginCommand(),
        DisablePluginCommand(),
        ReloadPluginsCommand(),
    ]

    for command in commands:
        resources = command.GetResources()
        assert resources["MenuText"]
        assert resources["ToolTip"]
        assert Path(resources["Pixmap"]).exists(), resources["Pixmap"]
        assert Path(resources["Pixmap"]).name != "default.svg", resources["Pixmap"]


def test_place_component_type_command_resources_are_valid() -> None:
    for ctype in ("button", "encoder", "fader", "pad", "display", "rgb_button"):
        cmd = PlaceComponentTypeCommand(ctype)
        resources = cmd.GetResources()
        assert resources["MenuText"]
        assert resources["ToolTip"]
        assert Path(resources["Pixmap"]).exists(), f"{ctype}: {resources['Pixmap']}"


def test_workbench_icon_exists() -> None:
    assert Path(OpenControllerWorkbench.Icon).exists()


def test_runtime_icon_helpers_fall_back_to_default_assets() -> None:
    missing_icon = Path(icon_path("missing-icon-name"))
    missing_component_icon = Path(component_icon_path("missing-component-icon.svg"))

    assert missing_icon.exists()
    assert missing_icon.name == "default.svg"
    assert missing_component_icon.exists()
    assert missing_component_icon.name == "generic.svg"
