from pathlib import Path

from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.services.schematic_service import SchematicService
from ocw_workbench.utils.yaml_io import load_yaml


def test_exports_schematic_yaml(tmp_path: Path):
    fixture = load_yaml("tests/fixtures/schematic_expected.yaml")
    service = SchematicService()
    controller = Controller("controller_a", 120, 80, 30, 3)
    components = [
        Component("enc_master_1", "encoder", 0, 0, library_ref="alps_ec11e15204a3", io_strategy="direct_gpio"),
        Component("oled_status", "display", 0, 0, library_ref="adafruit_oled_096_i2c_ssd1306", io_strategy="i2c", bus="i2c0"),
    ]
    firmware = {
        "buses": {"i2c0": {"type": "i2c", "pins": {"sda": "PB7", "scl": "PB6"}}},
        "controller_mcu": {"id": "stm32f405", "family": "STM32"},
    }

    schematic = service.build_from_controller(controller, components, firmware=firmware)
    out_path = tmp_path / "controller.schematic.yaml"
    service.export(schematic, out_path)
    exported = load_yaml(out_path)

    assert exported["schema_version"] == fixture["schema_version"]
    assert exported["export_type"] == fixture["export_type"]
    assert any(symbol["name"] == fixture["symbols"]["encoder"] for symbol in exported["symbols"])
    assert sorted(net["name"] for net in exported["power"]["nets"]) == fixture["power_nets"]


def test_preserves_electrical_warnings_in_export():
    service = SchematicService()
    mapping = {
        "schema_version": "1.0",
        "export_type": "controller.electrical",
        "meta": {},
        "controller": {"id": "controller_a", "controller_mcu": None},
        "io_strategy": {},
        "buses": {},
        "components": [],
        "signals": [],
        "assignments": [],
        "nets": [],
        "warnings": [{"code": "missing_i2c_bus", "message": "Missing i2c bus for display component 'oled_status'"}],
    }

    schematic = service.build_from_mapping(mapping)

    assert any(warning["code"] == "missing_i2c_bus" for warning in schematic["warnings"])
