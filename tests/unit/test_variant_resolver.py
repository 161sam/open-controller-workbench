import pytest

from ocw_workbench.variants.generator import VariantGenerator
from ocw_workbench.variants.resolver import VariantResolver


def test_variant_generator_replaces_fader_component():
    project = VariantGenerator().generate_from_variant("fader_strip_45mm")
    fader = next(component for component in project["components"] if component["id"] == "fader1")

    assert fader["library_ref"] == "generic_45mm_linear_fader"
    assert project["controller"]["surface"]["height"] == 124
    assert project["variant"]["id"] == "fader_strip_45mm"


def test_variant_generator_adds_oled_component():
    project = VariantGenerator().generate_from_variant("pad_grid_4x4_oled")
    component_ids = {component["id"] for component in project["components"]}

    assert "oled_status" in component_ids
    assert len(project["components"]) == 17
    assert project["controller"]["surface"]["width"] == 220


def test_variant_generator_sets_handedness_for_display_nav_variants():
    generator = VariantGenerator()

    left = generator.generate_from_variant("display_nav_left")
    right = generator.generate_from_variant("display_nav_right")

    assert left["defaults"]["handedness"] == "left"
    assert right["defaults"]["handedness"] == "right"
    assert left["layout"]["config"]["nav_alignment"] == "left"
    assert right["layout"]["config"]["nav_alignment"] == "right"


def test_runtime_overrides_take_precedence_over_variant():
    project = VariantGenerator().generate_from_variant(
        "encoder_module_compact",
        overrides={
            "controller": {"surface": {"width": 112}},
            "defaults": {"handedness": "right"},
        },
    )

    assert project["controller"]["surface"]["width"] == 112
    assert project["defaults"]["handedness"] == "right"


def test_variant_overrides_take_precedence_over_template_defaults():
    project = VariantGenerator().generate_from_variant("encoder_module_wide")

    assert project["controller"]["surface"]["width"] == 168
    assert project["layout"]["config"]["spacing_x_mm"] == 34


def test_unknown_variant_raises_key_error():
    with pytest.raises(KeyError, match="Unknown variant id: does_not_exist"):
        VariantGenerator().generate_from_variant("does_not_exist")


def test_unknown_template_for_variant_raises_key_error():
    resolver = VariantResolver()

    with pytest.raises(KeyError, match="Unknown template id for variant 'broken_variant': does_not_exist"):
        resolver.resolve(
            {
                "variant": {
                    "id": "broken_variant",
                    "template_id": "does_not_exist",
                },
                "overrides": {},
            }
        )


def test_replace_target_not_found_raises_error():
    resolver = VariantResolver()

    with pytest.raises(ValueError, match="Replace target not found: missing_component"):
        resolver.resolve(
            {
                "variant": {
                    "id": "broken_replace",
                    "template_id": "encoder_module",
                },
                "overrides": {
                    "components": {
                        "replace": [
                            {
                                "match_id": "missing_component",
                                "with": {
                                    "id": "encX",
                                    "type": "encoder",
                                    "library_ref": "alps_ec11e15204a3",
                                },
                            }
                        ]
                    }
                },
            }
        )


def test_remove_target_not_found_raises_error():
    resolver = VariantResolver()

    with pytest.raises(ValueError, match="Remove target not found: missing_component"):
        resolver.resolve(
            {
                "variant": {
                    "id": "broken_remove",
                    "template_id": "encoder_module",
                },
                "overrides": {
                    "components": {
                        "remove": [
                            {
                                "match_id": "missing_component",
                            }
                        ]
                    }
                },
            }
        )


def test_added_component_missing_library_ref_raises_error():
    resolver = VariantResolver()

    with pytest.raises(ValueError, match="Added component missing library_ref: oled_status"):
        resolver.resolve(
            {
                "variant": {
                    "id": "broken_add",
                    "template_id": "encoder_module",
                },
                "overrides": {
                    "components": {
                        "add": [
                            {
                                "id": "oled_status",
                                "type": "display",
                            }
                        ]
                    }
                },
            }
        )
