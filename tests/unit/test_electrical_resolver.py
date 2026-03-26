from ocw_workbench.domain.component import Component
from ocw_workbench.generator.electrical_resolver import ElectricalResolver


def test_encoder_direct_gpio_resolution():
    resolver = ElectricalResolver()

    resolved = resolver.resolve(
        Component(
            id="enc_master_1",
            type="encoder",
            x=0,
            y=0,
            library_ref="alps_ec11e15204a3",
            electrical={"io_strategy": "direct_gpio"},
        )
    )

    assert resolved["role"] == "incremental_encoder"
    assert [signal["name"] for signal in resolved["signals"]] == ["a", "b", "common"]
    assert resolved["electrical"]["io_strategy"] == "direct_gpio"


def test_oled_override_wins_for_address_and_bus():
    resolver = ElectricalResolver()

    resolved = resolver.resolve(
        Component(
            id="oled_status",
            type="display",
            x=0,
            y=0,
            library_ref="adafruit_oled_096_i2c_ssd1306",
            address="0x3D",
            bus="i2c1",
        )
    )

    assert resolved["role"] == "oled_display"
    assert resolved["electrical"]["address"] == "0x3D"
    assert resolved["electrical"]["bus"] == "i2c1"
    assert {signal["name"] for signal in resolved["signals"]} == {"vcc", "gnd", "sda", "scl", "rst"}


def test_component_without_electrical_data_becomes_mechanical_only():
    resolver = ElectricalResolver()

    resolved = resolver.resolve(
        Component(
            id="panel_spacer",
            type="mechanical",
            x=0,
            y=0,
        )
    )

    assert resolved["role"] == "mechanical_only"
    assert resolved["signals"] == []
    assert resolved["warnings"][0]["code"] == "missing_electrical_definition"
