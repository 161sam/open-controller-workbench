# Release Prep v0.x

This note collects the repo-facing preparation items for the next visible OCW release.

## Release communication set

Prepare these items together:

- `CHANGELOG.md`
- release draft in [releases/v0x_release_draft.md](releases/v0x_release_draft.md)
- `README.md`
- `docs/manual_ux_checklist.md`
- `docs/demo_flow.md`

## Recommended screenshots

Capture these 5 screenshots:

1. Full workbench overview
   - show toolbar, mini-inspector, 3D view, and one created template-based controller
2. Guided placement in a valid target area
   - show ghost preview and active target highlight
3. Guided placement in an invalid target area
   - show invalid target feedback clearly
4. Selection with on-object actions
   - show one selected component plus `Duplicate`, `Rotate`, and `Mirror`
5. Drag move plus inspector context
   - show selected component being moved and the mini-inspector reacting

## Recommended short GIFs

Capture these 2 short GIFs:

1. Guided placement flow
   - start suggested addition
   - move from invalid to valid target
   - release to place
2. Selection to action flow
   - hover component
   - select component
   - drag move or run `Duplicate`

Keep both GIFs short, under 10 seconds, and framed tightly around the 3D view plus mini-inspector.

## Release scope statement

Use this release framing:

- focused on workflow maturity, interaction clarity, and demo readiness
- not a feature-complete CAD editing release
- not a broad plugin-platform release

## Before creating a real GitHub release

1. Walk through the demo flow once in FreeCAD.
2. Run the documented manual UX checklist at least once.
3. Capture the recommended screenshots.
4. Finalize the release draft text.
5. Verify release metadata and packaging files still match the intended version.
