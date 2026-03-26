from __future__ import annotations

CORE_PLUGIN_API_VERSION = "1.0"
PLUGIN_API_VERSION = CORE_PLUGIN_API_VERSION


def is_api_compatible(
    plugin_api_version: str,
    core_api_version: str = CORE_PLUGIN_API_VERSION,
) -> bool:
    plugin_major = str(plugin_api_version).split(".", 1)[0]
    core_major = str(core_api_version).split(".", 1)[0]
    return plugin_major == core_major
