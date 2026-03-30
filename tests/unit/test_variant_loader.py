from pathlib import Path

import pytest

from ocw_workbench.utils.yaml_io import dump_yaml, load_yaml
from ocw_workbench.variants.loader import VariantLoader
from ocw_workbench.variants.registry import VariantRegistry


def test_variant_loader_loads_fader_strip_variant():
    variant = VariantLoader().load("plugins/plugin_midicontroller/variants/fader_strip_60mm.yaml")

    assert variant.id == "fader_strip_60mm"
    assert variant.template_id == "fader_strip"
    assert variant.overrides["components"]["replace"][0]["with"]["library_ref"] == "generic_60mm_linear_fader"


def test_variant_registry_lists_default_variants():
    registry = VariantRegistry()
    variants = registry.list_variants()
    ids = {variant["variant"]["id"] for variant in variants}
    fixture = load_yaml("tests/fixtures/variant_lookup_expected.yaml")

    assert set(fixture["expected_variants"]).issubset(ids)
    assert "basic_variants_pack.simple_variant" in ids


def test_variant_registry_filters_by_template_and_tag():
    registry = VariantRegistry()

    fader_variants = registry.list_variants(template_id="fader_strip")
    left_variants = registry.list_variants(tag="left")

    assert {variant["variant"]["id"] for variant in fader_variants} == {"fader_strip_45mm", "fader_strip_60mm"}
    assert {variant["variant"]["id"] for variant in left_variants} == {"display_nav_left"}


def test_variant_loader_rejects_missing_template_id(tmp_path: Path):
    path = tmp_path / "broken.yaml"
    dump_yaml(
        path,
        {
            "variant": {
                "id": "broken_variant",
                "name": "Broken Variant",
                "description": "Missing template id",
            },
            "overrides": {},
        },
    )

    with pytest.raises(ValueError, match="missing a valid 'template_id'"):
        VariantLoader().load(path)


def test_variant_loader_rejects_unknown_component_operation(tmp_path: Path):
    path = tmp_path / "broken_ops.yaml"
    dump_yaml(
        path,
        {
            "variant": {
                "id": "broken_ops",
                "name": "Broken Ops",
                "description": "Unknown component override op",
                "template_id": "encoder_module",
            },
            "overrides": {
                "components": {
                    "shuffle": [],
                }
            },
        },
    )

    with pytest.raises(ValueError, match="unknown component override operations"):
        VariantLoader().load(path)


def test_data_plugin_variant_alias_resolves_and_adds_component():
    from ocw_workbench.variants.generator import VariantGenerator

    project = VariantGenerator().generate_from_variant("simple_variant")

    assert project["variant"]["id"] == "basic_variants_pack.simple_variant"
    assert any(component["id"] == "btn2" for component in project["components"])
    assert next(component for component in project["components"] if component["id"] == "enc1")["x"] == 30.0
