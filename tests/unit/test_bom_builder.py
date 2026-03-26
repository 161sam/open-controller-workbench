from ocw_workbench.manufacturing.bom_builder import BomBuilder


def test_bom_builder_aggregates_identical_components_and_adds_mechanical_parts():
    builder = BomBuilder()
    controller = {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0, "surface": {"width": 120.0, "height": 80.0}}
    components = [
        {"id": "enc1", "type": "encoder", "library_ref": "alps_ec11e15204a3"},
        {"id": "enc2", "type": "encoder", "library_ref": "alps_ec11e15204a3"},
        {"id": "btn1", "type": "button", "library_ref": "omron_b3f_1000"},
    ]

    bom = builder.build(controller, components)

    encoder_item = next(item for item in bom["items"] if item["component"] == "alps_ec11e15204a3")
    top_plate = next(item for item in bom["items"] if item["component"] == "top_plate")
    assert encoder_item["quantity"] == 2
    assert encoder_item["manufacturer"] == "Alps Alpine"
    assert top_plate["material"] == "acrylic"


def test_bom_builder_warns_on_missing_library_data():
    builder = BomBuilder()
    controller = {"id": "demo", "width": 100.0, "depth": 60.0, "height": 30.0, "top_thickness": 3.0}
    components = [{"id": "x1", "type": "button", "library_ref": "missing_ref"}]

    bom = builder.build(controller, components)

    assert bom["warnings"]
    assert any(item["component"] == "missing_ref" for item in bom["items"])
