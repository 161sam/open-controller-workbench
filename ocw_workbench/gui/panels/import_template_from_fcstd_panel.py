from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    FallbackValue,
    configure_combo_box,
    current_text,
    load_qt,
    set_combo_items,
    set_text,
    set_tooltip,
    text_value,
    widget_value,
)
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.templates.fcstd_importer import FCStdTemplateImporter


class ImportTemplateFromFCStdPanel:
    def __init__(
        self,
        importer: FCStdTemplateImporter | None = None,
        template_service: TemplateService | None = None,
        on_imported: Any | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.importer = importer or FCStdTemplateImporter()
        self.template_service = template_service or TemplateService()
        self.on_imported = on_imported
        self.on_status = on_status
        self._targets: list[dict[str, str]] = []
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._configure_tooltips()
        self._connect_events()

    def browse_fcstd(self) -> None:
        _qtcore, _qtgui, qtwidgets = load_qt()
        if qtwidgets is None or not hasattr(qtwidgets, "QFileDialog"):
            raise RuntimeError("FCStd file picker requires a Qt binding")
        path, _selected = qtwidgets.QFileDialog.getOpenFileName(
            None,
            "Select FCStd File",
            "",
            "FreeCAD Documents (*.FCStd)",
        )
        if path:
            set_text(self.form["file_path"], str(path))
            self.load_targets()

    def load_targets(self) -> None:
        fcstd_path = text_value(self.form["file_path"]).strip()
        if not fcstd_path:
            raise ValueError("Choose an FCStd file first")
        self._targets = self.importer.list_targets(fcstd_path)
        target_labels = [item["label"] for item in self._targets if item["kind"] in {"object", "face"}]
        vertex_labels = [item["label"] for item in self._targets if item["kind"] == "vertex"]
        set_combo_items(self.form["target"], target_labels)
        set_combo_items(self.form["origin_vertex"], ["manual"] + vertex_labels)
        stem = Path(fcstd_path).stem
        if not text_value(self.form["template_id"]).strip():
            set_text(self.form["template_id"], stem.lower().replace("-", "_").replace(" ", "_"))
        if not text_value(self.form["name"]).strip():
            set_text(self.form["name"], stem.replace("_", " ").replace("-", " ").title())
        self._publish_status(
            f"Loaded {len(self._targets)} import targets from '{Path(fcstd_path).name}'. "
            "Leave Stage B disabled for YAML-only import, or enable it to reference the source FCStd as base geometry."
        )

    def import_template(self) -> Path:
        target_label = current_text(self.form["target"])
        target_ref = self._target_id_for_label(target_label)
        origin_label = current_text(self.form["origin_vertex"])
        origin_ref = None if origin_label in {"", "manual"} else self._target_id_for_label(origin_label)
        output_path = self.importer.import_template(
            fcstd_path=text_value(self.form["file_path"]).strip(),
            target_ref=target_ref,
            template_id=text_value(self.form["template_id"]).strip(),
            name=text_value(self.form["name"]).strip(),
            rotation_deg=widget_value(self.form["rotation"]),
            offset_x=widget_value(self.form["offset_x"]),
            offset_y=widget_value(self.form["offset_y"]),
            height_override=widget_value(self.form["height"]) if self.form["height_enabled"].isChecked() else None,
            origin_ref=origin_ref,
            use_source_as_base_geometry=self._use_source_as_base_geometry(),
        )
        self.template_service.registry.load_all()
        if self.on_imported is not None:
            self.on_imported(output_path)
        mode_label = "Stage B" if self._use_source_as_base_geometry() else "Stage A"
        self._publish_status(f"Imported template saved to '{output_path.name}' using {mode_label}.")
        return output_path

    def handle_browse_clicked(self) -> None:
        try:
            self.browse_fcstd()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not choose FCStd file", exc))

    def handle_load_targets_clicked(self) -> None:
        try:
            self.load_targets()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not inspect FCStd file", exc))

    def handle_import_clicked(self) -> None:
        try:
            self.import_template()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not import template", exc))

    def _target_id_for_label(self, label: str) -> str:
        for item in self._targets:
            if item["label"] == label:
                return item["id"]
        raise ValueError(f"Unknown target label '{label}'")

    def _connect_events(self) -> None:
        if hasattr(self.form["browse_button"], "clicked"):
            self.form["browse_button"].clicked.connect(self.handle_browse_clicked)
        if hasattr(self.form["load_targets_button"], "clicked"):
            self.form["load_targets_button"].clicked.connect(self.handle_load_targets_clicked)
        if hasattr(self.form["import_button"], "clicked"):
            self.form["import_button"].clicked.connect(self.handle_import_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["file_path"], "FCStd file to inspect and convert into a YAML template.")
        set_tooltip(self.form["target"], "Object or face used as the top-surface reference for width/depth extraction.")
        set_tooltip(self.form["origin_vertex"], "Optional origin vertex used for metadata and mounting-hole offsets.")
        set_tooltip(self.form["offset_x"], "Manual X offset applied to imported reference points.")
        set_tooltip(self.form["offset_y"], "Manual Y offset applied to imported reference points.")
        set_tooltip(self.form["rotation"], "Optional rotation applied to projected surface width/depth.")
        set_tooltip(self.form["height"], "Optional controller height override. If disabled, uses document bounding height.")
        set_tooltip(self.form["template_id"], "Template id for the generated YAML file.")
        set_tooltip(self.form["name"], "Template name shown in the Create panel.")
        set_tooltip(
            self.form["use_source_as_base_geometry"],
            "Enable Stage B to reference the source FCStd as custom base geometry for the top plate workflow.",
        )

    def _publish_status(self, message: str) -> None:
        level = "error" if message.lower().startswith("could not") else "info"
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message)

    def _use_source_as_base_geometry(self) -> bool:
        field = self.form["use_source_as_base_geometry"]
        return bool(field.isChecked()) if hasattr(field, "isChecked") else False


def _build_form() -> dict[str, Any]:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return {
            "widget": object(),
            "file_path": FallbackText(),
            "browse_button": FallbackButton("Browse FCStd"),
            "load_targets_button": FallbackButton("Load Targets"),
            "target": FallbackCombo(),
            "origin_vertex": FallbackCombo(["manual"]),
            "offset_x": FallbackValue(0.0),
            "offset_y": FallbackValue(0.0),
            "rotation": FallbackValue(0.0),
            "height": FallbackValue(0.0),
            "height_enabled": type("FallbackCheck", (), {"isChecked": lambda self: False})(),
            "template_id": FallbackText(),
            "name": FallbackText(),
            "use_source_as_base_geometry": type("FallbackCheck", (), {"isChecked": lambda self: False})(),
            "import_button": FallbackButton("Import Template"),
            "status": FallbackLabel(),
        }

    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    form = qtwidgets.QFormLayout()

    file_row = qtwidgets.QHBoxLayout()
    file_path = qtwidgets.QLineEdit()
    browse_button = qtwidgets.QPushButton("Browse FCStd")
    load_targets_button = qtwidgets.QPushButton("Load Targets")
    file_row.addWidget(file_path, 1)
    file_row.addWidget(browse_button)
    file_row.addWidget(load_targets_button)

    target = qtwidgets.QComboBox()
    origin_vertex = qtwidgets.QComboBox()
    configure_combo_box(target)
    configure_combo_box(origin_vertex)
    offset_x = qtwidgets.QDoubleSpinBox()
    offset_y = qtwidgets.QDoubleSpinBox()
    rotation = qtwidgets.QDoubleSpinBox()
    rotation.setRange(-360.0, 360.0)
    rotation.setSingleStep(90.0)
    height = qtwidgets.QDoubleSpinBox()
    height.setRange(0.0, 10000.0)
    height_enabled = qtwidgets.QCheckBox("Override height")
    template_id = qtwidgets.QLineEdit()
    name = qtwidgets.QLineEdit()
    use_source_as_base_geometry = qtwidgets.QCheckBox("Use source FCStd as base geometry (Stage B)")
    import_button = qtwidgets.QPushButton("Import Template")
    status = qtwidgets.QLabel("Choose an FCStd file to inspect. Stage A saves YAML only. Stage B also references the source FCStd as base geometry.")
    status.setWordWrap(True)

    form.addRow("FCStd File", file_row)
    form.addRow("Top Reference", target)
    form.addRow("Origin Vertex", origin_vertex)
    form.addRow("Offset X", offset_x)
    form.addRow("Offset Y", offset_y)
    form.addRow("Rotation", rotation)
    form.addRow("Height", height)
    form.addRow("", height_enabled)
    form.addRow("Template ID", template_id)
    form.addRow("Name", name)
    form.addRow("", use_source_as_base_geometry)
    layout.addLayout(form)
    layout.addWidget(import_button)
    layout.addWidget(status)
    return {
        "widget": widget,
        "file_path": file_path,
        "browse_button": browse_button,
        "load_targets_button": load_targets_button,
        "target": target,
        "origin_vertex": origin_vertex,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "rotation": rotation,
        "height": height,
        "height_enabled": height_enabled,
        "template_id": template_id,
        "name": name,
        "use_source_as_base_geometry": use_source_as_base_geometry,
        "import_button": import_button,
        "status": status,
    }
