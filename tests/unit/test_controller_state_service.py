from __future__ import annotations

from ocw_workbench.services.controller_state_service import ControllerStateService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_state_service_updates_project_state_without_document_sync():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 100.0})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=20.0, y=20.0)
    service.update_component(doc, "enc1", {"x": 55.0, "y": 35.0, "rotation": 15.0})

    state = service.get_state(doc)

    assert state["controller"]["id"] == "demo"
    assert state["components"][0]["x"] == 55.0
    assert state["components"][0]["y"] == 35.0
    assert state["components"][0]["rotation"] == 15.0
    assert doc.recompute_count == 0


def test_state_service_create_from_template_applies_layout_without_sync():
    service = ControllerStateService()
    doc = FakeDocument()

    state = service.create_from_template(doc, "pad_grid_4x4")

    assert len(state["components"]) == 16
    assert state["meta"]["layout"]["strategy"] == "grid"
    assert state["meta"]["layout"]["source"] == "template"
    assert len({(component["x"], component["y"]) for component in state["components"]}) == 16
    assert doc.recompute_count == 0


def test_state_service_select_and_validate_touch_only_state():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    service.select_component(doc, "btn1")
    report = service.validate_layout(doc)
    context = service.get_ui_context(doc)

    assert report["summary"]["error_count"] == 0
    assert context["selection"] == "btn1"
    assert isinstance(context["validation"], dict)
    assert doc.recompute_count == 0
