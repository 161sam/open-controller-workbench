from pathlib import Path

from ocw_workbench.pipeline.runner import run_full_pipeline


def test_pad_pipeline_runs_end_to_end(tmp_path: Path):
    result = run_full_pipeline("examples/projects/pad_grid_demo.yaml", output_dir=tmp_path)

    pad_components = [component for component in result["generated_project"]["components"] if component["type"] == "pad"]
    assert len(pad_components) == 16
    assert len(result["layout_result"]["placed_components"]) == 17
    assert not result["constraint_report"]["errors"]
    assert any(item["strategy"] == "matrix" for item in result["electrical_mapping"]["assignments"])
    assert result["schematic"]["connections"]
    assert Path(result["output_paths"]["schematic"]).exists()
