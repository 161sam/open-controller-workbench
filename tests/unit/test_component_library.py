from ocf_freecad.library.manager import ComponentLibraryManager
from ocf_freecad.utils.yaml_io import load_yaml


def test_load_all_components():
    manager = ComponentLibraryManager()
    manager.load_all()

    components = manager.list_components()
    ids = {component["id"] for component in components}
    fixture = load_yaml("tests/fixtures/library_lookup_expected.yaml")

    assert ids == set(fixture["expected_components"])


def test_get_component():
    manager = ComponentLibraryManager()
    component = manager.get_component("alps_ec11e15204a3")

    assert component["manufacturer"] == "Alps Alpine"
    assert component["category"] == "encoder"
    assert component["mechanical"]["panel"]["recommended_hole_diameter_mm"] == 7.0


def test_list_components_by_category():
    manager = ComponentLibraryManager()

    displays = manager.list_components(category="display")
    faders = manager.list_components(category="fader")
    pads = manager.list_components(category="pad")
    rgb_buttons = manager.list_components(category="rgb_button")

    assert len(displays) == 1
    assert displays[0]["id"] == "adafruit_oled_096_i2c_ssd1306"
    assert len(faders) == 2
    assert {item["id"] for item in faders} == {"generic_45mm_linear_fader", "generic_60mm_linear_fader"}
    assert len(pads) == 1
    assert pads[0]["id"] == "generic_mpc_pad_30mm"
    assert len(rgb_buttons) == 1
    assert rgb_buttons[0]["id"] == "generic_rgb_arcade_button_24mm"


def test_resolve_component_with_overrides():
    manager = ComponentLibraryManager()
    resolved = manager.resolve_component(
        "alps_ec11e15204a3",
        overrides={
            "ocf": {
                "default_logical_role": "master_encoder",
            },
            "mechanical": {
                "panel": {
                    "recommended_hole_diameter_with_tolerance_mm": 7.4,
                },
            },
        },
    )

    assert resolved["ocf"]["default_logical_role"] == "master_encoder"
    assert resolved["mechanical"]["panel"]["recommended_hole_diameter_mm"] == 7.0
    assert resolved["mechanical"]["panel"]["recommended_hole_diameter_with_tolerance_mm"] == 7.4


def test_encoder_with_push_resolves_switch_data():
    manager = ComponentLibraryManager()
    component = manager.get_component("generic_ec11_encoder_with_push")

    assert component["electrical"]["integrated_switch"] is True
    assert component["ocf"]["supports"] == ["rotate", "press"]
    assert component["pcb"]["default_footprint"] == "RotaryEncoder_Alps_EC11E_Switch_Vertical"


def test_new_component_categories_have_required_fields():
    manager = ComponentLibraryManager()
    compact_fader = manager.get_component("generic_45mm_linear_fader")
    fader = manager.get_component("generic_60mm_linear_fader")
    pad = manager.get_component("generic_mpc_pad_30mm")
    rgb_button = manager.get_component("generic_rgb_arcade_button_24mm")

    assert compact_fader["mechanical"]["travel_mm"] == 45.0
    assert fader["electrical"]["type"] == "potentiometer"
    assert fader["mechanical"]["slot_cutout"]["length_mm"] == 68.0
    assert pad["ocf"]["control_type"] == "pad"
    assert pad["mechanical"]["diffuser_light_area_mm"]["width"] == 24.0
    assert rgb_button["electrical"]["pins"] == ["SW1", "SW2", "R", "G", "B"]
    assert rgb_button["ocf"]["control_type"] == "button_rgb"


def test_unknown_component_raises_key_error():
    manager = ComponentLibraryManager()

    try:
        manager.get_component("does_not_exist")
        assert False, "Expected KeyError"
    except KeyError as exc:
        assert "Unknown component id" in str(exc)
