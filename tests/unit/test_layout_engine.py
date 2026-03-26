from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.services.layout_service import LayoutService


def test_places_simple_button_row():
    service = LayoutService()
    controller = Controller("c1", 160, 80, 30, 3)
    components = [
        Component("btn1", "button", 0, 0, library_ref="omron_b3f_1000"),
        Component("btn2", "button", 0, 0, library_ref="omron_b3f_1000"),
        Component("btn3", "button", 0, 0, library_ref="omron_b3f_1000"),
    ]

    result = service.place(controller, components, strategy="row", config={"spacing_mm": 22.0, "padding_mm": 12.0})

    assert len(result["placements"]) == 3
    assert result["placements"][0]["y"] == result["placements"][1]["y"] == result["placements"][2]["y"]
    assert result["validation"]["summary"]["error_count"] == 0


def test_places_encoder_grid():
    service = LayoutService()
    controller = Controller("c1", 180, 120, 30, 3)
    components = [
        Component("enc1", "encoder", 0, 0, library_ref="alps_ec11e15204a3"),
        Component("enc2", "encoder", 0, 0, library_ref="alps_ec11e15204a3"),
        Component("enc3", "encoder", 0, 0, library_ref="alps_ec11e15204a3"),
        Component("enc4", "encoder", 0, 0, library_ref="alps_ec11e15204a3"),
    ]

    result = service.place(controller, components, strategy="grid", config={"spacing_x_mm": 28.0, "spacing_y_mm": 28.0, "padding_mm": 16.0})

    assert len(result["placements"]) == 4
    assert len({(placement["x"], placement["y"]) for placement in result["placements"]}) == 4
    assert result["validation"]["summary"]["error_count"] == 0


def test_places_display_and_buttons_without_collision():
    service = LayoutService()
    controller = Controller("c1", 180, 100, 30, 3)
    components = [
        Component("disp1", "display", 0, 0, library_ref="adafruit_oled_096_i2c_ssd1306"),
        Component("btn1", "button", 0, 0, library_ref="omron_b3f_1000"),
        Component("btn2", "button", 0, 0, library_ref="omron_b3f_1000"),
    ]

    result = service.place(controller, components, strategy="grid", config={"spacing_x_mm": 40.0, "spacing_y_mm": 26.0, "padding_mm": 18.0})

    placed_ids = [placement["component_id"] for placement in result["placements"]]
    assert "disp1" in placed_ids
    assert len(result["placements"]) == 3
    assert result["validation"]["summary"]["error_count"] == 0


def test_places_fader_in_own_zone():
    service = LayoutService()
    controller = Controller(
        "c1",
        200,
        100,
        30,
        3,
        layout_zones=[
            {"id": "faders", "x": 20, "y": 20, "width": 120, "height": 40, "strategy": "row"},
            {"id": "buttons", "x": 20, "y": 70, "width": 140, "height": 20, "strategy": "row"},
        ],
    )
    components = [
        Component("fader1", "fader", 0, 0, library_ref="generic_60mm_linear_fader", zone_id="faders"),
        Component("btn1", "button", 0, 0, library_ref="omron_b3f_1000", zone_id="buttons"),
    ]

    result = service.place(controller, components, strategy="zone", config={"spacing_mm": 30.0, "padding_mm": 10.0})

    fader = next(placement for placement in result["placements"] if placement["component_id"] == "fader1")
    button = next(placement for placement in result["placements"] if placement["component_id"] == "btn1")
    assert fader["zone_id"] == "faders"
    assert 20 <= fader["x"] <= 140
    assert button["zone_id"] == "buttons"
    assert 70 <= button["y"] <= 90


def test_reports_failed_placement_for_small_surface():
    service = LayoutService()
    controller = Controller("c1", 40, 40, 30, 3)
    components = [
        Component("disp1", "display", 0, 0, library_ref="adafruit_oled_096_i2c_ssd1306"),
        Component("disp2", "display", 0, 0, library_ref="adafruit_oled_096_i2c_ssd1306"),
    ]

    result = service.place(controller, components, strategy="row", config={"spacing_mm": 20.0, "padding_mm": 4.0})

    assert len(result["placements"]) < 2
    assert "disp2" in result["unplaced_component_ids"] or "disp1" in result["unplaced_component_ids"]
    assert any(warning["code"] == "placement_failed" for warning in result["warnings"])


def test_places_pad_grid_4x4_without_cutout_overlap():
    service = LayoutService()
    controller = Controller(
        "pads",
        180,
        180,
        32,
        3,
        surface={"shape": "rounded_rect", "width": 180.0, "height": 180.0, "corner_radius": 10.0},
        layout_zones=[{"id": "pad_matrix", "x": 15.0, "y": 15.0, "width": 150.0, "height": 150.0, "strategy": "grid"}],
    )
    components = [
        Component(f"pad{index}", "pad", 0, 0, library_ref="generic_mpc_pad_30mm", zone_id="pad_matrix")
        for index in range(1, 17)
    ]

    result = service.place(
        controller,
        components,
        strategy="grid",
        config={
            "rows": 4,
            "cols": 4,
            "spacing_x_mm": 36.0,
            "spacing_y_mm": 36.0,
            "placement_blocking_mode": "cutout_surface",
        },
    )

    placements = result["placements"]
    assert len(placements) == 16
    assert {placement["x"] for placement in placements} == {36.0, 72.0, 108.0, 144.0}
    assert {placement["y"] for placement in placements} == {36.0, 72.0, 108.0, 144.0}
    assert not any(error["rule_id"] == "cutout_spacing" for error in result["validation"]["errors"])
