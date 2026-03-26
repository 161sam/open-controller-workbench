from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.overlay_service import OverlayService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_constraint_overlay_builds_measurements_conflict_lines_and_clearance_markers():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 70.0, "depth": 60.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=4.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=11.0, y=20.0)
    controller_service.select_component(doc, "btn1")
    controller_service.validate_layout(doc)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    line_items = [item for item in overlay["items"] if item["type"] == "line"]
    clearance_items = [item for item in overlay["items"] if item["id"].startswith("clearance:")]

    assert any(item["id"].startswith("conflict:edge:btn1") for item in line_items)
    assert any(item["id"].startswith("distance:component_spacing:btn1:btn2") for item in line_items)
    assert any(item["id"].startswith("clearance:edge:left:btn1") for item in clearance_items)
    assert any(item["id"].startswith("clearance:component_spacing:btn1") for item in clearance_items)


def test_constraint_overlay_toggles_hide_measurements_lines_and_labels():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 70.0, "depth": 60.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=4.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=11.0, y=20.0)
    controller_service.select_component(doc, "btn1")
    controller_service.validate_layout(doc)

    interaction_service.update_settings(
        doc,
        {
            "measurements_enabled": False,
            "conflict_lines_enabled": False,
            "constraint_labels_enabled": False,
        },
    )
    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)

    assert not any(item["id"].startswith("distance:") for item in overlay["items"])
    assert not any(item["id"].startswith("conflict:") for item in overlay["items"])
    assert not any(item["id"].startswith("label:") for item in overlay["items"])


def test_constraint_overlay_prioritizes_active_move_component():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=5.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=12.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn3", x=70.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn4", x=77.0, y=20.0)
    controller_service.select_component(doc, "btn3")
    interaction_service.arm_move(doc, "btn1")
    controller_service.validate_layout(doc)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    constraint_lines = [item for item in overlay["items"] if item["type"] == "line" and item["id"].startswith(("conflict:", "distance:"))]

    assert constraint_lines
    assert "btn1" in constraint_lines[0]["id"]


def test_constraint_overlay_styles_errors_before_warnings():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=12.0, y=20.0)
    controller_service.add_component(doc, "alps_ec11e15204a3", component_id="enc2", x=28.0, y=20.0)
    controller_service.select_component(doc, "enc1")
    controller_service.validate_layout(doc)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    error_line = next(item for item in overlay["items"] if item["id"].startswith("conflict:"))
    warning_line = next(item for item in overlay["items"] if item["id"].startswith("measurement:neighbor:"))

    assert error_line["style"]["kind"] == "conflict_line_error"
    assert warning_line["style"]["kind"] == "measurement_line"
