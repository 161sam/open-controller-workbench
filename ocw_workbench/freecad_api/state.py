from __future__ import annotations

import json
from copy import deepcopy
from time import perf_counter
from typing import Any

from ocw_workbench.freecad_api.metadata import (
    clear_document_data,
    get_document_data,
    set_document_data,
)
from ocw_workbench.freecad_api.model import read_project_state, write_project_state
from ocw_workbench.freecad_api.performance import record_profile_metric

# Deprecated legacy persistence path. Keep read support for migration only.
STATE_CONTAINER_NAME = "OCW_State"
STATE_CONTAINER_LABEL = "OCW State"
LEGACY_STATE_CONTAINER_NAMES = ("OCF_State",)
LEGACY_STATE_CONTAINER_LABELS = ("OCF State",)
STATE_PROPERTY_NAME = "StateJson"
STATE_GROUP_NAME = "OpenController"

# Runtime cache for environments where document objects are partially mocked.
STATE_CACHE_KEY = "OCWStateCache"
STATE_CACHE_JSON_KEY = "OCWStateCacheJson"

# Deprecated document metadata keys. Read-only for migration.
LEGACY_STATE_KEY = "OCFState"
LEGACY_STATE_JSON_KEY = "OCF_State_JSON"
LEGACY_STATE_CACHE_KEYS = ("OCFStateCache",)
LEGACY_STATE_CACHE_JSON_KEYS = ("OCFStateCacheJson",)
STATE_METRICS_KEY = "OCWStateMetrics"


class ProjectStateStore:
    def __init__(self, doc: Any) -> None:
        self.doc = doc

    def has_state(self) -> bool:
        self.migrate_legacy_state()
        return self._read_primary_state() is not None or self._read_runtime_cache() is not None

    def load(self) -> dict[str, Any] | None:
        started_at = perf_counter()
        self.migrate_legacy_state()
        state = self._read_primary_state()
        source = "primary"
        if state is not None:
            self._store_metrics("load", started_at, source=source, controller_id=self._controller_id(state))
            return state
        state = self._read_runtime_cache()
        source = "runtime_cache" if state is not None else "missing"
        self._store_metrics("load", started_at, source=source, controller_id=self._controller_id(state))
        return state

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        normalized = deepcopy(state)
        write_project_state(self.doc, normalized)
        set_document_data(self.doc, STATE_CACHE_KEY, normalized)
        self._clear_redundant_paths()
        self._store_metrics(
            "save",
            started_at,
            source="controller",
            controller_id=self._controller_id(normalized),
            payload_bytes=len(json.dumps(normalized, sort_keys=True)),
        )
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
        for legacy_key in LEGACY_STATE_CACHE_KEYS:
            state = get_document_data(self.doc, legacy_key)
            if isinstance(state, dict):
                return deepcopy(state)
        payload = get_document_data(self.doc, STATE_CACHE_JSON_KEY)
        if isinstance(payload, str) and payload.strip():
            return _load_json(payload)
        for legacy_key in LEGACY_STATE_CACHE_JSON_KEYS:
            payload = get_document_data(self.doc, legacy_key)
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

    def _store_metrics(self, operation: str, started_at: float, **details: Any) -> None:
        duration_ms = round((perf_counter() - started_at) * 1000.0, 3)
        metrics = get_document_data(self.doc, STATE_METRICS_KEY, {})
        if not isinstance(metrics, dict):
            metrics = {}
        metrics[operation] = {"duration_ms": duration_ms, **details}
        set_document_data(self.doc, STATE_METRICS_KEY, metrics)
        record_profile_metric(self.doc, "state", operation, duration_ms, details=details)

    def _controller_id(self, state: dict[str, Any] | None) -> str | None:
        if not isinstance(state, dict):
            return None
        controller = state.get("controller")
        if not isinstance(controller, dict):
            return None
        controller_id = controller.get("id")
        return None if controller_id in {None, ""} else str(controller_id)


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
        for name in (STATE_CONTAINER_NAME, *LEGACY_STATE_CONTAINER_NAMES):
            try:
                obj = doc.getObject(name)
                if obj is not None:
                    return obj
            except Exception:
                continue
    for obj in getattr(doc, "Objects", []):
        if getattr(obj, "Name", None) in (STATE_CONTAINER_NAME, *LEGACY_STATE_CONTAINER_NAMES):
            return obj
        if getattr(obj, "Label", None) in (STATE_CONTAINER_LABEL, *LEGACY_STATE_CONTAINER_LABELS):
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
