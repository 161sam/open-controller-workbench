from __future__ import annotations

from pathlib import Path
from typing import Any

from ocf_freecad.utils.yaml_io import dump_yaml


def export_schematic(data: dict[str, Any], path: str | Path) -> None:
    dump_yaml(path, data)
