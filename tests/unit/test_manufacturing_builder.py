from ocw_workbench.manufacturing.manufacturing_builder import ManufacturingBuilder


def test_manufacturing_builder_creates_parts_and_operations():
    builder = ManufacturingBuilder()
    controller = {
        "id": "demo",
        "width": 160.0,
        "depth": 90.0,
        "height": 30.0,
        "top_thickness": 3.0,
        "surface": {"shape": "rectangle", "width": 160.0, "height": 90.0},
        "mounting_holes": [{"id": "mh1", "x": 15.0, "y": 15.0, "diameter": 3.2}],
    }
    components = [{"id": "enc1", "type": "encoder", "x": 40.0, "y": 30.0, "library_ref": "alps_ec11e15204a3"}]

    result = builder.build(controller, components)

    assert any(part["part_id"] == "top_plate" for part in result["parts"])
    assert any(operation["type"] == "circular_hole" for operation in result["panel_operations"])
    assert any(operation["type"] == "mounting_hole" for operation in result["panel_operations"])
    assert result["recommended_processes"]["top_plate"] == "laser_cut"
