from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release-v0.1.yml"


def test_release_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_release_workflow_has_expected_triggers_and_assets() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    trigger_block = workflow.get("on", workflow.get(True))

    assert workflow["name"] == "Release v0.1"
    assert trigger_block["push"]["tags"] == ["v0.1.0"]
    assert "workflow_dispatch" in trigger_block

    steps = workflow["jobs"]["build-and-release"]["steps"]
    uses = [step.get("uses", "") for step in steps]
    runs = [step.get("run", "") for step in steps]

    assert any("actions/checkout" in value for value in uses)
    assert any("actions/setup-python" in value for value in uses)
    assert any("softprops/action-gh-release" in value for value in uses)
    assert any("python -m build --sdist --wheel" in value for value in runs)
    assert any("test_release_metadata.py" in value for value in runs)
    assert any("test_release_workflow_metadata.py" in value for value in runs)

    release_step = next(step for step in steps if step.get("uses", "").startswith("softprops/action-gh-release"))
    files_block = release_step["with"]["files"]
    assert "dist/*.tar.gz" in files_block
    assert "dist/*.whl" in files_block
    assert "dist/release/*.zip" in files_block
    assert release_step["with"]["body_path"] == "RELEASE_NOTES_v0.1.md"
