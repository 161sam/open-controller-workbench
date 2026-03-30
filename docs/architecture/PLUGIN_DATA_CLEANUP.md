# Plugin Data Cleanup

## Scope

This cleanup removes controller-specific legacy data from generic core locations and keeps only technical infrastructure in `ocw_workbench/plugins/internal/`.

## Removed From Core

The following legacy core data locations no longer carry MIDI/controller-specific project data:

- `ocw_workbench/library/components/`
- `ocw_workbench/templates/library/`
- `ocw_workbench/variants/library/`

These locations previously duplicated `plugin_midicontroller` data and kept domain content in the core.

## Kept In The Domain Plugin

`plugin_midicontroller` is now the primary source for:

- controller component libraries
- controller templates
- controller variants

Runtime loading now resolves those assets from:

- `plugins/plugin_midicontroller/components/`
- `plugins/plugin_midicontroller/templates/`
- `plugins/plugin_midicontroller/variants/`

## Moved Out Of Internal

The following domain-oriented packs were moved from `ocw_workbench/plugins/internal/` to `ocw_workbench/plugins/external/`:

- `basic_components_pack`
- `basic_templates_pack`
- `basic_variants_pack`
- `export_jlcpcb`
- `export_svg_panel`
- `export_eurorack`
- `export_mouser`

Reason:

- they are not generic core infrastructure
- they are controller, panel, PCB, or sample-pack oriented
- keeping them internal would blur the core/domain boundary

## Removed Internal Legacy Packs

These internal legacy packs were removed entirely:

- `core_components`
- `default_templates`
- `default_variants`

Reason:

- they only mirrored domain data that now lives in `plugin_midicontroller`
- keeping them would preserve duplicate domain sources

## Still In Internal

`ocw_workbench/plugins/internal/` now keeps only:

- `default_exporters`

This stays because it is currently treated as technical export infrastructure rather than domain-owned library data.

## Loader And Strict Mode

Fallback adapters for components, templates, and variants no longer fall back to old core library directories.

Implications:

- active domain plugin roots are the authoritative source
- plugin-pack sources remain valid
- strict mode no longer receives hidden controller data from core fallbacks

## Remaining Compatibility

Compatibility still exists through:

- plugin alias resolution for namespaced pack data such as `basic_components_pack.*`
- external plugin-pack loading through the existing plugin loader

No duplicate core/domain data source remains for the removed controller libraries.
