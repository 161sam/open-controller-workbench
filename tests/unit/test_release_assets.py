from __future__ import annotations

from pathlib import Path
import zipfile

from ocw_workbench.utils.release_assets import (
    MODULE_ROOT_NAME,
    build_checksum_file,
    build_workbench_archive,
    checksum_file_name,
    collect_release_files,
    workbench_archive_name,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_workbench_archive_contains_runtime_paths_and_no_test_tree(tmp_path: Path) -> None:
    archive_path = build_workbench_archive(REPO_ROOT, tmp_path, "v0.1.0")

    assert archive_path.name == workbench_archive_name("v0.1.0")

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())

    assert f"{MODULE_ROOT_NAME}/InitGui.py" in names
    assert f"{MODULE_ROOT_NAME}/LICENSE" in names
    assert f"{MODULE_ROOT_NAME}/VERSION" in names
    assert f"{MODULE_ROOT_NAME}/ocw_workbench/workbench.py" in names
    assert f"{MODULE_ROOT_NAME}/resources/icons/workbench.svg" in names
    assert f"{MODULE_ROOT_NAME}/ocw_workbench/templates/library/encoder_module.yaml" in names
    assert f"{MODULE_ROOT_NAME}/examples/projects/pad_grid_demo.yaml" in names
    assert f"{MODULE_ROOT_NAME}/examples/README.md" in names
    assert f"{MODULE_ROOT_NAME}/docs/plugin-installation.md" in names
    assert not any(name.startswith(f"{MODULE_ROOT_NAME}/tests/") for name in names)
    assert not any("/__pycache__/" in name for name in names)


def test_build_checksum_file_covers_release_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    sdist = dist_dir / "ocw-workbench-0.1.0.tar.gz"
    wheel = dist_dir / "ocw_workbench-0.1.0-py3-none-any.whl"
    sdist.write_bytes(b"sdist")
    wheel.write_bytes(b"wheel")
    archive_path = repo_root / "release" / workbench_archive_name("v0.1.0")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(b"archive")

    release_files = collect_release_files(repo_root, archive_path)
    checksum_path = build_checksum_file(release_files, tmp_path / checksum_file_name("v0.1.0"))
    contents = checksum_path.read_text(encoding="utf-8")

    assert "ocw-workbench-0.1.0.tar.gz" in contents
    assert "ocw_workbench-0.1.0-py3-none-any.whl" in contents
    assert workbench_archive_name("v0.1.0") in contents
