from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ocw_workbench.userdata.store import UserDataStore

DEFAULT_USERDATA_DIRNAME = ".ocw_userdata"
DEFAULT_FILENAME = "userdata.json"


class UserDataPersistence:
    def __init__(self, base_dir: str | None = None, filename: str = DEFAULT_FILENAME) -> None:
        self.base_dir = Path(base_dir or _default_base_dir())
        self.filename = filename

    @property
    def path(self) -> Path:
        return self.base_dir / self.filename

    def load(self) -> UserDataStore:
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return UserDataStore()
        except OSError:
            return UserDataStore()
        if not content.strip():
            return UserDataStore()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return UserDataStore()
        return UserDataStore.from_dict(data)

    def save(self, store: UserDataStore) -> None:
        payload = json.dumps(store.to_dict(), indent=2, sort_keys=True)
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.path.write_text(payload + "\n", encoding="utf-8")
            return
        except OSError:
            for fallback in (_home_state_dir(), _runtime_temp_dir()):
                try:
                    fallback.mkdir(parents=True, exist_ok=True)
                    self.base_dir = fallback
                    self.path.write_text(payload + "\n", encoding="utf-8")
                    return
                except OSError:
                    continue
            raise


def _default_base_dir() -> str:
    configured = os.environ.get("OCW_USERDATA_DIR") or os.environ.get("OCF_USERDATA_DIR")
    if configured:
        return configured
    freecad_dir = _freecad_userdata_dir()
    if freecad_dir is not None:
        return str(freecad_dir)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return str(Path(xdg) / "open-controller-workbench")
    return str(_home_state_dir())


def _freecad_userdata_dir() -> Path | None:
    try:
        import FreeCAD as App
    except ImportError:
        return None
    config_get = getattr(App, "ConfigGet", None)
    if not callable(config_get):
        return None
    for key in ("UserAppData", "AppData"):
        try:
            value = config_get(key)
        except Exception:
            continue
        if isinstance(value, str) and value.strip():
            base_path = Path(value.strip())
            current_path = base_path / "OpenControllerWorkbench"
            legacy_path = base_path / "OpenControllerFreeCAD"
            if current_path.exists() or not legacy_path.exists():
                return current_path
            return legacy_path
    return None


def _home_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "open-controller-workbench"


def _runtime_temp_dir() -> Path:
    return Path(tempfile.gettempdir()) / "open-controller-workbench"
