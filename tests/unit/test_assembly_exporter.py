from pathlib import Path

from ocw_workbench.exporters.assembly_exporter import export_assembly
from ocw_workbench.manufacturing.assembly_builder import AssemblyBuilder


def test_assembly_builder_and_exporter_create_structured_output(tmp_path: Path):
    builder = AssemblyBuilder()
    assembly = builder.build({"id": "demo"}, [{"id": "enc1", "type": "encoder"}])
    path = tmp_path / "controller.assembly.yaml"
    export_assembly(assembly, path)

    assert assembly["major_subassemblies"]
    assert assembly["steps"]
    assert path.exists()
