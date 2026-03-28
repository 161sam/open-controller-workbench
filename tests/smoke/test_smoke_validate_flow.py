from ocw_workbench.services.controller_service import ControllerService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []

    def recompute(self) -> None:
        return


def test_validate_report_is_reachable_from_document_state():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 110.0})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=24.0, y=24.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=72.0, y=24.0)

    report = service.validate_layout(doc)
    context = service.get_ui_context(doc)

    assert report["summary"]["total_count"] >= 0
    assert context["validation"] is not None
    assert context["validation"]["summary"] == report["summary"]
