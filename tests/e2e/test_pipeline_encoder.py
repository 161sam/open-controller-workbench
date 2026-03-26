from pathlib import Path

from ocw_workbench.pipeline.runner import run_full_pipeline


def test_encoder_pipeline_runs_end_to_end(tmp_path: Path):
    result = run_full_pipeline("examples/projects/encoder_module_demo.yaml", output_dir=tmp_path)

    assert len(result["generated_project"]["components"]) == 4
    assert len(result["layout_result"]["placed_components"]) == 4
    assert not result["constraint_report"]["errors"]
    assert len(result["kicad_layout"]["footprints"]) == 4
    assert result["electrical_mapping"]["signals"]
    assert result["schematic"]["components"]
    assert Path(result["output_paths"]["kicad_layout"]).exists()
