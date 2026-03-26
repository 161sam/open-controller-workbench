from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from ocw_workbench.freecad_api import gui as freecad_gui
from ocw_workbench.freecad_api.metadata import get_document_data, set_document_data, update_document_data
from ocw_workbench.freecad_api.model import (
    CONTROLLER_OBJECT_NAME,
    GENERATED_GROUP_NAME,
    clear_generated_group,
    get_controller_object,
    get_generated_group,
    group_generated_object,
    iter_generated_objects,
)
from ocw_workbench.freecad_api.performance import record_profile_metric
from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.services._logging import log_to_console


class SyncMode:
    FULL = "full"
    VISUAL_ONLY = "visual_only"
    PARTIAL_READY = "partial_ready"
    STATE_ONLY = "state_only"


class DocumentSyncService:
    def __init__(
        self,
        builder_factory: Callable[..., Any] | None = None,
        gui_module: Any | None = None,
    ) -> None:
        self.builder_factory = builder_factory or ControllerBuilder
        self.gui_module = gui_module or freecad_gui

    def sync_document(self, doc: Any, state: dict[str, Any]) -> None:
        self.update_document(doc, mode=SyncMode.FULL, state=state)

    def update_document(
        self,
        doc: Any,
        mode: str,
        state: dict[str, Any] | None = None,
        selection: str | None = None,
        recompute: bool = False,
    ) -> None:
        if mode == SyncMode.VISUAL_ONLY:
            self._perform_visual_refresh(doc, selection=selection, recompute=recompute)
            return
        if mode == SyncMode.PARTIAL_READY:
            if state is None:
                raise ValueError("partial_ready update requires project state")
            log_to_console("Partial-ready sync requested; falling back to full rebuild.")
            self._perform_full_sync(doc, state, requested_mode=SyncMode.PARTIAL_READY)
            return
        if mode == SyncMode.FULL:
            if state is None:
                raise ValueError("full sync requires project state")
            self._perform_full_sync(doc, state, requested_mode=SyncMode.FULL)
            return
        raise ValueError(f"Unsupported sync mode '{mode}'")

    def _perform_full_sync(self, doc: Any, state: dict[str, Any], requested_mode: str) -> None:
        started_at = perf_counter()
        phase_timings: dict[str, float] = {}
        controller_object = get_controller_object(doc, create=hasattr(doc, "addObject"))
        generated_group = get_generated_group(doc, create=hasattr(doc, "addObject"))
        self._set_last_sync(
            doc,
            {
                "requested_sync_mode": requested_mode,
                "controller_id": state["controller"]["id"],
                "component_count": len(state["components"]),
                "template_id": state["meta"].get("template_id"),
                "variant_id": state["meta"].get("variant_id"),
                "selection": state["meta"].get("selection"),
                "controller_object": getattr(controller_object, "Name", CONTROLLER_OBJECT_NAME) if controller_object is not None else None,
                "generated_group": getattr(generated_group, "Name", GENERATED_GROUP_NAME) if generated_group is not None else None,
            },
        )
        log_to_console(
            f"Syncing document '{getattr(doc, 'Name', '<unnamed>')}' "
            f"for controller '{state['controller']['id']}' with {len(state['components'])} components."
        )
        if not hasattr(doc, "addObject"):
            recompute_started_at = perf_counter()
            if hasattr(doc, "recompute"):
                doc.recompute()
            recompute_ms = round((perf_counter() - recompute_started_at) * 1000.0, 3)
            phase_timings["document_recompute_ms"] = recompute_ms
            self._set_last_sync(
                doc,
                {
                    "sync_duration_ms": round((perf_counter() - started_at) * 1000.0, 3),
                    **phase_timings,
                    "sync_mode": SyncMode.STATE_ONLY,
                },
            )
            for metric, duration_ms in phase_timings.items():
                record_profile_metric(doc, "sync", metric, duration_ms, details={"mode": SyncMode.STATE_ONLY})
            log_to_console(
                f"Document '{getattr(doc, 'Name', '<unnamed>')}' has no FreeCAD object API; state-only sync complete.",
                level="warning",
            )
            return

        self._clear_generated_objects(doc)
        controller = self._build_controller(state["controller"])
        components = [self._build_component(item) for item in state["components"]]
        builder = self.builder_factory(doc=doc)
        body_started_at = perf_counter()
        body = builder.build_body(controller)
        phase_timings["builder_body_generation_ms"] = round((perf_counter() - body_started_at) * 1000.0, 3)
        self._set_generated_label(body, "OCW_ControllerBody")
        group_generated_object(doc, body)
        top_started_at = perf_counter()
        top = builder.build_top_plate(controller)
        phase_timings["builder_top_plate_generation_ms"] = round((perf_counter() - top_started_at) * 1000.0, 3)
        cutout_tool_count = 0
        cutout_diagnostic_count = 0
        if hasattr(builder, "plan_cutout_boolean") and hasattr(builder, "apply_cutout_plan"):
            cutout_plan_started_at = perf_counter()
            cutout_plan = builder.plan_cutout_boolean(top, components)
            phase_timings["cutout_generation_ms"] = round((perf_counter() - cutout_plan_started_at) * 1000.0, 3)
            boolean_started_at = perf_counter()
            top_cut = builder.apply_cutout_plan(top, cutout_plan)
            phase_timings["boolean_phase_ms"] = round((perf_counter() - boolean_started_at) * 1000.0, 3)
            cutout_tool_count = len(getattr(cutout_plan, "tools", []))
            cutout_diagnostic_count = len(getattr(cutout_plan, "diagnostics", []))
        else:
            phase_timings["cutout_generation_ms"] = 0.0
            boolean_started_at = perf_counter()
            top_cut = builder.apply_cutouts(top, components)
            phase_timings["boolean_phase_ms"] = round((perf_counter() - boolean_started_at) * 1000.0, 3)
        self._set_generated_label(top_cut, "OCW_TopPlateCut" if state["components"] else "OCW_TopPlate")
        group_generated_object(doc, top_cut)
        self._materialize_debug_keepout_markers(doc, builder, components, float(state["controller"]["height"]))
        self._apply_selection_highlight(doc, state["meta"].get("selection"))
        recompute_started_at = perf_counter()
        if hasattr(doc, "recompute"):
            doc.recompute()
        phase_timings["document_recompute_ms"] = round((perf_counter() - recompute_started_at) * 1000.0, 3)
        generated_count = self._generated_object_count(doc)
        duration_ms = round((perf_counter() - started_at) * 1000.0, 3)
        self._set_last_sync(
            doc,
            {
                "generated_object_count": generated_count,
                "cutout_tool_count": cutout_tool_count,
                "cutout_diagnostic_count": cutout_diagnostic_count,
                **phase_timings,
                "sync_duration_ms": duration_ms,
                "sync_mode": SyncMode.FULL,
            },
        )
        record_profile_metric(
            doc,
            "sync",
            "full_sync",
            duration_ms,
            details={
                "mode": requested_mode,
                "actual_mode": SyncMode.FULL,
                "generated_object_count": generated_count,
                "cutout_tool_count": cutout_tool_count,
                "cutout_diagnostic_count": cutout_diagnostic_count,
            },
        )
        for metric, metric_duration_ms in phase_timings.items():
            record_profile_metric(
                doc,
                "sync",
                metric,
                metric_duration_ms,
                details={"mode": requested_mode, "actual_mode": SyncMode.FULL},
            )
        revealed = self.gui_module.reveal_generated_objects(doc)
        self.gui_module.activate_document(doc)
        self.gui_module.focus_view(doc, fit=True)
        log_to_console(
            f"Document sync complete for '{getattr(doc, 'Name', '<unnamed>')}': "
            f"{generated_count} generated objects, {revealed} visible in the 3D view, {duration_ms:.3f} ms."
        )

    def refresh_document_visuals(
        self,
        doc: Any,
        selection: str | None,
        recompute: bool = False,
    ) -> None:
        self.update_document(
            doc,
            mode=SyncMode.VISUAL_ONLY,
            selection=selection,
            recompute=recompute,
        )

    def _perform_visual_refresh(
        self,
        doc: Any,
        selection: str | None,
        recompute: bool = False,
    ) -> None:
        started_at = perf_counter()
        self._set_last_sync(
            doc,
            {
                "requested_sync_mode": SyncMode.VISUAL_ONLY,
                "selection": selection,
                "sync_mode": SyncMode.VISUAL_ONLY,
            },
        )
        if not hasattr(doc, "addObject"):
            return
        self._apply_selection_highlight(doc, selection)
        if recompute and hasattr(doc, "recompute"):
            recompute_started_at = perf_counter()
            doc.recompute()
            recompute_ms = round((perf_counter() - recompute_started_at) * 1000.0, 3)
            self._set_last_sync(doc, {"document_recompute_ms": recompute_ms})
            record_profile_metric(doc, "sync", "visual_recompute", recompute_ms, details={"mode": SyncMode.VISUAL_ONLY})
        duration_ms = round((perf_counter() - started_at) * 1000.0, 3)
        self._set_last_sync(doc, {"sync_duration_ms": duration_ms})
        record_profile_metric(doc, "sync", "visual_refresh", duration_ms, details={"mode": SyncMode.VISUAL_ONLY})

    def _materialize_debug_keepout_markers(self, doc: Any, builder: Any, components: list[Any], z_height: float) -> None:
        if not self._should_materialize_component_markers(doc):
            return
        shapes_api = __import__("ocw_workbench.freecad_api.shapes", fromlist=["create_cylinder"])
        for keepout in builder.build_keepouts(components):
            name = f"OCW_{keepout['component_id']}_{keepout['feature']}"
            if keepout["shape"] == "circle":
                marker = shapes_api.create_cylinder(
                    doc,
                    name,
                    radius=float(keepout["diameter"]) / 2.0,
                    height=1.0,
                    x=float(keepout["x"]),
                    y=float(keepout["y"]),
                    z=float(z_height),
                )
                self._set_generated_label(marker, name)
                group_generated_object(doc, marker)
                continue
            if keepout["shape"] in {"rect", "slot"}:
                shape_factory = shapes_api.make_rect_prism_shape if keepout["shape"] == "rect" else shapes_api.make_slot_prism_shape
                marker_shape = shapes_api.translate_shape(
                    shape_factory(
                        width=float(keepout["width"]),
                        depth=float(keepout["height"]),
                        height=1.0,
                    ),
                    x=float(keepout["x"]) - (float(keepout["width"]) / 2.0),
                    y=float(keepout["y"]) - (float(keepout["height"]) / 2.0),
                    z=float(z_height),
                )
                if float(keepout.get("rotation", 0.0) or 0.0) != 0.0:
                    marker_shape = shapes_api.rotate_shape(
                        marker_shape,
                        float(keepout["rotation"]),
                        center=(float(keepout["x"]), float(keepout["y"]), float(z_height)),
                    )
                marker = shapes_api.create_feature(doc, name, marker_shape)
                self._set_generated_label(marker, name)
                group_generated_object(doc, marker)

    def _clear_generated_objects(self, doc: Any) -> None:
        clear_generated_group(doc)

    def _set_generated_label(self, obj: Any, label: str) -> None:
        if hasattr(obj, "Label"):
            obj.Label = label
        else:
            setattr(obj, "Name", label)

    def _should_materialize_component_markers(self, doc: Any) -> bool:
        debug_ui = get_document_data(doc, "OCWDebugUI", {})
        if isinstance(debug_ui, dict):
            return bool(debug_ui.get("materialize_component_markers", False))
        return False

    def _apply_selection_highlight(self, doc: Any, selected_component_id: str | None) -> None:
        for obj in iter_generated_objects(doc):
            label = str(getattr(obj, "Label", getattr(obj, "Name", "")))
            view = getattr(obj, "ViewObject", None)
            if view is None:
                continue
            is_selected = selected_component_id is not None and selected_component_id in label
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.9, 0.3, 0.2) if is_selected else (0.7, 0.7, 0.7)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.9, 0.3, 0.2) if is_selected else (0.2, 0.2, 0.2)

    def _generated_object_count(self, doc: Any) -> int:
        return len(iter_generated_objects(doc))

    def _set_last_sync(self, doc: Any, updates: dict[str, Any]) -> None:
        if get_document_data(doc, "OCWLastSync") is None:
            set_document_data(doc, "OCWLastSync", {})
        update_document_data(doc, "OCWLastSync", updates)

    def _build_controller(self, controller_data: dict[str, Any]) -> Any:
        from ocw_workbench.domain.controller import Controller

        return Controller(**controller_data)

    def _build_component(self, component_data: dict[str, Any]) -> Any:
        from ocw_workbench.domain.component import Component

        return Component(**component_data)
