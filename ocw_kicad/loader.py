from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.utils.yaml_io import load_yaml


def load_layout(path: str | Path) -> dict[str, Any]:
    payload = load_yaml(path)
    if "board" not in payload:
        raise ValueError(f"Missing required top-level field 'board' in layout: {path}")
    if "footprints" not in payload:
        raise ValueError(f"Missing required top-level field 'footprints' in layout: {path}")
    if not isinstance(payload["board"], dict):
        raise ValueError(f"Field 'board' must be a mapping in layout: {path}")
    if not isinstance(payload["footprints"], list):
        raise ValueError(f"Field 'footprints' must be a list in layout: {path}")

    for field in ("mounting_holes", "keepouts", "warnings"):
        if field not in payload:
            payload[field] = []
        if not isinstance(payload[field], list):
            raise ValueError(f"Field '{field}' must be a list in layout: {path}")

    return payload
