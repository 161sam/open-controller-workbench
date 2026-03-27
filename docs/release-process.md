# Release Process

## Scope

This document describes the GitHub release workflow prepared for `v0.1.0`.

## Release trigger

The repository contains one release workflow:

- `.github/workflows/release-v0.1.yml`

It supports two trigger paths:

1. Push the exact tag `v0.1.0`
2. Run the workflow manually with `workflow_dispatch`

## Release notes source

The workflow uses:

- `RELEASE_NOTES_v0.1.md`

This is intentional. For the first release, a fixed file is more robust than auto-generated notes.

## Produced release artifacts

The workflow publishes these artifacts to the GitHub Release:

- source distribution: `dist/ocw-workbench-0.1.0.tar.gz`
- wheel distribution: `dist/ocw_workbench-0.1.0-py3-none-any.whl`
- workbench module archive:
  - `dist/release/OpenControllerWorkbench-v0.1.0-workbench.zip`

The workbench archive is meant for users who want the FreeCAD module-root layout directly.

## Workflow behavior

The workflow performs these steps:

1. Check out the repository with tags
2. Set up Python 3.12
3. Validate the release tag metadata
4. Install build tooling
5. Run release sanity tests
6. Build `sdist` and `wheel`
7. Create the module-root workbench zip archive
8. Create the GitHub Release and upload all release assets

## Draft vs published

- Tag-triggered runs publish a non-draft release by default
- Manual runs allow setting `draft: true`

This supports a release-manager flow where the asset build can be checked before final publication.

## Required GitHub permissions

The workflow uses:

- `contents: write`

No custom secrets are required beyond the standard `GITHUB_TOKEN`.

## How to create the v0.1.0 release

### Recommended path

1. Confirm `CHANGELOG.md`, `RELEASE_NOTES_v0.1.md`, and `README.md` are up to date.
2. Run the release sanity tests locally.
3. Push the release commit.
4. Create and push tag `v0.1.0`.
5. Wait for `.github/workflows/release-v0.1.yml` to complete.
6. Inspect uploaded assets and the generated GitHub Release page.

### Manual dry-run style path

1. Open the GitHub Actions tab.
2. Run `Release v0.1` manually.
3. Keep `tag_name = v0.1.0`.
4. Set `draft = true`.
5. Inspect the draft release and uploaded artifacts.

## Notes for later releases

This workflow is intentionally narrow for the first release.

For later versions, update or generalize:

- tag pattern
- release notes file selection
- asset naming
- release checklist references
