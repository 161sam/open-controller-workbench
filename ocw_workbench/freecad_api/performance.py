from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    import FreeCAD as App
except ImportError:
    App = None

from ocw_workbench.freecad_api.metadata import get_document_data, set_document_data

PERFORMANCE_FLAG_KEY = "OCWDebugProfiling"
PERFORMANCE_DATA_KEY = "OCWPerformance"


def profiling_options(doc: Any) -> dict[str, bool]:
    raw = get_document_data(doc, PERFORMANCE_FLAG_KEY, False)
    if isinstance(raw, dict):
        enabled = bool(raw.get("enabled", False))
        return {
            "enabled": enabled,
            "log": bool(raw.get("log", enabled)),
        }
    enabled = bool(raw)
    return {
        "enabled": enabled,
        "log": enabled,
    }


def profiling_enabled(doc: Any) -> bool:
    return bool(profiling_options(doc).get("enabled", False))


def record_profile_metric(
    doc: Any,
    section: str,
    metric: str,
    duration_ms: float,
    details: dict[str, Any] | None = None,
) -> None:
    options = profiling_options(doc)
    if not options["enabled"]:
        return
    payload = get_document_data(doc, PERFORMANCE_DATA_KEY, {})
    sections = dict(payload.get("sections", {})) if isinstance(payload, dict) else {}
    section_payload = dict(sections.get(section, {}))
    entry = {"duration_ms": round(float(duration_ms), 3)}
    if details:
        entry.update(deepcopy(details))
    section_payload[metric] = entry
    sections[section] = section_payload
    set_document_data(
        doc,
        PERFORMANCE_DATA_KEY,
        {
            "enabled": True,
            "sections": sections,
        },
    )
    if options["log"]:
        details_text = ""
        if details:
            details_text = " " + " ".join(f"{key}={value!r}" for key, value in sorted(details.items()))
        _log_to_console(
            f"Perf[{section}.{metric}] duration_ms={entry['duration_ms']:.3f}{details_text}"
        )


def _log_to_console(message: str) -> None:
    text = f"[OCW] {message}"
    if not text.endswith("\n"):
        text += "\n"
    console = getattr(App, "Console", None) if App is not None else None
    writer = getattr(console, "PrintMessage", None) if console is not None else None
    if callable(writer):
        writer(text)
        return
    print(text, end="")
