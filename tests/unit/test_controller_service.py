from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.document_sync_service import SyncMode


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.removed = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


class FakeFeatureDocument(FakeDocument):
    def __init__(self) -> None:
        super().__init__()
        self._objects_by_name = {}

    def addObject(self, type_name: str, name: str):
        obj = FakeFeature(type_name, name)
        self.Objects.append(obj)
        self._objects_by_name[name] = obj
        return obj

    def getObject(self, name: str):
        return self._objects_by_name.get(name)

    def removeObject(self, name: str) -> None:
        self.removed.append(name)
        self.Objects = [obj for obj in self.Objects if obj.Name != name]
        self._objects_by_name.pop(name, None)


class FakeFeature:
    def __init__(self, type_name: str, name: str) -> None:
        self.TypeId = type_name
        self.Name = name
        self.Label = name
        self.PropertiesList = []
        self.Group = []
        self.ViewObject = type("FakeViewObject", (), {"Visibility": True, "ShapeColor": None, "LineColor": None})()

    def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
        if name not in self.PropertiesList:
            self.PropertiesList.append(name)
            setattr(self, name, "")

    def setEditorMode(self, _name: str, _mode: int) -> None:
        return

    def addObject(self, obj) -> None:
        if obj not in self.Group:
            self.Group.append(obj)


def test_create_controller_and_add_components_without_freecad_objects():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 100.0})
    service.add_component(doc, "alps_ec11e15204a3", x=20.0, y=20.0)
    service.add_component(doc, "omron_b3f_1000", x=40.0, y=20.0)

    state = service.get_state(doc)

    assert state["controller"]["id"] == "demo"
    assert len(state["components"]) == 2
    assert doc.OCWLastSync["component_count"] == 2


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


def test_select_component_uses_visual_refresh_without_recompute():
    service = ControllerService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo"})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=10.0, y=10.0)
    recomputes_before = doc.recompute_count

    state = service.select_component(doc, "enc1")

    assert state["meta"]["selection"] == "enc1"
    assert doc.recompute_count == recomputes_before
    assert doc.OCWLastSync["sync_mode"] == "visual_only"
    assert doc.OCWLastSync["requested_sync_mode"] == "visual_only"


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


def test_create_from_variant_uses_variant_layout_config_for_initial_positions():
    service = ControllerService()
    doc = FakeDocument()

    state = service.create_from_variant(doc, "pad_grid_4x4_oled")

    assert state["meta"]["template_id"] == "pad_grid_4x4"
    assert state["meta"]["variant_id"] == "pad_grid_4x4_oled"
    assert state["meta"]["layout"]["strategy"] == "zone"
    assert state["meta"]["layout"]["config"]["rows"] == 4
    assert state["meta"]["layout"]["config"]["cols"] == 4
    assert state["meta"]["layout"]["config"]["spacing_x_mm"] == 36.0
    assert state["meta"]["layout"]["config"]["spacing_y_mm"] == 36.0
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


def test_create_from_template_pad_grid_uses_template_layout_without_cutout_overlap():
    service = ControllerService()
    doc = FakeDocument()

    state = service.create_from_template(doc, "pad_grid_4x4")

    assert len(state["components"]) == 16
    assert state["meta"]["layout"]["strategy"] == "grid"
    assert state["meta"]["layout"]["source"] == "template"
    assert state["meta"]["layout"]["config"]["rows"] == 4
    assert state["meta"]["layout"]["config"]["cols"] == 4
    assert state["meta"]["layout"]["config"]["spacing_x_mm"] == 36.0
    assert state["meta"]["layout"]["config"]["spacing_y_mm"] == 36.0
    assert state["meta"]["layout"]["config"]["padding_mm"] == 10.0

    placements = [(component["x"], component["y"]) for component in state["components"]]
    assert len(set(placements)) == 16
    assert {x for x, _y in placements} == {36.0, 72.0, 108.0, 144.0}
    assert {y for _x, y in placements} == {36.0, 72.0, 108.0, 144.0}
    assert all(15.0 <= component["x"] - 15.0 <= 135.0 for component in state["components"])
    assert all(15.0 <= component["y"] - 15.0 <= 135.0 for component in state["components"])

    for index, first in enumerate(state["components"]):
        for second in state["components"][index + 1:]:
            overlap_x = abs(first["x"] - second["x"]) < 30.0
            overlap_y = abs(first["y"] - second["y"]) < 30.0
            assert not (overlap_x and overlap_y)


def test_sync_document_uses_central_controller_object_and_generated_group(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            return self.doc.addObject("Part::Feature", "TopPlate")

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()

    service.create_controller(doc, {"id": "demo"})

    controller = doc.getObject("OCW_Controller")
    generated = doc.getObject("OCW_Generated")

    assert controller is not None
    assert generated is not None
    assert controller.ProjectJson
    assert [obj.Label for obj in generated.Group] == ["OCW_ControllerBody", "OCW_TopPlate"]
    assert doc.OCWLastSync["controller_object"] == "OCW_Controller"
    assert doc.OCWLastSync["generated_group"] == "OCW_Generated"
    assert doc.OCWLastSync["requested_sync_mode"] == "full"
    assert doc.OCWLastSync["builder_body_generation_ms"] >= 0.0
    assert doc.OCWLastSync["builder_top_plate_generation_ms"] >= 0.0
    assert doc.OCWLastSync["cutout_generation_ms"] >= 0.0
    assert doc.OCWLastSync["boolean_phase_ms"] >= 0.0
    assert doc.OCWLastSync["document_recompute_ms"] >= 0.0


def test_sync_document_records_detailed_profile_metrics_when_enabled(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            top = self.doc.addObject("Part::Feature", "TopPlate")
            top.Shape = type("Shape", (), {"BoundBox": type("BoundBox", (), {"ZMin": 0.0, "ZLength": 3.0})(), "copy": lambda self: self})()
            return top

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    doc.OCWDebugProfiling = {"enabled": True, "log": False}

    service.create_controller(doc, {"id": "demo"})

    profile = doc.OCWPerformance["sections"]["sync"]

    assert profile["full_sync"]["duration_ms"] >= 0.0
    assert profile["builder_body_generation_ms"]["duration_ms"] >= 0.0
    assert profile["builder_top_plate_generation_ms"]["duration_ms"] >= 0.0
    assert profile["boolean_phase_ms"]["duration_ms"] >= 0.0


def test_sync_document_clears_only_group_managed_objects(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            return self.doc.addObject("Part::Feature", "TopPlate")

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.document_sync_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    user_obj = doc.addObject("Part::Feature", "UserSolid")

    service.create_controller(doc, {"id": "demo"})
    first_generated_names = sorted(obj.Name for obj in doc.getObject("OCW_Generated").Group)

    assert user_obj in doc.Objects

    service.sync_document(doc)

    second_generated_names = sorted(obj.Name for obj in doc.getObject("OCW_Generated").Group)
    assert first_generated_names == second_generated_names
    assert doc.getObject("UserSolid") is user_obj


def test_partial_ready_sync_mode_currently_falls_back_to_full(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            return self.doc.addObject("Part::Feature", "TopPlate")

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.document_sync_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    state = service.create_controller(doc, {"id": "demo"})

    service.update_document(doc, mode=SyncMode.PARTIAL_READY, state=state)

    assert doc.OCWLastSync["requested_sync_mode"] == "partial_ready"
    assert doc.OCWLastSync["sync_mode"] == "full"


def test_sync_document_does_not_materialize_keepout_markers_by_default(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            return self.doc.addObject("Part::Feature", "TopPlate")

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            raise AssertionError("keepouts must stay in overlay-only mode unless debug markers are enabled")

    monkeypatch.setattr("ocw_workbench.services.document_sync_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()

    service.create_controller(doc, {"id": "demo", "height": 30.0})

    assert sorted(obj.Label for obj in doc.getObject("OCW_Generated").Group) == ["OCW_ControllerBody", "OCW_TopPlate"]


def test_sync_document_can_materialize_keepout_markers_in_debug_mode(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            return self.doc.addObject("Part::Feature", "ControllerBody")

        def build_top_plate(self, _controller):
            return self.doc.addObject("Part::Feature", "TopPlate")

        def apply_cutouts(self, top, _components):
            top.Shape = "cut"
            return top

        def build_keepouts(self, _components):
            return [{"component_id": "btn1", "feature": "keepout_top", "shape": "circle", "diameter": 20.0, "x": 30.0, "y": 20.0}]

    def fake_create_cylinder(doc, name, **_kwargs):
        return doc.addObject("Part::Feature", name)

    monkeypatch.setattr("ocw_workbench.services.document_sync_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.document_sync_service.freecad_gui.focus_view", lambda _doc, fit=True: True)
    monkeypatch.setattr("ocw_workbench.freecad_api.shapes.create_cylinder", fake_create_cylinder)

    service = ControllerService()
    doc = FakeFeatureDocument()
    doc.OCWDebugUI = {"materialize_component_markers": True}

    service.create_controller(doc, {"id": "demo", "height": 30.0})

    labels = sorted(obj.Label for obj in doc.getObject("OCW_Generated").Group)
    assert labels == ["OCW_ControllerBody", "OCW_TopPlate", "OCW_btn1_keepout_top"]


def test_repeated_sync_document_keeps_document_object_count_bounded(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            obj = self.doc.addObject("Part::Feature", "ControllerBody")
            obj.Shape = "body"
            return obj

        def build_top_plate(self, _controller):
            obj = self.doc.addObject("Part::Feature", "TopPlate")
            obj.Shape = type("Shape", (), {"BoundBox": type("BoundBox", (), {"ZMin": 0.0, "ZLength": 3.0})(), "copy": lambda self: self})()
            return obj

        def apply_cutouts(self, top, _components):
            top.Shape = "top-cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    service.create_controller(doc, {"id": "demo"})
    for index in range(17):
        service.add_component(doc, "omron_b3f_1000", component_id=f"btn{index + 1}", x=10.0 + index, y=20.0)

    service.sync_document(doc)
    stable_names = sorted(obj.Name for obj in doc.Objects)
    stable_count = len(doc.Objects)

    for _ in range(3):
        service.sync_document(doc)
        assert len(doc.Objects) == stable_count
        assert sorted(obj.Name for obj in doc.Objects) == stable_names
        assert not any(obj.Name.startswith("cutout_") for obj in doc.Objects)
        assert not any(obj.Name.startswith("TopPlate_") for obj in doc.Objects)


def test_pad_grid_sync_keeps_only_final_generated_objects(monkeypatch):
    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            obj = self.doc.addObject("Part::Feature", "ControllerBody")
            obj.Shape = "body"
            return obj

        def build_top_plate(self, _controller):
            obj = self.doc.addObject("Part::Feature", "TopPlate")
            obj.Shape = type("Shape", (), {"BoundBox": type("BoundBox", (), {"ZMin": 0.0, "ZLength": 3.0})(), "copy": lambda self: self})()
            return obj

        def apply_cutouts(self, top, components):
            top.Shape = f"top-cut-{len(components)}"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    service.create_from_template(doc, "pad_grid_4x4")

    labels = sorted(obj.Label for obj in doc.Objects if obj.Name not in {"OCW_Controller", "OCW_Generated"})

    assert labels == ["OCW_ControllerBody", "OCW_TopPlateCut"]
    assert not any(obj.Name.startswith("cutout_") for obj in doc.Objects)
    assert not any(obj.Name.startswith("TopPlate_") for obj in doc.Objects)


def test_sync_document_preserves_single_overlay_object(monkeypatch):
    from ocw_workbench.gui.overlay.renderer import OverlayRenderer

    class FakeBuilder:
        def __init__(self, doc):
            self.doc = doc

        def build_body(self, _controller):
            obj = self.doc.addObject("Part::Feature", "ControllerBody")
            obj.Shape = "body"
            return obj

        def build_top_plate(self, _controller):
            obj = self.doc.addObject("Part::Feature", "TopPlate")
            obj.Shape = type("Shape", (), {"BoundBox": type("BoundBox", (), {"ZMin": 0.0, "ZLength": 3.0})(), "copy": lambda self: self})()
            return obj

        def apply_cutouts(self, top, _components):
            top.Shape = "top-cut"
            return top

        def build_keepouts(self, _components):
            return []

    monkeypatch.setattr("ocw_workbench.services.controller_service.ControllerBuilder", FakeBuilder)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.reveal_generated_objects", lambda _doc: 0)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.activate_document", lambda _doc: True)
    monkeypatch.setattr("ocw_workbench.services.controller_service.freecad_gui.focus_view", lambda _doc, fit=True: True)

    service = ControllerService()
    doc = FakeFeatureDocument()
    renderer = OverlayRenderer()

    service.create_controller(doc, {"id": "demo"})
    renderer.render(
        doc,
        {
            "enabled": True,
            "controller_height": 10.0,
            "items": [
                {"id": "surface", "type": "rect", "geometry": {"x": 20.0, "y": 20.0, "width": 40.0, "height": 20.0}, "style": {}},
                {"id": "label", "type": "text_marker", "geometry": {"x": 20.0, "y": 20.0}, "style": {}, "label": "Demo"},
            ],
        },
    )

    overlay = doc.getObject("OCW_Overlay")

    assert overlay is not None

    for _ in range(3):
        service.sync_document(doc)
        assert doc.getObject("OCW_Overlay") is overlay
        renderer.render(
            doc,
            {
                "enabled": True,
                "controller_height": 10.0,
                "items": [
                    {"id": "surface", "type": "rect", "geometry": {"x": 20.0, "y": 20.0, "width": 40.0, "height": 20.0}, "style": {}},
                    {"id": "line", "type": "line", "geometry": {"start_x": 0.0, "start_y": 0.0, "end_x": 10.0, "end_y": 10.0}, "style": {}},
                ],
            },
        )
        assert doc.getObject("OCW_Overlay") is overlay
        assert len([obj for obj in doc.Objects if obj.Name == "OCW_Overlay"]) == 1
        assert not any(obj.Name.startswith("OCW_OVERLAY_") for obj in doc.Objects)
