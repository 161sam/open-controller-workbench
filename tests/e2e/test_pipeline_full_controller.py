from pathlib import Path

from ocw_workbench.pipeline.runner import run_full_pipeline


def test_full_controller_pipeline_runs_end_to_end(tmp_path: Path):
    result = run_full_pipeline("examples/projects/full_controller_demo.yaml", output_dir=tmp_path)

    component_types = {component["type"] for component in result["generated_project"]["components"]}
    assert {"display", "encoder", "button", "fader", "pad", "rgb_button"} <= component_types
    assert len(result["layout_result"]["unplaced_component_ids"]) == 0
    assert not result["constraint_report"]["errors"]
    assert len(result["kicad_layout"]["footprints"]) == len(result["layout_result"]["placed_components"])
    assert result["electrical_mapping"]["assignments"]
    assert result["schematic"]["components"]
    assert Path(result["output_paths"]["kicad_layout"]).exists()
    assert result["bom"]["items"]
    assert result["manufacturing"]["parts"]
    assert result["assembly"]["steps"]
    assert Path(result["output_paths"]["bom_yaml"]).exists()
    assert Path(result["output_paths"]["bom_csv"]).exists()
    assert Path(result["output_paths"]["manufacturing"]).exists()
    assert Path(result["output_paths"]["assembly"]).exists()
