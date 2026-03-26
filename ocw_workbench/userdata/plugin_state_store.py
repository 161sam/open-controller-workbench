from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocw_workbench.userdata.persistence import _default_base_dir

DEFAULT_PLUGIN_STATE_FILENAME = "plugin_states.json"


@dataclass(frozen=True)
class PluginStateEntry:
    plugin_id: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
        }


@dataclass
class PluginStateStore:
    states: list[PluginStateEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"states": [entry.to_dict() for entry in self.states]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PluginStateStore":
        data = payload if isinstance(payload, dict) else {}
        raw_states = data.get("states", [])
        if not isinstance(raw_states, list):
            return cls()
        items: list[PluginStateEntry] = []
        for value in raw_states:
            if not isinstance(value, dict):
                continue
            plugin_id = value.get("plugin_id")
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            items.append(PluginStateEntry(plugin_id=plugin_id, enabled=bool(value.get("enabled", True))))
        return cls(states=items)


class PluginStatePersistence:
    def __init__(self, base_dir: str | None = None, filename: str = DEFAULT_PLUGIN_STATE_FILENAME) -> None:
        self.base_dir = Path(base_dir or _default_base_dir())
        self.filename = filename

    @property
    def path(self) -> Path:
        return self.base_dir / self.filename

    def load(self) -> PluginStateStore:
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return PluginStateStore()
        except OSError:
            return PluginStateStore()
        if not content.strip():
            return PluginStateStore()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return PluginStateStore()
        return PluginStateStore.from_dict(data)

    def save(self, store: PluginStateStore) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store.to_dict(), indent=2, sort_keys=True)
        self.path.write_text(payload + "\n", encoding="utf-8")

    def is_enabled(self, plugin_id: str, default: bool = True) -> bool:
        store = self.load()
        for entry in store.states:
            if entry.plugin_id == plugin_id:
                return entry.enabled
        return default
