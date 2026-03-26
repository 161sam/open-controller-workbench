from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from ocw_workbench.pipeline.runner import run_full_pipeline
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.variant_service import VariantService


def main() -> int:
    template_service = TemplateService()
    variant_service = VariantService()

    templates = template_service.list_templates()
    variants = variant_service.list_variants()

    print(f"Templates OK: {len(templates)} loaded")
    print(f"Variants OK: {len(variants)} loaded")

    warnings = 0
    project_paths = sorted(Path("examples/projects").glob("*.yaml"))
    with tempfile.TemporaryDirectory(prefix="ocw-smoke-") as temp_dir:
        for project_path in project_paths:
            result = run_full_pipeline(project_path, output_dir=Path(temp_dir) / project_path.stem)
            warnings += len(result["warnings"])

    print(f"Pipeline OK: {len(project_paths)} demo projects")
    print(f"Warnings: {warnings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
