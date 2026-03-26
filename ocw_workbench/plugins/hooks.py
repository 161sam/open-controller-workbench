from __future__ import annotations

from types import ModuleType
from typing import Callable

from ocw_workbench.plugins.context import PluginContext

HOOK_NAMES = [
    "register_components",
    "register_templates",
    "register_variants",
    "register_exporters",
    "register_layout_strategies",
    "register_constraints",
]


def run_module_hooks(module: ModuleType, context: PluginContext) -> None:
    for hook_name in HOOK_NAMES:
        hook = getattr(module, hook_name, None)
        if hook is None:
            continue
        _run_hook(hook, hook_name, context)


def _run_hook(hook: Callable[[PluginContext], None], hook_name: str, context: PluginContext) -> None:
    try:
        hook(context)
    except Exception as exc:
        plugin_id = context.config.get("plugin_id", "<unknown>")
        context.warn(f"Plugin '{plugin_id}' hook '{hook_name}' failed: {exc}")
