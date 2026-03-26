from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.services.constraint_service import ConstraintService
from ocw_workbench.services.controller_service import ControllerService


class PreviewValidationService:
    def __init__(
        self,
        controller_service: ControllerService | None = None,
        constraint_service: ConstraintService | None = None,
    ) -> None:
        self.controller_service = controller_service or ControllerService()
        self.constraint_service = constraint_service or ConstraintService()

    def validate_place(
        self,
        doc: Any,
        *,
        template_id: str,
        x: float,
        y: float,
        rotation: float = 0.0,
    ) -> dict[str, Any]:
        library_component = self.controller_service.library_service.get(template_id)
        component = {
            "id": "__preview__",
            "type": str(library_component.get("category") or "component"),
            "library_ref": template_id,
            "x": float(x),
            "y": float(y),
            "rotation": float(rotation),
        }
        components = deepcopy(self.controller_service.get_state(doc)["components"])
        components.append(component)
        return self._validate(doc, components=components, preview_component_id="__preview__")

    def validate_move(
        self,
        doc: Any,
        *,
        component_id: str,
        x: float,
        y: float,
        rotation: float = 0.0,
    ) -> dict[str, Any]:
        state = self.controller_service.get_state(doc)
        components = deepcopy(state["components"])
        for component in components:
            if component["id"] != component_id:
                continue
            component["x"] = float(x)
            component["y"] = float(y)
            component["rotation"] = float(rotation)
            break
        else:
            raise KeyError(f"Unknown component id: {component_id}")
        return self._validate(doc, components=components, preview_component_id=component_id)

    def _validate(self, doc: Any, *, components: list[dict[str, Any]], preview_component_id: str) -> dict[str, Any]:
        controller = deepcopy(self.controller_service.get_state(doc)["controller"])
        validation = self.constraint_service.validate(controller, components)
        findings = self._preview_findings(validation, preview_component_id)
        error_count = sum(1 for finding in findings if finding.get("severity") == "error")
        warning_count = sum(1 for finding in findings if finding.get("severity") == "warning")
        primary = self._primary_status(findings)
        return {
            "valid": error_count == 0,
            "severity": "error" if error_count else ("warning" if warning_count else None),
            "status": primary["message"],
            "status_code": primary["code"],
            "commit_allowed": error_count == 0,
            "findings": findings,
            "summary": {
                "error_count": error_count,
                "warning_count": warning_count,
                "total_count": error_count + warning_count,
            },
        }

    def _preview_findings(self, validation: dict[str, Any], preview_component_id: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for severity in ("errors", "warnings"):
            for finding in validation.get(severity, []):
                if not isinstance(finding, dict):
                    continue
                source = finding.get("source_component")
                affected = finding.get("affected_component")
                if source == preview_component_id or affected == preview_component_id:
                    findings.append(deepcopy(finding))
        return findings

    def _primary_status(self, findings: list[dict[str, Any]]) -> dict[str, str]:
        if not findings:
            return {"code": "valid", "message": "Valid placement"}
        if any(str(finding.get("rule_id") or "").startswith("inside_surface") or str(finding.get("rule_id")) == "edge_distance" for finding in findings):
            return {"code": "out_of_bounds", "message": "Out of bounds"}
        if any(str(finding.get("rule_id")) in {"component_spacing", "cutout_spacing"} for finding in findings):
            return {"code": "overlap_risk", "message": "Overlap risk"}
        if any(str(finding.get("rule_id")) in {"keepout_spacing", "mounting_hole_clearance"} for finding in findings):
            return {"code": "keepout_warning", "message": "Keepout warning"}
        if any(str(finding.get("severity")) == "warning" for finding in findings):
            return {"code": "warning", "message": "Keepout warning"}
        return {"code": "invalid", "message": "Overlap risk"}
