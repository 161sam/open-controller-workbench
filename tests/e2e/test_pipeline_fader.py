from pathlib import Path

from ocw_workbench.pipeline.runner import run_full_pipeline


def test_fader_pipeline_runs_end_to_end(tmp_path: Path):
    result = run_full_pipeline("examples/projects/fader_strip_demo.yaml", output_dir=tmp_path)

    fader = next(component for component in result["generated_project"]["components"] if component["id"] == "fader1")
    assert fader["library_ref"] == "generic_60mm_linear_fader"
    assert len(result["layout_result"]["placed_components"]) == 4
    assert not result["constraint_report"]["errors"]
    assert any(component["id"] == "fader1" for component in result["electrical_mapping"]["components"])
    assert result["schematic"]["nets"]
    assert Path(result["output_paths"]["electrical"]).exists()
