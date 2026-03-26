from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

import yaml

from ocw_workbench.templates.loader import TemplateLoader
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.userdata.persistence import UserDataPersistence
from ocw_workbench.utils.yaml_io import dump_yaml, load_yaml

_TEMPLATE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class TemplateEditorService:
    def __init__(
        self,
        loader: TemplateLoader | None = None,
        registry: TemplateRegistry | None = None,
        userdata: UserDataPersistence | None = None,
    ) -> None:
        self.loader = loader or TemplateLoader()
        self.registry = registry or TemplateRegistry()
        self.userdata = userdata or UserDataPersistence()

    def load_template(self, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        payload = load_yaml(file_path)
        self.loader.load_payload(payload, source=file_path)
        normalized = self._normalize_payload(payload)
        normalized["_editor"] = {
            "source_path": str(file_path),
            "status": self._template_status(normalized),
            "is_user_template": self._is_user_template_path(file_path),
        }
        return normalized

    def validate_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self.normalize_payload(payload)
        errors: list[str] = []
        warnings: list[str] = []

        template_meta = normalized["template"]
        controller = normalized["controller"]
        metadata = normalized["metadata"]
        source = metadata.get("source", {}) if isinstance(metadata.get("source"), dict) else {}
        origin = source.get("origin", {}) if isinstance(source.get("origin"), dict) else {}

        template_id = str(template_meta.get("id") or "").strip()
        name = str(template_meta.get("name") or "").strip()
        if not template_id:
            errors.append("Template id is required.")
        elif not _TEMPLATE_ID_PATTERN.match(template_id):
            errors.append("Template id must use lowercase letters, numbers, and underscores only.")
        if not name:
            errors.append("Template name is required.")

        for field in ("width", "depth", "height"):
            value = controller.get(field)
            if not isinstance(value, (int, float)) or float(value) <= 0.0:
                errors.append(f"Controller {field} must be a positive number.")

        rotation = source.get("rotation_deg", 0.0)
        if not isinstance(rotation, (int, float)):
            errors.append("Source rotation must be numeric.")
        elif float(rotation) % 90.0 != 0.0:
            warnings.append("Rotation is not aligned to a 90-degree step.")

        for field in ("offset_x", "offset_y"):
            if field in origin and not isinstance(origin.get(field), (int, float)):
                errors.append(f"Origin {field} must be numeric.")

        zones = normalized["zones"]
        if not isinstance(zones, list):
            errors.append("Zones must be a list.")
        else:
            for index, zone in enumerate(zones):
                if not isinstance(zone, dict):
                    errors.append(f"Zone #{index + 1} must be a mapping.")
                    continue
                zone_id = str(zone.get("id") or "").strip()
                if not zone_id:
                    errors.append(f"Zone #{index + 1} is missing an id.")
                for field in ("x", "y", "width", "height"):
                    value = zone.get(field)
                    if not isinstance(value, (int, float)):
                        errors.append(f"Zone '{zone_id or index + 1}' field '{field}' must be numeric.")
                        continue
                    if field in {"width", "height"} and float(value) <= 0.0:
                        errors.append(f"Zone '{zone_id or index + 1}' field '{field}' must be positive.")

        mounting_holes = controller.get("mounting_holes", [])
        if not isinstance(mounting_holes, list):
            errors.append("Mounting holes must be a list.")
        else:
            for index, hole in enumerate(mounting_holes):
                if not isinstance(hole, dict):
                    errors.append(f"Mounting hole #{index + 1} must be a mapping.")
                    continue
                if not str(hole.get("id") or "").strip():
                    errors.append(f"Mounting hole #{index + 1} is missing an id.")
                for field in ("x", "y", "diameter"):
                    value = hole.get(field)
                    if not isinstance(value, (int, float)):
                        errors.append(f"Mounting hole '{hole.get('id', index + 1)}' field '{field}' must be numeric.")
                        continue
                    if field == "diameter" and float(value) <= 0.0:
                        errors.append(f"Mounting hole '{hole.get('id', index + 1)}' diameter must be positive.")

        try:
            self.loader.load_payload(normalized, source=Path(template_id or "template.yaml"))
        except Exception as exc:
            errors.append(str(exc))

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "payload": normalized,
            "status": "validated" if not errors else "invalid",
        }

    def save_user_template(
        self,
        payload: dict[str, Any],
        *,
        overwrite: bool = False,
    ) -> Path:
        validation = self.validate_template(payload)
        if not validation["valid"]:
            raise ValueError(validation["errors"][0])
        normalized = validation["payload"]
        template_id = normalized["template"]["id"]
        output_path = self.userdata.templates_dir / f"{template_id}.yaml"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"User template '{template_id}' already exists. Enable overwrite to replace it.")
        normalized["metadata"].setdefault("editor", {})
        normalized["metadata"]["editor"]["validated"] = True
        normalized["metadata"]["editor"]["status"] = "edited"
        dump_yaml(output_path, normalized)
        self.registry.load_all()
        return output_path

    def parse_yaml_list(self, content: str, field_name: str) -> list[dict[str, Any]]:
        text = str(content or "").strip()
        if not text:
            return []
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"{field_name} must contain valid YAML: {exc}") from exc
        if parsed is None:
            return []
        if not isinstance(parsed, list):
            raise ValueError(f"{field_name} must be a YAML list.")
        return parsed

    def dump_yaml_block(self, value: list[dict[str, Any]]) -> str:
        if not value:
            return "[]\n"
        return yaml.safe_dump(value, sort_keys=False, allow_unicode=True, default_flow_style=False)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(payload)
        normalized.setdefault("template", {})
        normalized.setdefault("controller", {})
        normalized.setdefault("zones", [])
        normalized.setdefault("components", [])
        normalized.setdefault("layout", {})
        normalized.setdefault("constraints", {})
        normalized.setdefault("defaults", {})
        normalized.setdefault("firmware", {})
        normalized.setdefault("ocf", {})
        normalized.setdefault("metadata", {})
        normalized["controller"].setdefault("mounting_holes", [])
        normalized["controller"].setdefault("reserved_zones", [])
        normalized["controller"].setdefault("layout_zones", [])
        normalized["metadata"].setdefault("source", {})
        normalized["template"].setdefault("description", f"Imported template '{normalized['template'].get('name') or normalized['template'].get('id') or 'template'}'")
        if normalized["template"].get("category") is None:
            normalized["template"]["category"] = "imported"
        if normalized["template"].get("tags") is None:
            normalized["template"]["tags"] = ["fcstd", "user"]
        if normalized["template"].get("version") is None:
            normalized["template"]["version"] = "user"
        template_id = str(normalized["template"].get("id") or "").strip()
        if template_id:
            normalized["controller"]["id"] = template_id
        return normalized

    def normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_payload(payload)

    def _is_user_template_path(self, path: Path) -> bool:
        try:
            return self.userdata.templates_dir.resolve() in path.resolve().parents
        except Exception:
            return False

    def _template_status(self, payload: dict[str, Any]) -> str:
        editor = payload.get("metadata", {}).get("editor", {})
        if isinstance(editor, dict) and editor.get("validated"):
            return "Edited / validated template"
        return "Imported raw template"
