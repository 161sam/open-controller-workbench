from __future__ import annotations

from typing import Any


def resolve_footprint(
    pcbnew_module: Any,
    footprint_name: str,
) -> Any | None:
    if not isinstance(footprint_name, str) or not footprint_name:
        raise ValueError("Missing or invalid footprint name")

    if ":" not in footprint_name:
        print(f"Skipping footprint {footprint_name}: not found")
        return None

    library_name, footprint_id = footprint_name.split(":", 1)

    if hasattr(pcbnew_module, "FootprintLoad"):
        footprint = pcbnew_module.FootprintLoad(library_name, footprint_id)
        if footprint is None:
            print(f"Skipping footprint {footprint_name}: not found")
        return footprint

    if hasattr(pcbnew_module, "LoadFootprint"):
        footprint = pcbnew_module.LoadFootprint(library_name, footprint_id)
        if footprint is None:
            print(f"Skipping footprint {footprint_name}: not found")
        return footprint

    raise RuntimeError("pcbnew module does not provide a footprint loading API")
