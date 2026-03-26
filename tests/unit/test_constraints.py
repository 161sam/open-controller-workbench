from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.services.constraint_service import ConstraintService


def test_two_encoders_too_close_produces_spacing_error():
    service = ConstraintService()
    controller = Controller("c1", 120, 80, 30, 3)
    components = [
        Component("enc1", "encoder", 30, 30, library_ref="alps_ec11e15204a3"),
        Component("enc2", "encoder", 42, 30, library_ref="alps_ec11e15204a3"),
    ]

    report = service.validate(controller, components)

    assert any(error["rule_id"] == "component_spacing" for error in report["errors"])


def test_component_too_close_to_edge_produces_error():
    service = ConstraintService()
    controller = Controller("c1", 120, 80, 30, 3)
    components = [
        Component("enc1", "encoder", 6, 30, library_ref="alps_ec11e15204a3"),
    ]

    report = service.validate(controller, components)

    assert any(error["rule_id"] == "edge_distance" for error in report["errors"])


def test_component_outside_surface_produces_error():
    service = ConstraintService()
    controller = Controller("c1", 120, 80, 30, 3, surface={"shape": "rounded_rect", "corner_radius": 10})
    components = [
        Component("enc1", "encoder", 118, 78, library_ref="alps_ec11e15204a3"),
    ]

    report = service.validate(controller, components)

    assert any(error["rule_id"] == "inside_surface_component" for error in report["errors"])


def test_component_colliding_with_mounting_hole_produces_error():
    service = ConstraintService()
    controller = Controller(
        "c1",
        120,
        80,
        30,
        3,
        mounting_holes=[{"id": "mh1", "x": 30, "y": 30, "diameter": 3.0}],
    )
    components = [
        Component("btn1", "button", 30, 30, library_ref="omron_b3f_1000"),
    ]

    report = service.validate(controller, components)

    assert any(error["rule_id"] == "mounting_hole_clearance" for error in report["errors"])


def test_ergonomic_warning_for_close_placement():
    service = ConstraintService()
    controller = Controller("c1", 160, 100, 30, 3)
    components = [
        Component("fader1", "fader", 60, 40, library_ref="generic_60mm_linear_fader"),
        Component("btn1", "button", 75, 40, library_ref="omron_b3f_1000"),
    ]

    report = service.validate(controller, components)

    assert any(warning["rule_id"] == "ergonomic_fader_button_proximity" for warning in report["warnings"])


def test_rotated_rect_component_uses_rotated_inside_surface_check():
    service = ConstraintService()
    controller = Controller("c1", 50, 100, 30, 3)
    components = [
        Component("fader1", "fader", 25, 50, rotation=90.0, library_ref="generic_45mm_linear_fader"),
    ]

    report = service.validate(controller, components)

    assert not any(error["rule_id"] == "inside_surface_component" for error in report["errors"])
