from ocf_freecad.services.controller_service import ControllerService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.removed = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_create_controller_and_add_components_without_freecad_objects():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 100.0})
    service.add_component(doc, "alps_ec11e15204a3", x=20.0, y=20.0)
    service.add_component(doc, "omron_b3f_1000", x=40.0, y=20.0)

    state = service.get_state(doc)

    assert state["controller"]["id"] == "demo"
    assert len(state["components"]) == 2
    assert doc.OCFLastSync["component_count"] == 2


def test_auto_layout_and_validate_work_on_document_state():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 200.0, "depth": 120.0})
    service.add_component(doc, "alps_ec11e15204a3")
    service.add_component(doc, "alps_ec11e15204a3")
    service.add_component(doc, "omron_b3f_1000")
    service.add_component(doc, "omron_b3f_1000")
    service.add_component(doc, "omron_b3f_1000")
    service.add_component(doc, "omron_b3f_1000")
    service.add_component(doc, "adafruit_oled_096_i2c_ssd1306")

    layout = service.auto_layout(doc, strategy="grid", config={"spacing_x_mm": 30.0, "spacing_y_mm": 24.0, "padding_mm": 16.0})
    report = service.validate_layout(doc)

    assert len(layout["placements"]) >= 6
    assert report["summary"]["error_count"] == 0
    assert doc.recompute_count > 0


def test_move_component_updates_state():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo"})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=10.0, y=10.0)
    service.move_component(doc, "enc1", x=55.0, y=35.0, rotation=15.0)

    state = service.get_state(doc)

    assert state["components"][0]["x"] == 55.0
    assert state["components"][0]["y"] == 35.0
    assert state["components"][0]["rotation"] == 15.0


def test_update_controller_updates_geometry_fields():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    state = service.update_controller(
        doc,
        {
            "width": 180.0,
            "depth": 110.0,
            "height": 34.0,
            "wall_thickness": 4.0,
            "bottom_thickness": 5.0,
            "top_thickness": 3.5,
            "lid_inset": 2.0,
            "inner_clearance": 0.5,
            "surface_shape": "rounded_rect",
            "corner_radius": 10.0,
        },
    )

    assert state["controller"]["width"] == 180.0
    assert state["controller"]["depth"] == 110.0
    assert state["controller"]["height"] == 34.0
    assert state["controller"]["wall_thickness"] == 4.0
    assert state["controller"]["surface"]["shape"] == "rounded_rect"
    assert state["controller"]["surface"]["corner_radius"] == 10.0


def test_create_from_template_populates_metadata_and_components():
    service = ControllerService()
    doc = FakeDocument()

    state = service.create_from_template(doc, "encoder_module")

    assert state["meta"]["template_id"] == "encoder_module"
    assert state["meta"]["variant_id"] is None
    assert len(state["components"]) == 4
    assert state["meta"]["selection"] == "enc1"
    assert state["meta"]["layout"]["strategy"] == "grid"
    assert state["meta"]["layout"]["source"] == "template"
    assert len({(component["x"], component["y"]) for component in state["components"]}) > 1


def test_create_from_variant_populates_variant_metadata():
    service = ControllerService()
    doc = FakeDocument()

    state = service.create_from_variant(doc, "display_nav_right")

    assert state["meta"]["template_id"] == "display_nav_module"
    assert state["meta"]["variant_id"] == "display_nav_right"
    assert state["controller"]["surface"]["width"] == 200.0
    assert state["meta"]["layout"]["source"] == "template"
    assert any(component["x"] != 0.0 or component["y"] != 0.0 for component in state["components"])


def test_update_select_and_context_work_together():
    service = ControllerService()
    doc = FakeDocument()

    service.create_from_template(doc, "transport_module")
    service.select_component(doc, "play")
    service.update_component(doc, "play", {"x": 44.0, "y": 22.0, "rotation": 5.0})
    service.auto_layout(doc, strategy="row", config={"spacing_mm": 24.0, "padding_mm": 8.0})
    service.validate_layout(doc)

    component = service.get_component(doc, "play")
    context = service.get_ui_context(doc)

    assert component["rotation"] == 5.0 or component["rotation"] == 0.0
    assert context["selection"] == "play"
    assert context["template_id"] == "transport_module"
    assert context["layout"]["strategy"] == "row"
    assert isinstance(context["validation"], dict)


def test_create_from_template_uses_fallback_grid_when_layout_is_missing():
    class FakeTemplateService:
        def generate_from_template(self, template_id, overrides=None):
            return {
                "template": {"id": template_id},
                "controller": {
                    "id": template_id,
                    "width": 120.0,
                    "depth": 80.0,
                    "height": 30.0,
                    "top_thickness": 3.0,
                    "surface": {"shape": "rectangle", "width": 120.0, "height": 80.0},
                    "mounting_holes": [],
                    "reserved_zones": [],
                    "layout_zones": [],
                },
                "components": [
                    {"id": "a", "type": "button", "library_ref": "omron_b3f_1000", "x": 0.0, "y": 0.0, "rotation": 0.0},
                    {"id": "b", "type": "button", "library_ref": "omron_b3f_1000", "x": 0.0, "y": 0.0, "rotation": 0.0},
                    {"id": "c", "type": "button", "library_ref": "omron_b3f_1000", "x": 0.0, "y": 0.0, "rotation": 0.0},
                ],
                "layout": {},
            }

    service = ControllerService(template_service=FakeTemplateService())
    doc = FakeDocument()

    state = service.create_from_template(doc, "fallback_demo")

    assert state["meta"]["layout"]["strategy"] == "grid"
    assert state["meta"]["layout"]["source"] == "fallback"
    assert len({(component["x"], component["y"]) for component in state["components"]}) == 3
    assert all(component["x"] != 0.0 or component["y"] != 0.0 for component in state["components"])
