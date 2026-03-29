from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import zipfile


MODULE_ROOT_NAME = "OpenControllerWorkbench"
RUNTIME_TREE_PATHS = [
    "ocw_kicad",
    "ocw_workbench",
    "resources",
    "examples",
    "screenshots",
]
RELEASE_DOC_PATHS = [
    "README.md",
    "CHANGELOG.md",
    "RELEASE_NOTES_v0.1.md",
    "docs/README.md",
    "docs/plugin-installation.md",
    "docs/release-process.md",
    "docs/release-checklist.md",
    "docs/user-guide.md",
]
ROOT_RUNTIME_FILES = [
    "Init.py",
    "InitGui.py",
    "LICENSE",
    "ocw_kicad_plugin.py",
    "VERSION",
]


def workbench_archive_name(tag_name: str) -> str:
    return f"ocw-workbench-{tag_name}-freecad-mod.zip"


def checksum_file_name(tag_name: str) -> str:
    return f"ocw-workbench-{tag_name}-sha256.txt"


def build_workbench_archive(repo_root: Path, output_dir: Path, tag_name: str) -> Path:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / workbench_archive_name(tag_name)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in ROOT_RUNTIME_FILES + RELEASE_DOC_PATHS:
            source = repo_root / relative_path
            if not source.exists():
                continue
            archive.write(source, arcname=str(Path(MODULE_ROOT_NAME) / relative_path))
        for relative_root in RUNTIME_TREE_PATHS:
            source_root = repo_root / relative_root
            if not source_root.exists():
                continue
            for source in sorted(source_root.rglob("*")):
                if source.is_dir():
                    continue
                if _should_skip(source):
                    continue
                archive.write(source, arcname=str(Path(MODULE_ROOT_NAME) / source.relative_to(repo_root)))
    return archive_path


def build_checksum_file(release_files: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for release_file in sorted(release_files, key=lambda item: item.name):
        digest = sha256(release_file.read_bytes()).hexdigest()
        lines.append(f"{digest}  {release_file.name}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def collect_release_files(repo_root: Path, archive_path: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    dist_dir = repo_root / "dist"
    release_files = sorted(dist_dir.glob("*.tar.gz")) + sorted(dist_dir.glob("*.whl"))
    release_files.append(archive_path)
    return release_files


def _should_skip(path: Path) -> bool:
    return (
        "__pycache__" in path.parts
        or path.suffix == ".pyc"
        or ".pytest_cache" in path.parts
        or ".github" in path.parts
        or "tests" in path.parts
    )
