from ocw_workbench.services.template_service import TemplateService


def test_all_templates_load():
    templates = TemplateService().list_templates()

    assert templates
    assert all("template" in item for item in templates)
