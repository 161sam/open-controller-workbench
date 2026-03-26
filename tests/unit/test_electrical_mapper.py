from pathlib import Path

from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.services.electrical_service import ElectricalService
from ocw_workbench.utils.yaml_io import load_yaml


def test_maps_encoder_button_and_oled_roles_and_assignments(tmp_path: Path):
    fixture = load_yaml("tests/fixtures/electrical_mapping_expected.yaml")
    service = ElectricalService()
    controller = Controller("controller_a", 120, 80, 30, 3)
    components = [
        Component(
            id="enc_master_1",
            type="encoder",
            x=10,
            y=10,
            library_ref="alps_ec11e15204a3",
            io_strategy="direct_gpio",
        ),
        Component(
            id="btn_play",
            type="button",
            x=20,
            y=10,
            library_ref="omron_b3f_1000",
            io_strategy="matrix",
            row=1,
            col=2,
        ),
        Component(
            id="oled_status",
            type="display",
            x=30,
            y=10,
            library_ref="adafruit_oled_096_i2c_ssd1306",
            io_strategy="i2c",
            bus="i2c0",
        ),
    ]
    firmware = {
        "io_strategy": {"default": "direct_gpio", "button": "matrix", "display": "i2c"},
        "buses": {"i2c0": {"type": "i2c", "pins": {"sda": "PB7", "scl": "PB6"}}},
        "controller_mcu": {"id": "stm32f405", "family": "STM32"},
    }

    mapping = service.map_controller(controller, components, firmware=firmware)
    service.export_mapping(mapping, tmp_path / "controller.electrical.yaml")

    assert mapping["schema_version"] == fixture["schema_version"]
    assert mapping["export_type"] == fixture["export_type"]
    assert [component["role"] for component in mapping["components"]] == [
        fixture["components"][0]["role"],
        fixture["components"][1]["role"],
        fixture["components"][2]["role"],
    ]
    assert mapping["components"][0]["io_strategy"] == fixture["components"][0]["io_strategy"]
    assert mapping["components"][1]["assignments"][0]["row"] == 1
    assert mapping["components"][1]["assignments"][0]["col"] == 2
    assert mapping["components"][2]["assignments"][0]["bus"] == "i2c0"
    assert mapping["components"][2]["assignments"][0]["address"] == "0x3C"
    assert any(net["net_name"] == "i2c0.sda" for net in mapping["nets"])
    assert (tmp_path / "controller.electrical.yaml").exists()


def test_missing_bus_warning_for_i2c_display():
    service = ElectricalService()
    controller = Controller("controller_a", 120, 80, 30, 3)
    components = [
        Component(
            id="oled_status",
            type="display",
            x=30,
            y=10,
            library_ref="adafruit_oled_096_i2c_ssd1306",
            io_strategy="i2c",
        )
    ]

    mapping = service.map_controller(controller, components, firmware={"buses": {}})

    assert mapping["warnings"][0]["code"] == "missing_i2c_bus"


def test_override_pins_win_for_direct_gpio():
    service = ElectricalService()
    controller = Controller("controller_a", 120, 80, 30, 3)
    components = [
        Component(
            id="enc_master_1",
            type="encoder",
            x=10,
            y=10,
            library_ref="alps_ec11e15204a3",
            io_strategy="direct_gpio",
            pins={"a": "PA0", "b": "PA1"},
        )
    ]

    mapping = service.map_controller(controller, components)

    assert mapping["assignments"][0]["logical_pin"] == "PA0"
    assert mapping["assignments"][1]["logical_pin"] == "PA1"


def test_conflicting_i2c_address_warning_is_reported():
    service = ElectricalService()
    controller = Controller("controller_a", 120, 80, 30, 3)
    components = [
        Component(
            id="oled_status",
            type="display",
            x=30,
            y=10,
            library_ref="adafruit_oled_096_i2c_ssd1306",
            io_strategy="i2c",
            bus="i2c0",
            address="0x3C",
        ),
        Component(
            id="oled_aux",
            type="display",
            x=60,
            y=10,
            library_ref="adafruit_oled_096_i2c_ssd1306",
            io_strategy="i2c",
            bus="i2c0",
            address="0x3C",
        ),
    ]
    firmware = {"buses": {"i2c0": {"type": "i2c"}}}

    mapping = service.map_controller(controller, components, firmware=firmware)

    assert any(warning["code"] == "conflicting_i2c_address" for warning in mapping["warnings"])
