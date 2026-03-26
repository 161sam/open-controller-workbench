from pathlib import Path

from ocw_workbench.pipeline.runner import run_full_pipeline


def test_all_demo_projects_export(tmp_path: Path):
    project_paths = sorted(Path("examples/projects").glob("*.yaml"))

    assert project_paths
    for project_path in project_paths:
        result = run_full_pipeline(project_path, output_dir=tmp_path / project_path.stem)
        assert "board" in result["kicad_layout"]
        assert result["kicad_layout"]["footprints"] is not None
        assert result["electrical_mapping"]["signals"] is not None
        assert result["electrical_mapping"]["assignments"] is not None
        assert result["schematic"]["nets"] is not None
        assert Path(result["output_paths"]["kicad_layout"]).exists()
