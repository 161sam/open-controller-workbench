from ocf_freecad.domain.component import Component
from ocf_freecad.domain.controller import Controller
from ocf_freecad.generator.electrical_mapper import ElectricalMapper
from ocf_freecad.generator.electrical_resolver import ElectricalResolver
from ocf_freecad.generator.schematic_builder import SchematicBuilder
from ocf_freecad.utils.yaml_io import load_yaml


def _build_mapping(components, firmware=None):
    mapper = ElectricalMapper(ElectricalResolver())
    controller = Controller("controller_a", 120, 80, 30, 3)
    return mapper.map_controller(controller, components, firmware=firmware)


def test_builds_encoder_button_and_oled_schematic():
    fixture = load_yaml("tests/fixtures/schematic_expected.yaml")
    firmware = {
        "buses": {"i2c0": {"type": "i2c", "pins": {"sda": "PB7", "scl": "PB6"}}},
        "controller_mcu": {"id": "stm32f405", "family": "STM32"},
    }
    mapping = _build_mapping(
        [
            Component("enc_master_1", "encoder", 0, 0, library_ref="alps_ec11e15204a3", io_strategy="direct_gpio"),
            Component("btn_play", "button", 0, 0, library_ref="omron_b3f_1000", io_strategy="matrix", row=0, col=1),
            Component("oled_status", "display", 0, 0, library_ref="adafruit_oled_096_i2c_ssd1306", io_strategy="i2c", bus="i2c0"),
        ],
        firmware=firmware,
    )

    schematic = SchematicBuilder().build(mapping)

    assert schematic["schema_version"] == fixture["schema_version"]
    assert schematic["export_type"] == fixture["export_type"]
    assert schematic["components"][1]["symbol"] == fixture["symbols"]["encoder"]
    assert schematic["components"][2]["symbol"] == fixture["symbols"]["button"]
    assert schematic["components"][3]["symbol"] == fixture["symbols"]["display"]
    assert any(connection["net"] == "i2c0.sda" for connection in schematic["connections"])
    assert any(net["name"] == "enc_master_1.a" for net in schematic["nets"])


def test_warns_when_power_connection_missing():
    mapping = {
        "schema_version": "1.0",
        "export_type": "controller.electrical",
        "meta": {},
        "controller": {"id": "controller_a", "controller_mcu": {"id": "rp2040"}},
        "buses": {},
        "components": [
            {
                "id": "oled_status",
                "type": "display",
                "role": "oled_display",
                "library_ref": "adafruit_oled_096_i2c_ssd1306",
                "assignments": [{"component_id": "oled_status", "strategy": "i2c", "bus": None, "address": "0x3C"}],
            }
        ],
        "signals": [],
        "assignments": [{"component_id": "oled_status", "strategy": "i2c", "bus": None, "address": "0x3C"}],
        "nets": [
            {"component_id": "oled_status", "signal": "sda", "net_name": "oled_status.sda", "role": "oled_display"},
            {"component_id": "oled_status", "signal": "scl", "net_name": "oled_status.scl", "role": "oled_display"},
        ],
        "warnings": [],
        "io_strategy": {},
    }

    schematic = SchematicBuilder().build(mapping)

    assert any(warning["code"] == "missing_power_connection" for warning in schematic["warnings"])
    assert any(warning["code"] == "missing_bus" for warning in schematic["warnings"])


def test_unknown_component_gets_fallback_symbol_warning():
    mapping = _build_mapping([Component("mystery", "custom", 0, 0, electrical={"type": "mystery"})])

    schematic = SchematicBuilder().build(mapping)

    assert schematic["components"][0]["symbol"] == "generic_component"
    assert any(warning["code"] == "unknown_component_type" for warning in schematic["warnings"])
