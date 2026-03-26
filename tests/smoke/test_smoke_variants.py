from ocw_workbench.services.variant_service import VariantService


def test_all_variants_load():
    variants = VariantService().list_variants()

    assert variants
    assert all("variant" in item for item in variants)
