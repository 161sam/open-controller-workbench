from ocw_kicad.plugin import build_roundtrip_import_descriptor
from ocw_workbench.pipeline.runner import PipelineRunner
from ocw_workbench.utils.yaml_io import dump_yaml


def test_kicad_layout_export_includes_mechanical_stackup_mounting_and_roundtrip(tmp_path):
    runner = PipelineRunner()
    controller = {
        "id": "demo",
        "width": 120.0,
        "depth": 80.0,
        "height": 30.0,
        "top_thickness": 3.0,
        "bottom_thickness": 3.0,
        "wall_thickness": 3.0,
        "inner_clearance": 0.35,
        "pcb_thickness": 1.6,
        "pcb_inset": 8.0,
        "pcb_standoff_height": 8.0,
        "mounting": {"fastener_type": "m3_pan_head"},
        "mounting_holes": [{"id": "mh1", "x": 15.0, "y": 12.0, "diameter": 3.2}],
        "surface": {"shape": "rounded_rect", "width": 120.0, "height": 80.0, "corner_radius": 4.0},
    }
    components = [
        {
            "id": "btn1",
            "type": "button",
            "library_ref": "omron_b3f_1000",
            "x": 30.0,
            "y": 25.0,
            "rotation": 0.0,
        }
    ]

    payload = runner._build_kicad_layout("demo", controller, components)
    layout_path = tmp_path / "demo.kicad.layout.yaml"
    dump_yaml(layout_path, payload)
    descriptor = build_roundtrip_import_descriptor(layout_path)

    assert payload["mechanical_stackup"]["pcb"]["thickness_mm"] == 1.6
    assert payload["mechanical_stackup"]["pcb"]["reference"]["z"] == 11.0
    assert payload["mounting"]["fasteners"][0]["id"] == "mh1"
    assert payload["mounting"]["fasteners"][0]["fastener_type"] == "m3_pan_head"
    assert payload["roundtrip"]["import_strategy"] == "kicad_stepup_board_import"
    assert descriptor["component_reference_key"] == "component_id"
    assert descriptor["pcb_reference"]["top_z"] == 12.6
