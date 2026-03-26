# Performance Metrics

## Goal

Open Controller now exposes lightweight internal timing data so sync and overlay costs can
be measured instead of guessed.

The metrics are intended for:

- debugging slow documents
- comparing refactors
- identifying whether time is spent in state handling, geometry rebuild, boolean work,
  overlay build, overlay render, or document recompute

## Always-Available Metrics

These metrics are written in normal operation and do not require a debug flag.

### State

Document metadata key:

- `OCWStateMetrics`

Fields:

- `load.duration_ms`
- `load.source`
- `load.controller_id`
- `save.duration_ms`
- `save.source`
- `save.controller_id`
- `save.payload_bytes`

### Sync

Document metadata key:

- `OCWLastSync`

Relevant fields:

- `requested_sync_mode`
- `sync_mode`
- `sync_duration_ms`
- `builder_body_generation_ms`
- `builder_top_plate_generation_ms`
- `cutout_generation_ms`
- `boolean_phase_ms`
- `document_recompute_ms`
- `generated_object_count`
- `cutout_tool_count`
- `cutout_diagnostic_count`

### Overlay

Document metadata key:

- `OCWOverlayRender`

Relevant fields:

- `build_duration_ms`
- `render_duration_ms`
- `render_path`
- `render_item_count`
- `dropped_item_count`
- `dropped_reasons`

## Optional Detailed Profiling

Detailed grouped profiling is disabled by default.

Enable it by setting:

```python
doc.OCWDebugProfiling = {"enabled": True, "log": False}
```

or:

```python
doc.OCWDebugProfiling = True
```

Behavior:

- `enabled=True`: collect grouped metrics into `OCWPerformance`
- `log=True`: also print compact profiling lines to the FreeCAD console

Document metadata key:

- `OCWPerformance`

Structure:

```python
{
    "enabled": True,
    "sections": {
        "state": {
            "load": {...},
            "save": {...},
        },
        "sync": {
            "full_sync": {...},
            "builder_body_generation_ms": {...},
            "builder_top_plate_generation_ms": {...},
            "cutout_generation_ms": {...},
            "boolean_phase_ms": {...},
            "document_recompute_ms": {...},
            "visual_refresh": {...},
        },
        "overlay": {
            "build": {...},
            "render": {...},
        },
    },
}
```

## How To Interpret The Metrics

### `state`

High `load` or `save` times usually indicate large project payloads or repeated state
serialization, not geometry problems.

### `builder_body_generation_ms`

Time spent building the enclosure body feature shape.
If this grows disproportionately, the shell geometry is likely becoming too complex.

### `builder_top_plate_generation_ms`

Time spent building the top plate before cutouts.
If this is already high before booleans, the base plate geometry itself is the cost.

### `cutout_generation_ms`

Time spent planning or preparing cutout inputs.
If this grows with component count, the cutout planning path is likely the scaling factor.

### `boolean_phase_ms`

Time spent applying cutouts to the top plate.
If this dominates, boolean complexity is the current bottleneck.

### `document_recompute_ms`

Time spent in `doc.recompute()`.
If this dominates while shape-build times stay low, the bottleneck is FreeCAD document
evaluation rather than the Python-side planning work.

### `overlay.build`

Time spent creating overlay payload data from current state.
If this is high, overlay item generation is too expensive.

### `overlay.render`

Time spent normalizing payload items and updating the overlay object/view provider.
If this is high while `overlay.build` is low, the rendering/update path is the issue.

## Recommended Debug Workflow

1. Enable profiling on the active document.
2. Run the action you want to inspect:
   - create controller
   - auto layout
   - move component
   - validate
   - toggle overlay
3. Inspect:
   - `OCWStateMetrics`
   - `OCWLastSync`
   - `OCWOverlayRender`
   - `OCWPerformance` if detailed profiling is enabled
4. Decide whether the bottleneck is:
   - state serialization
   - geometry planning
   - boolean work
   - recompute
   - overlay build
   - overlay render

## Design Rule

Keep the lightweight metrics always available and the detailed profiling optional.

This gives the project:

- low-noise normal operation
- measurable performance work during refactors
- a stable basis for future partial-sync optimization
