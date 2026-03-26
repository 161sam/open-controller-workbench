from __future__ import annotations

import json

from ocw_workbench.freecad_api.model import (
    CONTROLLER_OBJECT_NAME,
    GENERATED_GROUP_NAME,
    OVERLAY_OBJECT_NAME,
    PROJECT_JSON_PROPERTY,
    clear_generated_group,
    get_controller_object,
    get_generated_group,
    group_generated_object,
    iter_generated_objects,
)
from ocw_workbench.freecad_api.state import (
    LEGACY_STATE_JSON_KEY,
    LEGACY_STATE_KEY,
    STATE_CACHE_JSON_KEY,
    STATE_CACHE_KEY,
    STATE_PROPERTY_NAME,
    get_project_state_store,
    get_state_container,
    has_persisted_state,
    read_state,
    write_state,
)


class FakeViewObject:
    def __init__(self) -> None:
        self.Visibility = True
        self.Object = None
        self.Proxy = None


class FakeDocumentObject:
    def __init__(self, document, type_name: str, name: str) -> None:
        self.Document = document
        self.TypeId = type_name
        self.Name = name
        self.Label = name
        self.PropertiesList: list[str] = []
        self.ViewObject = FakeViewObject()
        self.ViewObject.Object = self
        self.editor_modes: dict[str, int] = {}
        self.Group: list[FakeDocumentObject] = []
        self.Proxy = None

    def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
        if name not in self.PropertiesList:
            self.PropertiesList.append(name)
            setattr(self, name, "")

    def setEditorMode(self, name: str, mode: int) -> None:
        self.editor_modes[name] = mode

    def addObject(self, obj) -> None:
        if obj not in self.Group:
            self.Group.append(obj)


class FakeDocument:
    def __init__(self) -> None:
        self.Objects: list[FakeDocumentObject] = []
        self.removed: list[str] = []

    def addObject(self, type_name: str, name: str) -> FakeDocumentObject:
        obj = FakeDocumentObject(self, type_name, name)
        self.Objects.append(obj)
        return obj

    def getObject(self, name: str):
        for obj in self.Objects:
            if obj.Name == name:
                return obj
        return None

    def removeObject(self, name: str) -> None:
        self.removed.append(name)
        self.Objects = [obj for obj in self.Objects if obj.Name != name]


def test_write_state_creates_controller_object_with_persistent_properties():
    doc = FakeDocument()

    write_state(
        doc,
        {
            "controller": {
                "id": "demo",
                "width": 180.0,
                "depth": 110.0,
                "height": 32.0,
                "top_thickness": 3.0,
                "wall_thickness": 4.0,
                "bottom_thickness": 5.0,
                "lid_inset": 1.5,
                "inner_clearance": 0.4,
                "surface": {
                    "shape": "rounded_rect",
                    "corner_radius": 8.0,
                },
            },
            "components": [],
            "meta": {
                "template_id": "encoder_module",
                "variant_id": "encoder_compact",
                "selection": "enc1",
            },
        },
    )

    controller = doc.getObject(CONTROLLER_OBJECT_NAME)

    assert controller is not None
    assert controller.ViewObject.Visibility is True
    assert json.loads(controller.ProjectJson)["controller"]["id"] == "demo"
    assert controller.ControllerId == "demo"
    assert controller.TemplateId == "encoder_module"
    assert controller.VariantId == "encoder_compact"
    assert controller.SelectionId == "enc1"
    assert controller.Width == 180.0
    assert controller.Depth == 110.0
    assert controller.WallThickness == 4.0
    assert controller.SurfaceShape == "rounded_rect"
    assert controller.CornerRadius == 8.0


def test_read_state_prefers_controller_object_payload():
    doc = FakeDocument()
    write_state(doc, {"controller": {"id": "persisted"}, "components": [], "meta": {}})

    state = read_state(doc)

    assert state is not None
    assert state["controller"]["id"] == "persisted"
    assert has_persisted_state(doc) is True


def test_project_state_store_loads_existing_controller_state():
    doc = FakeDocument()
    controller = get_controller_object(doc, create=True)
    controller.ProjectJson = json.dumps({"controller": {"id": "existing"}, "components": [], "meta": {}})

    state = get_project_state_store(doc).load()

    assert state is not None
    assert state["controller"]["id"] == "existing"


def test_project_state_store_records_load_and_save_metrics():
    doc = FakeDocument()

    write_state(doc, {"controller": {"id": "metrics-demo"}, "components": [], "meta": {}})
    state = read_state(doc)

    assert state is not None
    assert doc.OCWStateMetrics["save"]["source"] == "controller"
    assert doc.OCWStateMetrics["save"]["payload_bytes"] > 0
    assert doc.OCWStateMetrics["load"]["source"] == "primary"
    assert doc.OCWStateMetrics["load"]["controller_id"] == "metrics-demo"


def test_read_state_migrates_legacy_state_container_into_controller_object():
    doc = FakeDocument()
    legacy = get_state_container(doc, create=True)
    legacy.StateJson = json.dumps({"controller": {"id": "legacy"}, "components": [], "meta": {}})

    state = read_state(doc)
    controller = doc.getObject(CONTROLLER_OBJECT_NAME)

    assert state is not None
    assert state["controller"]["id"] == "legacy"
    assert controller is not None
    assert json.loads(controller.ProjectJson)["controller"]["id"] == "legacy"
    assert legacy.StateJson


def test_project_state_store_migrates_legacy_document_metadata():
    doc = FakeDocument()
    setattr(doc, LEGACY_STATE_JSON_KEY, json.dumps({"controller": {"id": "legacy-doc"}, "components": [], "meta": {}}))

    state = get_project_state_store(doc).load()
    controller = doc.getObject(CONTROLLER_OBJECT_NAME)

    assert state is not None
    assert state["controller"]["id"] == "legacy-doc"
    assert controller is not None
    assert json.loads(controller.ProjectJson)["controller"]["id"] == "legacy-doc"
    assert not hasattr(doc, LEGACY_STATE_KEY)
    assert not hasattr(doc, LEGACY_STATE_JSON_KEY)


def test_generated_group_reuses_single_group_container():
    doc = FakeDocument()

    first = get_generated_group(doc, create=True)
    second = get_generated_group(doc, create=True)

    assert first is second
    assert first.Name == GENERATED_GROUP_NAME


def test_controller_object_uses_featurepython_proxy_and_claims_generated_group_only():
    doc = FakeDocument()

    controller = get_controller_object(doc, create=True)
    generated = get_generated_group(doc, create=True)
    overlay = doc.addObject("App::FeaturePython", OVERLAY_OBJECT_NAME)
    overlay.Label = "OCW Overlay"

    claimed = controller.ViewObject.Proxy.claimChildren()

    assert controller.Proxy is not None
    assert controller.ViewObject.Proxy is not None
    assert controller.ViewObject.Visibility is True
    assert generated.ViewObject.Visibility is True
    assert generated in claimed
    assert overlay not in claimed


def test_controller_proxy_execute_syncs_properties_from_project_json():
    doc = FakeDocument()
    controller = get_controller_object(doc, create=True)
    controller.ProjectJson = json.dumps(
        {
            "controller": {
                "id": "demo",
                "width": 190.0,
                "depth": 120.0,
                "height": 34.0,
                "top_thickness": 3.5,
                "surface": {"shape": "rounded_rect", "corner_radius": 6.0},
            },
            "components": [],
            "meta": {"template_id": "encoder_module", "variant_id": "compact", "selection": "enc1"},
        }
    )

    controller.Proxy.execute(controller)

    assert controller.ControllerId == "demo"
    assert controller.TemplateId == "encoder_module"
    assert controller.VariantId == "compact"
    assert controller.SelectionId == "enc1"
    assert controller.Width == 190.0
    assert controller.SurfaceShape == "rounded_rect"
    assert controller.CornerRadius == 6.0


def test_controller_proxy_updates_project_json_from_mirrored_properties():
    doc = FakeDocument()
    controller = get_controller_object(doc, create=True)
    write_state(doc, {"controller": {"id": "demo", "width": 160.0, "depth": 100.0}, "components": [], "meta": {}})

    controller.Width = 210.0
    controller.SurfaceShape = "rounded_rect"
    controller.CornerRadius = 9.0
    controller.Proxy.onChanged(controller, "Width")
    controller.Proxy.onChanged(controller, "SurfaceShape")
    controller.Proxy.onChanged(controller, "CornerRadius")

    payload = json.loads(getattr(controller, PROJECT_JSON_PROPERTY))

    assert payload["controller"]["width"] == 210.0
    assert payload["controller"]["surface"]["shape"] == "rounded_rect"
    assert payload["controller"]["surface"]["corner_radius"] == 9.0


def test_controller_proxy_restore_rebinds_and_resyncs_properties():
    doc = FakeDocument()
    controller = get_controller_object(doc, create=True)
    controller.ProjectJson = json.dumps(
        {
            "controller": {"id": "restored", "width": 175.0, "depth": 105.0},
            "components": [],
            "meta": {"template_id": "transport_module"},
        }
    )
    controller.ControllerId = ""
    controller.Width = 0.0
    controller.TemplateId = ""

    controller.Proxy.onDocumentRestored(controller)

    assert controller.Proxy.Object is controller
    assert controller.ControllerId == "restored"
    assert controller.Width == 175.0
    assert controller.TemplateId == "transport_module"


def test_write_state_uses_controller_as_primary_store_and_runtime_cache():
    doc = FakeDocument()

    write_state(doc, {"controller": {"id": "primary"}, "components": [], "meta": {}})

    controller = doc.getObject(CONTROLLER_OBJECT_NAME)

    assert controller is not None
    assert json.loads(controller.ProjectJson)["controller"]["id"] == "primary"
    assert getattr(doc, STATE_CACHE_KEY)["controller"]["id"] == "primary"
    assert not hasattr(doc, STATE_CACHE_JSON_KEY)
    assert not hasattr(doc, LEGACY_STATE_KEY)
    assert not hasattr(doc, LEGACY_STATE_JSON_KEY)


def test_iter_generated_objects_uses_group_membership_only():
    doc = FakeDocument()
    group = get_generated_group(doc, create=True)
    generated = doc.addObject("Part::Feature", "ControllerBody")
    foreign = doc.addObject("Part::Feature", "OCW_Stray")
    overlay = doc.addObject("App::FeaturePython", OVERLAY_OBJECT_NAME)
    overlay.Label = "OCW Overlay"

    group_generated_object(doc, generated)
    members = iter_generated_objects(doc)

    assert group is not None
    assert members == [generated]
    assert foreign not in members
    assert overlay not in members


def test_clear_generated_group_removes_only_group_members():
    doc = FakeDocument()
    get_controller_object(doc, create=True)
    group = get_generated_group(doc, create=True)
    generated_one = doc.addObject("Part::Feature", "ControllerBody")
    generated_two = doc.addObject("Part::Feature", "TopPlate")
    foreign = doc.addObject("Part::Feature", "UserSketch")
    overlay = doc.addObject("App::FeaturePython", OVERLAY_OBJECT_NAME)
    overlay.Label = "OCW Overlay"

    group_generated_object(doc, generated_one)
    group_generated_object(doc, generated_two)
    clear_generated_group(doc)

    assert group is not None
    assert doc.getObject(CONTROLLER_OBJECT_NAME) is not None
    assert doc.getObject(OVERLAY_OBJECT_NAME) is overlay
    assert doc.getObject("UserSketch") is foreign
    assert doc.getObject("ControllerBody") is None
    assert doc.getObject("TopPlate") is None
    assert group.Group == []
    assert doc.removed == ["ControllerBody", "TopPlate"]
