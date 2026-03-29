from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from ocw_workbench.freecad_api import gui as freecad_gui
from ocw_workbench.freecad_api.metadata import get_document_data, set_document_data, update_document_data
from ocw_workbench.freecad_api.model import (
    COMPONENTS_GROUP_NAME,
    CONTROLLER_OBJECT_NAME,
    GENERATED_GROUP_NAME,
    clear_generated_group,
    get_component_group,
    get_components_group,
    get_controller_object,
    get_generated_group,
    get_mounting_group,
    group_generated_object,
    iter_generated_objects,
)
from ocw_workbench.freecad_api.performance import record_profile_metric
from ocw_workbench.freecad_api.state import read_state
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
        if mode == SyncMode.STATE_ONLY:
            self._perform_state_only_update(doc, selection=selection)
            return
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

    def _perform_state_only_update(
        self,
        doc: Any,
        selection: str | None,
    ) -> None:
        started_at = perf_counter()
        self._refresh_component_document_metadata(doc)
        self._set_last_sync(
            doc,
            {
                "requested_sync_mode": SyncMode.STATE_ONLY,
                "selection": selection,
                "sync_mode": SyncMode.STATE_ONLY,
            },
        )
        duration_ms = round((perf_counter() - started_at) * 1000.0, 3)
        self._set_last_sync(doc, {"sync_duration_ms": duration_ms})
        record_profile_metric(doc, "sync", "state_only_refresh", duration_ms, details={"mode": SyncMode.STATE_ONLY})

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
        self._style_document_object(body, role="body")
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
        self._style_document_object(top_cut, role="top_plate")
        group_generated_object(doc, top_cut)
        pcb = self._materialize_pcb_object(doc, builder, controller)
        mounting_feature_count = self._materialize_mounting_supports(doc, builder, controller)
        component_object_count = self._materialize_component_objects(doc, builder, controller, state["components"])
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
                "pcb_object": getattr(pcb, "Name", None) if pcb is not None else None,
                "mounting_feature_count": mounting_feature_count,
                "component_object_count": component_object_count,
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
                "mounting_feature_count": mounting_feature_count,
                "component_object_count": component_object_count,
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

    def _refresh_component_document_metadata(self, doc: Any) -> None:
        state = read_state(doc)
        if not isinstance(state, dict):
            return
        components = state.get("components")
        if not isinstance(components, list):
            return
        component_by_id = {
            str(component.get("id")): component
            for component in components
            if isinstance(component, dict) and component.get("id") is not None
        }
        if not component_by_id:
            return
        for obj in iter_generated_objects(doc):
            component_id = getattr(obj, "OCWComponentId", None)
            if not isinstance(component_id, str):
                continue
            component_data = component_by_id.get(component_id)
            if component_data is None:
                continue
            self._set_component_label(obj, component_data)

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

    def _materialize_component_objects(
        self,
        doc: Any,
        builder: Any,
        controller: Any,
        components: list[Any],
    ) -> int:
        if not components or not hasattr(builder, "build_component_feature"):
            return 0
        components_group = get_components_group(doc, create=True)
        component_groups: dict[str, Any] = {}
        count = 0
        for component in components:
            target_group = self._resolve_component_tree_group(doc, components_group, component, component_groups)
            feature = builder.build_component_feature(controller, component)
            self._set_component_metadata(feature, component)
            self._set_component_label(feature, component)
            self._style_document_object(feature, role="component", component=component)
            self._group_component_object(target_group, feature)
            count += 1
        return count

    def _materialize_pcb_object(self, doc: Any, builder: Any, controller: Any) -> Any | None:
        if not hasattr(builder, "build_pcb"):
            return None
        pcb = builder.build_pcb(controller)
        self._set_generated_label(pcb, "OCW_PCB")
        self._style_document_object(pcb, role="pcb")
        group_generated_object(doc, pcb)
        return pcb

    def _materialize_mounting_supports(self, doc: Any, builder: Any, controller: Any) -> int:
        if not hasattr(builder, "build_mounting_support_features"):
            return 0
        supports = list(builder.build_mounting_support_features(controller))
        if not supports:
            return 0
        mounting_group = get_mounting_group(doc, create=True)
        for support in supports:
            role = "fastener" if str(getattr(support, "Name", "")).startswith("OCW_Screw_") else "mounting"
            self._style_document_object(support, role=role)
            self._group_component_object(mounting_group, support)
        return len(supports)

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
            view = getattr(obj, "ViewObject", None)
            if view is None:
                continue
            component_id = getattr(obj, "OCWComponentId", None)
            is_selected = isinstance(component_id, str) and selected_component_id is not None and component_id == selected_component_id
            if hasattr(view, "ShapeColor"):
                if is_selected:
                    view.ShapeColor = (0.9, 0.3, 0.2)
                elif component_id:
                    view.ShapeColor = (0.48, 0.62, 0.82)
                else:
                    view.ShapeColor = (0.7, 0.7, 0.7)
            if hasattr(view, "LineColor"):
                if is_selected:
                    view.LineColor = (0.9, 0.3, 0.2)
                elif component_id:
                    view.LineColor = (0.18, 0.28, 0.42)
                else:
                    view.LineColor = (0.2, 0.2, 0.2)

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

    def _group_component_object(self, components_group: Any | None, obj: Any) -> None:
        if components_group is None or obj is None:
            return
        if hasattr(components_group, "addObject"):
            try:
                components_group.addObject(obj)
                return
            except Exception:
                pass
        group_list = list(getattr(components_group, "Group", []))
        if obj not in group_list:
            group_list.append(obj)
            try:
                components_group.Group = group_list
            except Exception:
                pass

    def _resolve_component_tree_group(
        self,
        doc: Any,
        components_group: Any | None,
        component_data: dict[str, Any],
        group_cache: dict[str, Any],
    ) -> Any | None:
        group_id = component_data.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            return components_group
        normalized_group_id = group_id.strip()
        if normalized_group_id in group_cache:
            return group_cache[normalized_group_id]
        group_role = component_data.get("group_role")
        role = str(group_role).strip() if isinstance(group_role, str) and group_role.strip() else None
        group = get_component_group(doc, normalized_group_id, create=True, role=role)
        if group is None:
            return components_group
        group_cache[normalized_group_id] = group
        return group

    def _set_component_metadata(self, obj: Any, component_data: dict[str, Any]) -> None:
        self._ensure_string_property(obj, "OCWComponentId", "OCW", "Open Controller component id")
        self._ensure_string_property(obj, "OCWComponentType", "OCW", "Open Controller component type")
        self._ensure_string_property(obj, "OCWLibraryRef", "OCW", "Open Controller component library reference")
        self._ensure_string_property(obj, "OCWGroupId", "OCW", "Open Controller component group id")
        self._ensure_string_property(obj, "OCWGroupRole", "OCW", "Open Controller component group role")
        self._ensure_float_property(obj, "OCWX", "OCW", "Open Controller component X")
        self._ensure_float_property(obj, "OCWY", "OCW", "Open Controller component Y")
        self._ensure_float_property(obj, "OCWRotation", "OCW", "Open Controller component rotation")
        setattr(obj, "OCWComponentId", str(component_data.get("id") or ""))
        setattr(obj, "OCWComponentType", str(component_data.get("type") or "component"))
        setattr(obj, "OCWLibraryRef", str(component_data.get("library_ref") or ""))
        setattr(obj, "OCWGroupId", str(component_data.get("group_id") or ""))
        setattr(obj, "OCWGroupRole", str(component_data.get("group_role") or ""))
        setattr(obj, "OCWX", float(component_data.get("x", 0.0) or 0.0))
        setattr(obj, "OCWY", float(component_data.get("y", 0.0) or 0.0))
        setattr(obj, "OCWRotation", float(component_data.get("rotation", 0.0) or 0.0))

    def _set_component_label(self, obj: Any, component_data: dict[str, Any]) -> None:
        component_id = str(component_data.get("id") or getattr(obj, "Name", "component"))
        component_type = str(component_data.get("type") or "component")
        component_label = component_data.get("label")
        if isinstance(component_label, str) and component_label.strip():
            self._set_generated_label(obj, f"{component_label.strip()} [{component_type}]")
            return
        self._set_generated_label(obj, f"{component_id} [{component_type}]")

    def _style_document_object(self, obj: Any, role: str, component: dict[str, Any] | None = None) -> None:
        view = getattr(obj, "ViewObject", None)
        if view is None:
            return
        if hasattr(view, "Visibility"):
            view.Visibility = True
        if role == "body":
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.72, 0.72, 0.76)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.24, 0.24, 0.28)
            return
        if role == "top_plate":
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.88, 0.88, 0.9)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.25, 0.25, 0.28)
            return
        if role == "pcb":
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.18, 0.48, 0.22)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.08, 0.22, 0.1)
            return
        if role == "mounting":
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.78, 0.7, 0.52)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.38, 0.3, 0.14)
            return
        if role == "fastener":
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = (0.72, 0.74, 0.78)
            if hasattr(view, "LineColor"):
                view.LineColor = (0.28, 0.3, 0.36)
            return
        if role == "component":
            component_type = str((component or {}).get("type") or "component")
            palette = {
                "button": ((0.32, 0.52, 0.8), (0.14, 0.24, 0.42)),
                "encoder": ((0.28, 0.62, 0.54), (0.12, 0.32, 0.28)),
                "fader": ((0.76, 0.56, 0.28), (0.4, 0.28, 0.12)),
                "pad": ((0.62, 0.34, 0.76), (0.3, 0.16, 0.4)),
                "display": ((0.18, 0.58, 0.74), (0.08, 0.26, 0.36)),
                "rgb_button": ((0.78, 0.36, 0.36), (0.42, 0.14, 0.14)),
            }
            shape_color, line_color = palette.get(component_type, ((0.48, 0.62, 0.82), (0.18, 0.28, 0.42)))
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = shape_color
            if hasattr(view, "LineColor"):
                view.LineColor = line_color

    def _ensure_string_property(self, obj: Any, name: str, group: str, description: str) -> None:
        properties = list(getattr(obj, "PropertiesList", []))
        if name not in properties and hasattr(obj, "addProperty"):
            obj.addProperty("App::PropertyString", name, group, description)

    def _ensure_float_property(self, obj: Any, name: str, group: str, description: str) -> None:
        properties = list(getattr(obj, "PropertiesList", []))
        if name not in properties and hasattr(obj, "addProperty"):
            obj.addProperty("App::PropertyFloat", name, group, description)
