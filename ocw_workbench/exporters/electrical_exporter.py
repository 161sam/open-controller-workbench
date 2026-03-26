from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.utils.yaml_io import dump_yaml


def export_electrical_mapping(data: dict[str, Any], path: str | Path) -> None:
    dump_yaml(path, data)
