from ocw_workbench.templates.parameters import TemplateParameterResolver


def test_parameter_schema_builds_controls_with_defaults():
    template = {
        "parameters": [
            {"id": "pad_count_x", "type": "int", "default": 4, "min": 2, "max": 8, "control": "slider"},
            {
                "id": "fader_length",
                "type": "enum",
                "default": 60,
                "options": [{"value": 45, "label": "45 mm"}, {"value": 60, "label": "60 mm"}],
            },
        ]
    }

    model = TemplateParameterResolver().build_ui_model(template)

    assert model["values"]["pad_count_x"] == 4
    assert model["controls"][0]["control"] == "slider"
    assert model["controls"][1]["options"][1]["value"] == 60


def test_parameter_schema_applies_preset_and_user_override_sources():
    template = {
        "parameters": [
            {"id": "pad_count_x", "type": "int", "default": 4, "min": 2, "max": 8},
            {"id": "case_width", "type": "float", "default": 180.0, "min": 120.0, "max": 320.0},
        ],
        "parameter_presets": [
            {"id": "wide", "name": "Wide", "values": {"pad_count_x": 8, "case_width": 300.0}},
        ],
    }

    model = TemplateParameterResolver().build_ui_model(template, values={"case_width": 290.0}, preset_id="wide")

    assert model["values"] == {"pad_count_x": 8, "case_width": 290.0}
    assert model["sources"] == {"pad_count_x": "preset", "case_width": "user"}


def test_parameter_bindings_generate_component_grid_and_mapped_component_refs():
    template = {
        "controller": {"width": 180.0, "depth": 180.0, "surface": {"width": 180.0, "height": 180.0}},
        "zones": [{"id": "pad_matrix", "type": "grid"}],
        "components": [{"id": "fader1", "type": "fader", "library_ref": "generic_60mm_linear_fader"}],
        "parameters": [
            {"id": "pad_count_x", "type": "int", "default": 4, "min": 1, "max": 8},
            {"id": "pad_count_y", "type": "int", "default": 2, "min": 1, "max": 8},
            {
                "id": "fader_length",
                "type": "enum",
                "default": 45,
                "options": [{"value": 45, "label": "45 mm"}, {"value": 60, "label": "60 mm"}],
            },
        ],
        "parameter_bindings": {
            "values": [
                {
                    "target": "components[fader1].library_ref",
                    "parameter": "fader_length",
                    "value_map": {"45": "generic_45mm_linear_fader", "60": "generic_60mm_linear_fader"},
                }
            ],
            "component_grids": [
                {
                    "id_prefix": "pad",
                    "group_id": "pad_matrix",
                    "group_role": "performance_pad_matrix",
                    "label_pattern": "Pad {row},{col}",
                    "count_x_parameter": "pad_count_x",
                    "count_y_parameter": "pad_count_y",
                    "component": {"type": "pad", "library_ref": "generic_mpc_pad_30mm", "zone": "pad_matrix"},
                }
            ],
        },
    }

    resolved = TemplateParameterResolver().apply(
        template,
        values={"pad_count_x": 3, "pad_count_y": 2, "fader_length": 45},
    )

    assert resolved["components"][0]["library_ref"] == "generic_45mm_linear_fader"
    assert len(resolved["components"]) == 7
    assert resolved["components"][1]["id"] == "pad1"
    assert resolved["components"][1]["group_id"] == "pad_matrix"
    assert resolved["components"][1]["group_role"] == "performance_pad_matrix"
    assert resolved["components"][1]["row"] == 0
    assert resolved["components"][1]["col"] == 0
    assert resolved["components"][1]["label"] == "Pad 1,1"


def test_parameter_bindings_map_component_selection_for_display_and_knob_profiles():
    template = {
        "controller": {"width": 160.0, "depth": 90.0, "surface": {"width": 160.0, "height": 90.0}},
        "components": [
            {"id": "oled_status", "type": "display", "library_ref": "adafruit_oled_096_i2c_ssd1306"},
            {"id": "enc_left", "type": "encoder", "library_ref": "generic_ec11_encoder_with_push"},
        ],
        "parameters": [
            {
                "id": "display_size_inch",
                "type": "enum",
                "default": "0.96",
                "options": [{"value": "0.96", "label": "0.96 inch"}, {"value": "1.3", "label": "1.3 inch"}],
            },
            {
                "id": "knob_diameter",
                "type": "enum",
                "default": 24,
                "options": [{"value": 18, "label": "18 mm"}, {"value": 24, "label": "24 mm"}],
            },
        ],
        "parameter_bindings": {
            "values": [
                {
                    "target": "components[oled_status].library_ref",
                    "parameter": "display_size_inch",
                    "value_map": {"0.96": "adafruit_oled_096_i2c_ssd1306", "1.3": "adafruit_oled_130_i2c_ssd1306"},
                },
                {
                    "target": "components[enc_left].library_ref",
                    "parameter": "knob_diameter",
                    "value_map": {"18": "generic_ec11_encoder_with_push", "24": "generic_ec11_encoder_with_push_large_knob"},
                },
            ]
        },
    }

    resolved = TemplateParameterResolver().apply(
        template,
        values={"display_size_inch": "1.3", "knob_diameter": 24},
    )

    assert resolved["components"][0]["library_ref"] == "adafruit_oled_130_i2c_ssd1306"
    assert resolved["components"][1]["library_ref"] == "generic_ec11_encoder_with_push_large_knob"


def test_parameter_references_resolve_exact_numeric_and_embedded_string_values():
    template = {
        "controller": {
            "width": "${parameters.case_width}",
            "surface": {
                "width": "${parameters.case_width}",
                "label": "Case ${parameters.case_width} mm",
            },
        },
        "parameters": [
            {"id": "case_width", "type": "float", "default": 180.0},
        ],
    }

    resolved = TemplateParameterResolver().apply(template, values={"case_width": 190.0})

    assert resolved["controller"]["width"] == 190.0
    assert resolved["controller"]["surface"]["width"] == 190.0
    assert resolved["controller"]["surface"]["label"] == "Case 190.0 mm"


def test_parameter_references_raise_clear_error_for_unknown_parameter():
    template = {
        "controller": {"width": "${parameters.unknown_width}"},
        "parameters": [{"id": "case_width", "type": "float", "default": 180.0}],
    }

    try:
        TemplateParameterResolver().apply(template)
    except ValueError as exc:
        assert "unknown_width" in str(exc)
        assert "controller.width" in str(exc)
    else:
        raise AssertionError("Expected parameter reference error")
