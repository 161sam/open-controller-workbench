# MIDI Controller Layout Intelligence

## Scope

This MVP adds lightweight layout guidance to `plugin_midicontroller`.

It does not attempt full auto-layout or generic recommendation logic across every domain.

## What The MVP Adds

Templates can now describe:

- `workflow_hint`
- `ideal_for`
- `next_step`
- `layout_zones`
- `smart_defaults`
- `suggested_additions`

Components can now describe:

- `ocf.role`
- `ocf.placement_preference`

## Template Patterns

Current high-value patterns:

- `pad_grid_4x4`
  - utility strip on the right
  - navigation encoder pair on the top row
  - centered display header
- `encoder_module`
  - centered display header
  - compact utility buttons below
- `fader_strip`
  - display or label area above the lane
  - one top encoder above the strip
- `display_nav_module`
  - transport row below the navigation controls
- `transport_module`
  - display header above the row
  - jog encoder on the right

## Placement Heuristics

The MVP uses a small deterministic rule set:

- `right_of_main`
- `top_row`
- `centered_above_group`
- `bottom_transport_row`
- `aligned_with_group`

Anchor selection prefers:

1. template smart default primary zone
2. template smart default primary group role
3. current component bounds

## What It Can Do

- expose template-specific next-step suggestions
- generate deterministic default positions for suggested additions
- suggest a sensible default position for a newly added component type
- keep added controls grouped through `group_id` and `group_role`

## What It Does Not Do

- full controller relayout
- collision solving beyond normal layout / validation paths
- adaptive optimization or AI placement
- generic cross-domain recommendation logic

## Next Evolution

Later product work can build on this metadata to add:

- quick actions in existing panels
- template-aware one-click add flows
- richer secondary-layout patterns for larger controllers
