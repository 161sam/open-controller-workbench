from __future__ import annotations

from copy import deepcopy
from typing import Any
from weakref import WeakKeyDictionary

_DOC_DATA: WeakKeyDictionary[Any, dict[str, Any]] = WeakKeyDictionary()
_DOC_DATA_FALLBACK: dict[int, dict[str, Any]] = {}
_MISSING = object()


def get_document_data(doc: Any, key: str, default: Any = None) -> Any:
    value = getattr(doc, key, _MISSING)
    if value is not _MISSING:
        return value
    bucket = _get_bucket(doc)
    if key in bucket:
        return deepcopy(bucket[key])
    return default


def set_document_data(doc: Any, key: str, value: Any) -> None:
    try:
        setattr(doc, key, value)
    except Exception:
        pass
    bucket = _ensure_bucket(doc)
    bucket[key] = deepcopy(value)


def has_document_data(doc: Any, key: str) -> bool:
    if getattr(doc, key, _MISSING) is not _MISSING:
        return True
    bucket = _get_bucket(doc)
    return key in bucket


def clear_document_data(doc: Any, key: str) -> None:
    try:
        if hasattr(doc, key):
            delattr(doc, key)
    except Exception:
        pass
    bucket = _get_bucket(doc)
    if key in bucket:
        del bucket[key]


def update_document_data(doc: Any, key: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_document_data(doc, key, {})
    merged = dict(current) if isinstance(current, dict) else {}
    merged.update(deepcopy(updates))
    set_document_data(doc, key, merged)
    return merged


def _get_bucket(doc: Any) -> dict[str, Any]:
    try:
        return _DOC_DATA.get(doc, {})
    except TypeError:
        return _DOC_DATA_FALLBACK.get(id(doc), {})


def _ensure_bucket(doc: Any) -> dict[str, Any]:
    try:
        bucket = _DOC_DATA.get(doc)
        if bucket is None:
            bucket = {}
            _DOC_DATA[doc] = bucket
        return bucket
    except TypeError:
        key = id(doc)
        bucket = _DOC_DATA_FALLBACK.get(key)
        if bucket is None:
            bucket = {}
            _DOC_DATA_FALLBACK[key] = bucket
        return bucket
