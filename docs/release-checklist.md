# Release Checklist

## Scope

This checklist is for preparing `v0.1.0` and later early OCW releases.

## Metadata

- Confirm `pyproject.toml` version matches `ocw_workbench/version.py`
- Confirm `VERSION` matches the package version
- Confirm `ocw_workbench/__init__.py` exposes `__version__`
- Confirm README references the same release version

## Packaging

- Confirm `Init.py`, `InitGui.py`, and `ocw_kicad_plugin.py` are included in the source distribution
- Confirm YAML template, variant, library, and plugin data are included in package metadata
- Confirm icon resources are included for installation/runtime use
- Confirm `InitGui.py` still registers `Open Controller Workbench`

## Documentation

- Update `CHANGELOG.md`
- Update `RELEASE_NOTES_v0.1.md` or the current release-notes document
- Update `docs/releases/v0x_release_draft.md` for the active visible release
- Update `docs/release_prep_v0x.md` if screenshot or demo recommendations changed
- Update `docs/release-process.md` if the workflow or artifact set changes
- Verify `docs/README.md` points new users to installation and quick-start material
- Verify README installation and first-run sections
- Verify `examples/README.md` matches the current demo templates
- Verify `screenshots/` contains real FreeCAD captures before publishing the public release
- Verify the recommended 5 screenshots and 2 short GIFs from `docs/release_prep_v0x.md`
- Verify docs links:
  - user guide
  - workflows
  - installation
  - architecture

## Quality

- Run the main unit test suite
- Run `tests/unit/test_release_metadata.py`
- Run `tests/unit/test_release_workflow_metadata.py`
- Perform one manual FreeCAD startup check from a clean module-root symlink
- Verify icons load in the workbench toolbar
- Verify templates, variants, and libraries resolve in the Create panel

## Release blockers

- Final project license not selected yet

## Manual smoke test

1. Start FreeCAD with the repository root linked into the `Mod` directory.
2. Open `Open Controller Workbench`.
3. Create a controller from a template.
4. Add or place a component, then confirm continuous place exits cleanly on `ESC`.
5. Start drag-move, confirm hover highlight appears, and cancel once with `ESC`.
6. Open `Validate`, confirm findings and overlay output stay visible.
7. Reopen the document and confirm project parameters reload when available.
