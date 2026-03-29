from __future__ import annotations

from pathlib import Path

import tomllib

import ocw_workbench


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_version_is_consistent() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    version_file = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert project_version == "0.1.0"
    assert ocw_workbench.__version__ == project_version
    assert version_file == project_version


def test_release_documents_exist() -> None:
    assert (REPO_ROOT / "CHANGELOG.md").exists()
    assert (REPO_ROOT / "RELEASE_NOTES_v0.1.md").exists()
    assert (REPO_ROOT / "docs" / "README.md").exists()
    assert (REPO_ROOT / "docs" / "release-checklist.md").exists()
    assert (REPO_ROOT / "examples" / "README.md").exists()
    assert (REPO_ROOT / "screenshots" / "README.md").exists()


def test_manifest_and_packaging_cover_runtime_resources() -> None:
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "recursive-include resources" in manifest
    data_files = pyproject["tool"]["setuptools"]["data-files"]
    assert "resources/icons" in data_files
    assert "resources/icons/components" in data_files


def test_runtime_resource_and_registry_files_exist() -> None:
    required_paths = [
        REPO_ROOT / "InitGui.py",
        REPO_ROOT / "resources" / "icons" / "workbench.svg",
        REPO_ROOT / "resources" / "icons" / "default.svg",
        REPO_ROOT / "ocw_workbench" / "templates" / "library" / "encoder_module.yaml",
        REPO_ROOT / "ocw_workbench" / "variants" / "library" / "encoder_module_compact.yaml",
        REPO_ROOT / "ocw_workbench" / "library" / "components" / "encoders.yaml",
    ]

    for path in required_paths:
        assert path.exists(), path


def test_release_demo_templates_exist() -> None:
    required_templates = {
        "pad_grid_4x4",
        "encoder_module",
        "fader_strip",
    }
    template_dir = REPO_ROOT / "ocw_workbench" / "templates" / "library"
    present = {path.stem for path in template_dir.glob("*.yaml")}

    assert required_templates.issubset(present)
