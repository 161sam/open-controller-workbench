from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ocf_freecad.freecad_api.metadata import (
    clear_document_data,
    get_document_data,
    set_document_data,
)
from ocf_freecad.freecad_api.model import read_project_state, write_project_state

# Deprecated legacy persistence path. Keep read support for migration only.
STATE_CONTAINER_NAME = "OCF_State"
STATE_CONTAINER_LABEL = "OCF State"
STATE_PROPERTY_NAME = "StateJson"
STATE_GROUP_NAME = "OpenController"

# Runtime cache for environments where document objects are partially mocked.
STATE_CACHE_KEY = "OCFStateCache"
STATE_CACHE_JSON_KEY = "OCFStateCacheJson"

# Deprecated document metadata keys. Read-only for migration.
LEGACY_STATE_KEY = "OCFState"
LEGACY_STATE_JSON_KEY = "OCF_State_JSON"


class ProjectStateStore:
    def __init__(self, doc: Any) -> None:
        self.doc = doc

    def has_state(self) -> bool:
        self.migrate_legacy_state()
        return self._read_primary_state() is not None or self._read_runtime_cache() is not None

    def load(self) -> dict[str, Any] | None:
        self.migrate_legacy_state()
        state = self._read_primary_state()
        if state is not None:
            return state
        return self._read_runtime_cache()

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(state)
        write_project_state(self.doc, normalized)
        set_document_data(self.doc, STATE_CACHE_KEY, normalized)
        self._clear_redundant_paths()
        return deepcopy(normalized)

    def migrate_legacy_state(self) -> dict[str, Any] | None:
        if self._read_primary_state() is not None:
            return None
        legacy_state = self._read_legacy_state()
        if legacy_state is None:
            return None
        self.save(legacy_state)
        return deepcopy(legacy_state)

    def _read_primary_state(self) -> dict[str, Any] | None:
        state = read_project_state(self.doc)
        if isinstance(state, dict):
            return deepcopy(state)
        return None

    def _read_runtime_cache(self) -> dict[str, Any] | None:
        state = get_document_data(self.doc, STATE_CACHE_KEY)
        if isinstance(state, dict):
            return deepcopy(state)
        payload = get_document_data(self.doc, STATE_CACHE_JSON_KEY)
        if isinstance(payload, str) and payload.strip():
            return _load_json(payload)
        return None

    def _read_legacy_state(self) -> dict[str, Any] | None:
        container = get_state_container(self.doc, create=False)
        payload = getattr(container, STATE_PROPERTY_NAME, "") if container is not None else ""
        if isinstance(payload, str) and payload.strip():
            try:
                return _load_json(payload)
            except ValueError:
                return None
        legacy_state = get_document_data(self.doc, LEGACY_STATE_KEY)
        if isinstance(legacy_state, dict):
            return deepcopy(legacy_state)
        payload = get_document_data(self.doc, LEGACY_STATE_JSON_KEY)
        if isinstance(payload, str) and payload.strip():
            try:
                return _load_json(payload)
            except ValueError:
                return None
        return None

    def _clear_redundant_paths(self) -> None:
        clear_document_data(self.doc, STATE_CACHE_JSON_KEY)
        clear_document_data(self.doc, LEGACY_STATE_KEY)
        clear_document_data(self.doc, LEGACY_STATE_JSON_KEY)


def get_project_state_store(doc: Any) -> ProjectStateStore:
    return ProjectStateStore(doc)


def get_state_container(doc: Any, create: bool = True) -> Any | None:
    if not hasattr(doc, "addObject"):
        return None
    existing = _find_state_container(doc)
    if existing is not None or not create:
        return existing
    container = _create_state_container(doc)
    _ensure_state_properties(container)
    _hide_state_container(container)
    return container


def has_persisted_state(doc: Any) -> bool:
    return get_project_state_store(doc).has_state()


def read_state(doc: Any) -> dict[str, Any] | None:
    return get_project_state_store(doc).load()


def write_state(doc: Any, state: dict[str, Any]) -> None:
    get_project_state_store(doc).save(state)


def migrate_legacy_state(doc: Any) -> None:
    get_project_state_store(doc).migrate_legacy_state()


def _find_state_container(doc: Any) -> Any | None:
    if hasattr(doc, "getObject"):
        try:
            obj = doc.getObject(STATE_CONTAINER_NAME)
            if obj is not None:
                return obj
        except Exception:
            pass
    for obj in getattr(doc, "Objects", []):
        if getattr(obj, "Name", None) == STATE_CONTAINER_NAME or getattr(obj, "Label", None) == STATE_CONTAINER_LABEL:
            return obj
    return None


def _create_state_container(doc: Any) -> Any:
    for object_type in ("App::FeaturePython", "App::Feature"):
        try:
            return doc.addObject(object_type, STATE_CONTAINER_NAME)
        except Exception:
            continue
    raise RuntimeError("Failed to create Open Controller state container")


def _ensure_state_properties(container: Any) -> None:
    properties = list(getattr(container, "PropertiesList", []))
    if STATE_PROPERTY_NAME not in properties and hasattr(container, "addProperty"):
        container.addProperty("App::PropertyString", STATE_PROPERTY_NAME, STATE_GROUP_NAME, "Open Controller state JSON")


def _hide_state_container(container: Any) -> None:
    if hasattr(container, "Label"):
        container.Label = STATE_CONTAINER_LABEL
    view = getattr(container, "ViewObject", None)
    if view is not None and hasattr(view, "Visibility"):
        view.Visibility = False
    if hasattr(container, "setEditorMode"):
        for name in ("Label", STATE_PROPERTY_NAME):
            try:
                container.setEditorMode(name, 2)
            except Exception:
                continue


def _load_json(payload: str) -> dict[str, Any]:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Controller state JSON must decode to an object")
    return data
