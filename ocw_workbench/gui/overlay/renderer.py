from __future__ import annotations

import math
from time import perf_counter
from typing import Any

from ocw_workbench.freecad_api.metadata import set_document_data
from ocw_workbench.freecad_api.performance import record_profile_metric
from ocw_workbench.gui.overlay.object import clear_legacy_overlay_objects, overlay_render_path, update_overlay_object
from ocw_workbench.gui.panels._common import log_to_console
from ocw_workbench.services.overlay_service import OverlayService


class OverlayRenderer:
    OVERLAY_OBJECT_NAME = "OCW_Overlay"
    MIN_GEOMETRY_EPSILON = 1e-6

    def __init__(self, overlay_service: OverlayService | None = None) -> None:
        self.overlay_service = overlay_service or OverlayService()

    def refresh(self, doc: Any) -> dict[str, Any]:
        build_started_at = perf_counter()
        payload = self.overlay_service.build_overlay(doc)
        build_duration_ms = (perf_counter() - build_started_at) * 1000.0
        summary = dict(payload.get("summary", {}))
        summary["build_duration_ms"] = round(build_duration_ms, 3)
        payload["summary"] = summary
        record_profile_metric(
            doc,
            "overlay",
            "build",
            build_duration_ms,
            details={"item_count": len(payload.get("items", [])), "enabled": bool(payload.get("enabled", True))},
        )
        return self.render(doc, payload, build_duration_ms=build_duration_ms)

    def render(
        self,
        doc: Any,
        payload: dict[str, Any],
        recompute: bool = False,
        build_duration_ms: float | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        clear_legacy_overlay_objects(doc)
        stats = {
            "total_items": len(payload.get("items", [])),
            "rendered_items": 0,
            "dropped_items": 0,
            "dropped_reasons": {},
            "render_path": "disabled",
            "duration_ms": 0.0,
            "visual_only": True,
            "build_duration_ms": round(float(build_duration_ms or payload.get("summary", {}).get("build_duration_ms", 0.0)), 3),
        }
        if not payload.get("enabled", True):
            if hasattr(doc, "addObject"):
                update_overlay_object(doc, payload, stats)
            stats["duration_ms"] = (perf_counter() - started_at) * 1000.0
            updated = self._with_render_summary(payload, stats)
            self._store_overlay_state(doc, updated)
            record_profile_metric(
                doc,
                "overlay",
                "render",
                stats["duration_ms"],
                details={"render_path": stats["render_path"], "rendered_items": 0, "dropped_items": 0},
            )
            self._log_render_summary(updated)
            return updated
        if not hasattr(doc, "addObject"):
            stats["render_path"] = "headless"
            stats["duration_ms"] = (perf_counter() - started_at) * 1000.0
            updated = self._with_render_summary(payload, stats)
            self._store_overlay_state(doc, updated)
            record_profile_metric(
                doc,
                "overlay",
                "render",
                stats["duration_ms"],
                details={"render_path": stats["render_path"], "rendered_items": 0, "dropped_items": 0},
            )
            self._log_render_summary(updated)
            return updated
        normalized_items = []
        for item in payload.get("items", []):
            _, drop_reason = self._item_shape(item)
            if drop_reason is None:
                normalized_items.append(item)
                stats["rendered_items"] += 1
                continue
            stats["dropped_items"] += 1
            key = drop_reason or "unknown"
            stats["dropped_reasons"][key] = int(stats["dropped_reasons"].get(key, 0)) + 1
        updated = dict(payload)
        updated["items"] = normalized_items
        overlay_obj = update_overlay_object(doc, updated, stats)
        stats["render_path"] = overlay_render_path(overlay_obj)
        updated = self._with_render_summary(updated, stats)
        if overlay_obj is not None:
            update_overlay_object(doc, updated, stats)
        if recompute:
            log_to_console("Overlay render requested recompute, but overlay updates stay visual-only.", level="warning")
        stats["duration_ms"] = (perf_counter() - started_at) * 1000.0
        updated = self._with_render_summary(updated, stats)
        if overlay_obj is not None:
            update_overlay_object(doc, updated, stats)
        self._store_overlay_state(doc, updated)
        record_profile_metric(
            doc,
            "overlay",
            "render",
            stats["duration_ms"],
            details={
                "render_path": stats["render_path"],
                "rendered_items": stats["rendered_items"],
                "dropped_items": stats["dropped_items"],
            },
        )
        self._log_render_summary(updated)
        return updated

    def _item_shape(self, item: dict[str, Any]) -> tuple[bool, str | None]:
        try:
            geometry = item["geometry"]
            item_type = str(item.get("type", ""))
            if item_type == "text_marker":
                label = str(item.get("label", "") or "")
                if not label:
                    return False, "empty_text"
                return True, None
            if item_type == "rect":
                width = float(geometry["width"])
                height = float(geometry["height"])
                if not self._is_positive(width) or not self._is_positive(height):
                    return False, "degenerate_rect"
                return True, None
            if item_type == "slot":
                width = float(geometry["width"])
                height = float(geometry["height"])
                if not self._is_positive(width) or not self._is_positive(height):
                    return False, "degenerate_slot"
                return True, None
            if item_type == "circle":
                diameter = float(geometry["diameter"])
                if not self._is_positive(diameter):
                    return False, "degenerate_circle"
                return True, None
            if item_type == "line":
                start_x = float(geometry["start_x"])
                start_y = float(geometry["start_y"])
                end_x = float(geometry["end_x"])
                end_y = float(geometry["end_y"])
                if math.hypot(end_x - start_x, end_y - start_y) <= self.MIN_GEOMETRY_EPSILON:
                    return False, "degenerate_line"
                return True, None
            return False, f"unsupported:{item_type or 'unknown'}"
        except Exception:
            return False, "build_error"

    def _is_positive(self, value: float) -> bool:
        return math.isfinite(value) and value > self.MIN_GEOMETRY_EPSILON

    def _with_render_summary(self, payload: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        summary = dict(updated.get("summary", {}))
        summary.update(
            {
                "render_item_count": int(stats["rendered_items"]),
                "dropped_item_count": int(stats["dropped_items"]),
                "render_path": str(stats["render_path"]),
                "build_duration_ms": round(float(stats.get("build_duration_ms", 0.0)), 3),
                "render_duration_ms": round(float(stats.get("duration_ms", 0.0)), 3),
                "visual_only": bool(stats.get("visual_only", True)),
            }
        )
        if stats.get("dropped_reasons"):
            summary["dropped_reasons"] = dict(stats["dropped_reasons"])
        updated["summary"] = summary
        return updated

    def _store_overlay_state(self, doc: Any, payload: dict[str, Any]) -> None:
        summary = payload.get("summary", {})
        set_document_data(doc, "OCWOverlayState", payload)
        set_document_data(
            doc,
            "OCWOverlayRender",
            {
                "render_path": summary.get("render_path"),
                "render_item_count": summary.get("render_item_count", 0),
                "dropped_item_count": summary.get("dropped_item_count", 0),
                "dropped_reasons": dict(summary.get("dropped_reasons", {})),
                "build_duration_ms": summary.get("build_duration_ms", 0.0),
                "render_duration_ms": summary.get("render_duration_ms", 0.0),
            },
        )

    def _log_render_summary(self, payload: dict[str, Any]) -> None:
        summary = payload.get("summary", {})
        log_to_console(
            "Overlay render "
            f"path={summary.get('render_path', 'unknown')} "
            f"items={summary.get('item_count', 0)} "
            f"rendered={summary.get('render_item_count', 0)} "
            f"dropped={summary.get('dropped_item_count', 0)} "
            f"build_ms={summary.get('build_duration_ms', 0.0):.3f} "
            f"duration_ms={summary.get('render_duration_ms', 0.0):.3f}."
        )
