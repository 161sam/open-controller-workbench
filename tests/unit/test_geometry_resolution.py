from pathlib import Path

import pytest

from ocf_freecad.domain.component import Component
from ocf_freecad.generator.component_resolver import ComponentResolver
from ocf_freecad.generator.controller_builder import ControllerBuilder
from ocf_freecad.generator.mechanical_resolver import MechanicalResolver
from ocf_freecad.library.manager import ComponentLibraryManager
from ocf_freecad.services.library_service import LibraryService
from ocf_freecad.utils.yaml_io import dump_yaml, load_yaml


def test_encoder_resolution_from_library_fixture():
    fixture = load_yaml("tests/fixtures/mechanical_resolution_expected.yaml")
    resolver = MechanicalResolver()

    resolved = resolver.resolve(
        Component(
            id="enc1",
            type="encoder",
            x=40,
            y=30,
            library_ref="alps_ec11e15204a3",
        )
    )

    assert resolved.to_dict()["cutout"] == fixture["encoder"]["cutout"]
    assert resolved.to_dict()["keepout_top"] == fixture["encoder"]["keepout_top"]
    assert resolved.to_dict()["keepout_bottom"] == fixture["encoder"]["keepout_bottom"]


def test_button_and_display_resolution_from_library_fixture():
    fixture = load_yaml("tests/fixtures/mechanical_resolution_expected.yaml")
    resolver = MechanicalResolver()

    button = resolver.resolve(
        Component(
            id="btn1",
            type="button",
            x=20,
            y=20,
            library_ref="omron_b3f_1000",
        )
    )
    display = resolver.resolve(
        Component(
            id="disp1",
            type="display",
            x=60,
            y=25,
            library_ref="adafruit_oled_096_i2c_ssd1306",
        )
    )

    assert button.to_dict() == fixture["button"]
    assert display.to_dict() == fixture["display"]


def test_explicit_cutout_override_wins_over_library_default():
    resolver = MechanicalResolver()

    resolved = resolver.resolve(
        Component(
            id="enc1",
            type="encoder",
            x=0,
            y=0,
            library_ref="alps_ec11e15204a3",
            mechanical={
                "cutout": {
                    "shape": "circle",
                    "diameter": 8.4,
                }
            },
        )
    )

    assert resolved.cutout.diameter == 8.4
    assert resolved.keepout_top.diameter == 20.0


def test_missing_library_ref_requires_mechanical_overrides():
    resolver = MechanicalResolver()

    with pytest.raises(ValueError, match="Missing library_ref or mechanical overrides"):
        resolver.resolve(
            Component(
                id="enc1",
                type="encoder",
                x=0,
                y=0,
            )
        )


def test_unknown_library_ref_raises_clear_error():
    resolver = MechanicalResolver()

    with pytest.raises(KeyError, match="Unknown component id: does_not_exist"):
        resolver.resolve(
            Component(
                id="enc1",
                type="encoder",
                x=0,
                y=0,
                library_ref="does_not_exist",
            )
        )


def test_incomplete_library_data_raises_clear_error(tmp_path: Path):
    base_path = tmp_path / "components"
    dump_yaml(
        base_path / "broken.yaml",
        {
            "components": [
                {
                    "id": "broken_encoder",
                    "category": "encoder",
                    "manufacturer": "Test",
                    "part_number": "BROKEN-1",
                    "description": "Broken encoder fixture",
                    "tags": [],
                    "mechanical": {
                        "panel": {
                            "recommended_keepout_top_diameter_mm": 10.0,
                        }
                    },
                    "electrical": {},
                    "pcb": {},
                    "ocf": {},
                }
            ]
        },
    )

    manager = ComponentLibraryManager(base_path=base_path)
    service = LibraryService(manager)
    resolver = MechanicalResolver(service)

    with pytest.raises(ValueError, match="Missing mechanical defaults for component 'enc1'"):
        resolver.resolve(
            Component(
                id="enc1",
                type="encoder",
                x=0,
                y=0,
                library_ref="broken_encoder",
            )
        )


def test_unsupported_shape_type_raises_clear_error():
    resolver = MechanicalResolver()

    with pytest.raises(ValueError, match="Unsupported cutout shape: triangle"):
        resolver.resolve(
            Component(
                id="enc1",
                type="encoder",
                x=0,
                y=0,
                mechanical={
                    "cutout": {"shape": "triangle", "diameter": 7.0},
                    "keepout_top": {"shape": "circle", "diameter": 20.0},
                    "keepout_bottom": {"shape": "circle", "diameter": 24.0, "depth": 18.0},
                },
            )
        )


def test_component_resolver_and_builder_keepouts_are_normalized():
    component = Component(
        id="disp1",
        type="display",
        x=50,
        y=35,
        library_ref="adafruit_oled_096_i2c_ssd1306",
    )
    component_resolver = ComponentResolver()
    builder = ControllerBuilder(doc=None, component_resolver=component_resolver)

    resolved = component_resolver.resolve(component)
    keepouts = builder.build_keepouts([component])
    cutouts = builder.build_cutout_primitives([component])

    assert resolved["mechanical"]["cutout"]["shape"] == "rect"
    assert cutouts[0]["width"] == 27.0
    assert keepouts[0]["feature"] == "keepout_top"
    assert keepouts[1]["depth"] == 8.0
