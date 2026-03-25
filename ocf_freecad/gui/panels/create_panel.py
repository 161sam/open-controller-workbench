from __future__ import annotations

from collections import Counter
from typing import Any

from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.template_service import TemplateService
from ocf_freecad.services.variant_service import VariantService


class CreatePanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        template_service: TemplateService | None = None,
        variant_service: VariantService | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.template_service = template_service or TemplateService()
        self.variant_service = variant_service or VariantService()
        self._templates: list[dict[str, Any]] = []
        self._variants: list[dict[str, Any]] = []
        self.form = _build_form()
        self.refresh_templates()

    def refresh_templates(self) -> None:
        self._templates = self.template_service.list_templates()
        labels = [_template_label(item) for item in self._templates]
        _set_combo_items(self.form["template"], labels)
        self.refresh_variants()
        self.refresh_preview()

    def refresh_variants(self) -> None:
        template_id = self.selected_template_id()
        self._variants = self.variant_service.list_variants(template_id=template_id) if template_id else []
        labels = ["Template Default"] + [_variant_label(item) for item in self._variants]
        _set_combo_items(self.form["variant"], labels)

    def refresh_preview(self) -> str:
        preview = self._build_preview()
        _set_text(self.form["preview"], preview)
        return preview

    def selected_template_id(self) -> str | None:
        label = _current_text(self.form["template"])
        for item in self._templates:
            if _template_label(item) == label:
                return item["template"]["id"]
        return None

    def selected_variant_id(self) -> str | None:
        label = _current_text(self.form["variant"])
        if label in {"", "Template Default"}:
            return None
        for item in self._variants:
            if _variant_label(item) == label:
                return item["variant"]["id"]
        return None

    def create_controller(self) -> dict[str, Any]:
        template_id = self.selected_template_id()
        if not template_id:
            raise ValueError("No template selected")
        variant_id = self.selected_variant_id()
        if variant_id:
            return self.controller_service.create_from_variant(self.doc, variant_id)
        return self.controller_service.create_from_template(self.doc, template_id)

    def accept(self) -> bool:
        self.create_controller()
        return True

    def _build_preview(self) -> str:
        template_id = self.selected_template_id()
        if not template_id:
            return "Select a template to preview components."
        variant_id = self.selected_variant_id()
        if variant_id:
            project = self.variant_service.generate_from_variant(variant_id)
            title = f"Variant: {variant_id}"
        else:
            project = self.template_service.generate_from_template(template_id)
            title = f"Template: {template_id}"
        counts = Counter(component["type"] for component in project["components"])
        summary = ", ".join(f"{component_type} x{count}" for component_type, count in sorted(counts.items()))
        return "\n".join(
            [
                title,
                f"Surface: {project['controller']['surface']['shape']} {project['controller']['surface']['width']} x {project['controller']['surface']['height']} mm",
                f"Components: {len(project['components'])}",
                f"Types: {summary or 'none'}",
            ]
        )


def _build_form() -> dict[str, Any]:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide import QtGui as QtWidgets  # type: ignore
        except ImportError:
            return {
                "template": _FallbackCombo(),
                "variant": _FallbackCombo(),
                "preview": _FallbackText(),
            }

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    form = QtWidgets.QFormLayout()
    template = QtWidgets.QComboBox()
    variant = QtWidgets.QComboBox()
    preview = QtWidgets.QPlainTextEdit()
    preview.setReadOnly(True)
    form.addRow("Template", template)
    form.addRow("Variant", variant)
    layout.addLayout(form)
    layout.addWidget(preview)
    return {
        "widget": widget,
        "template": template,
        "variant": variant,
        "preview": preview,
    }


def _template_label(item: dict[str, Any]) -> str:
    template = item["template"]
    return f"{template['name']} ({template['id']})"


def _variant_label(item: dict[str, Any]) -> str:
    variant = item["variant"]
    return f"{variant['name']} ({variant['id']})"


def _set_combo_items(combo: Any, items: list[str]) -> None:
    if hasattr(combo, "clear"):
        combo.clear()
    if hasattr(combo, "addItems"):
        combo.addItems(items)
    else:
        combo.items = list(items)
        combo.index = 0


def _current_text(combo: Any) -> str:
    if hasattr(combo, "currentText"):
        return str(combo.currentText())
    return combo.items[combo.index] if combo.items else ""


def _set_text(widget: Any, value: str) -> None:
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(value)
    else:
        widget.text = value


class _FallbackCombo:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.index = 0


class _FallbackText:
    def __init__(self) -> None:
        self.text = ""
