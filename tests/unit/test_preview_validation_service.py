from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.preview_validation_service import PreviewValidationService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_preview_validation_reports_valid_placement():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})

    result = PreviewValidationService(controller_service=controller_service).validate_place(
        doc,
        template_id="omron_b3f_1000",
        x=30.0,
        y=30.0,
    )

    assert result["valid"] is True
    assert result["status"] == "Valid placement"
    assert result["commit_allowed"] is True


def test_preview_validation_reports_out_of_bounds():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 40.0, "depth": 40.0, "height": 30.0})

    result = PreviewValidationService(controller_service=controller_service).validate_place(
        doc,
        template_id="omron_b3f_1000",
        x=2.0,
        y=2.0,
    )

    assert result["valid"] is False
    assert result["status"] == "Out of bounds"
    assert result["commit_allowed"] is False


def test_preview_validation_reports_overlap_risk():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=30.0, y=30.0)

    result = PreviewValidationService(controller_service=controller_service).validate_place(
        doc,
        template_id="omron_b3f_1000",
        x=30.0,
        y=30.0,
    )

    assert result["valid"] is False
    assert result["status"] == "Overlap risk"
    assert result["commit_allowed"] is False


def test_preview_validation_reports_keepout_warning_for_mounting_hole_overlap():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(
        doc,
        {
            "id": "demo",
            "width": 120.0,
            "depth": 80.0,
            "height": 30.0,
            "mounting_holes": [{"id": "mh1", "x": 30.0, "y": 30.0, "diameter": 3.0}],
        },
    )

    result = PreviewValidationService(controller_service=controller_service).validate_place(
        doc,
        template_id="omron_b3f_1000",
        x=30.0,
        y=30.0,
    )

    assert result["valid"] is False
    assert result["status"] == "Keepout warning"
    assert result["commit_allowed"] is False
