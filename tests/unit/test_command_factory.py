from __future__ import annotations

import pytest

from ocw_workbench.commands.factory import (
    build_plugin_commands,
    command_specs_by_command_id,
    component_toolbar_command_ids,
    component_toolbar_groups,
    iter_plugin_command_specs,
)
from ocw_workbench.plugins.activation import activate_plugin
from ocw_workbench.plugins.registry import ExtensionRegistry, Plugin
from ocw_workbench.services.plugin_service import reset_plugin_service


@pytest.fixture(autouse=True)
def _activate_midicontroller():
    reset_plugin_service()
    activate_plugin("midicontroller")
    yield
    reset_plugin_service()


def test_plugin_command_specs_include_pad_and_encoder() -> None:
    specs = {spec.component: spec for spec in iter_plugin_command_specs()}

    assert "pad" in specs
    assert "encoder" in specs
    assert specs["pad"].command_id == "OCW_PlacePad"
    assert specs["encoder"].command_id == "OCW_PlaceEncoder"


def test_component_toolbar_groups_are_plugin_driven() -> None:
    groups = dict(component_toolbar_groups(active_plugin_id="midicontroller"))

    assert list(groups) == [
        "OCW Performance Surface",
        "OCW Mixing & Levels",
        "OCW Rotary Controls",
        "OCW Navigation & Feedback",
        "OCW Buttons & Utility",
    ]
    assert groups["OCW Performance Surface"] == ["OCW_PlacePad", "OCW_PlaceRgbButton"]
    assert groups["OCW Rotary Controls"] == ["OCW_PlaceRotaryEncoder", "OCW_PlaceEncoder"]
    assert groups["OCW Navigation & Feedback"] == ["OCW_PlaceDisplay"]


def test_command_spec_lookup_exposes_command_metadata() -> None:
    specs = command_specs_by_command_id()

    assert specs["OCW_PlacePad"].icon == "pad.svg"
    assert specs["OCW_PlacePad"].category == "Performance Surface"
    assert "Place Performance Pad" in specs["OCW_PlacePad"].tooltip
    assert specs["OCW_PlaceRotaryEncoder"].category == "Rotary Controls"
    assert "synth macros" in specs["OCW_PlaceRotaryEncoder"].tooltip
    assert "OCW_PlaceEncoder" in component_toolbar_command_ids()
    assert "OCW_PlaceRotaryEncoder" in component_toolbar_command_ids()


def test_build_plugin_commands_creates_freecad_place_commands() -> None:
    commands = build_plugin_commands()

    assert "OCW_PlacePad" in commands
    assert "OCW_PlaceEncoder" in commands
    assert "OCW_PlaceRotaryEncoder" in commands
    assert commands["OCW_PlacePad"].component_type == "pad"
    assert commands["OCW_PlaceEncoder"].component_type == "encoder"


def test_build_plugin_commands_works_without_plugin_command_files() -> None:
    reset_plugin_service()
    activate_plugin("bike_trailer")

    commands = build_plugin_commands()

    assert "OCW_PlaceWheel" in commands
    assert "OCW_PlaceCargoBoxModule" in commands
    assert commands["OCW_PlaceWheel"].default_library_ref == "bike_trailer.wheel_20in_spoked"


def test_explicit_plugin_command_overrides_auto_generated_place_command(monkeypatch) -> None:
    import ocw_workbench.commands.factory as factory_module

    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="demo_domain",
            name="Demo Domain",
            version="0.1.0",
            plugin_type="domain",
            domain_type="demo_domain",
        )
    )
    registry.set_active_plugin("demo_domain")

    class FakePluginService:
        def registry(self):
            return registry

        def get_commands_for_active_plugin(self):
            return {
                "plugin_id": "demo_domain",
                "root": None,
                "commands": {
                    "place_widget": {
                        "id": "place_widget",
                        "type": "place_component",
                        "component": "widget",
                        "category": "Override Tools",
                        "icon": "override.svg",
                        "label": "Place Override Widget",
                        "tooltip": "Place Override Widget with explicit plugin command metadata.",
                        "library_ref": "demo_domain.widget_default",
                        "command_id": "OCW_PlaceWidget",
                        "plugin_id": "demo_domain",
                    }
                },
            }

    class FakeManager:
        def list_components(self):
            return [
                {
                    "id": "demo_domain.widget_default",
                    "category": "widget",
                    "description": "Demo widget",
                    "ocf": {"control_type": "widget"},
                    "ui": {
                        "label": "Demo Widget",
                        "icon": "widget.svg",
                        "category": "Demo Components",
                        "command": {
                            "placeable": True,
                            "toolbar": True,
                            "order": 10,
                            "category": "Demo Components",
                            "label": "Place Demo Widget",
                            "command_id": "OCW_PlaceWidget",
                        },
                    },
                }
            ]

    monkeypatch.setattr(factory_module, "get_plugin_service", lambda: FakePluginService())
    monkeypatch.setattr(factory_module, "ComponentLibraryManager", FakeManager)

    specs = {spec.command_id: spec for spec in iter_plugin_command_specs()}

    assert specs["OCW_PlaceWidget"].label == "Place Override Widget"
    assert specs["OCW_PlaceWidget"].category == "Override Tools"
