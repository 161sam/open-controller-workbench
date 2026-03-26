
# Workflows

## Workflow 1 – Setup

- Repo klonen
- Plugin installieren
- Workbench starten

## Workflow 2 – Geometry (Python)

- Controller definieren
- Builder nutzen
- Geometrie erzeugen

## Workflow 3 – Schema Import

- YAML laden
- validieren
- Domain erzeugen
- Geometrie bauen

## Workflow 4 – UI (Ziel)

- Projekt erstellen
- Parameter anpassen
- Komponenten platzieren
- Constraints prüfen
- Export

## Workflow 5 – Schema Export

- controller.hw.yaml erzeugen

## Workflow 6 – KiCad Übergabe

- Outline
- Positionen
- Rotation
- Keepouts

## Workflow 7 – Validation

- fehlende Daten
- Kollisionen
- Constraints

## Workflow 8 – Import FCStd -> refine -> save

- FCStd Datei wählen
- Top Surface Referenz wählen
- Zwischen `Stage A` und `Stage B` wählen
- `Stage A`: YAML Template importieren
- `Stage B`: YAML Template mit `custom_fcstd` Base-Geometry-Referenz importieren
- rohes Template im Template Inspector prüfen
- Parameter und Template-Presets im Inspector prüfen
- Preset anwenden oder Parameter manuell überschreiben
- `Apply` für resolved Preview ohne Speichern
- ID, Name, Maße, Rotation und Origin-Offsets korrigieren
- Zonen und Mounting-Holes bei Bedarf ergänzen oder bereinigen
- Template validieren
- Template direkt speichern oder als User-Template sichern
- Template im Create Panel auswählen
- Controller weiter verfeinern und speichern

## Workflow 9 – Template -> Parameters -> Create

- Template auswählen
- optional Variant auswählen
- Template-Preset anwenden
- Parameter im Parameter-Editor anpassen
- Preview prüfen
- `Create` für neue Controller verwenden
- `Apply Parameters` für bestehende Controller aus derselben Template-/Variant-Auswahl verwenden
- Layout, Komponenten und Constraints danach wie gewohnt weiter bearbeiten

## Workflow 9a – Open Project -> Edit Parameters -> Regenerate

- bestehendes Controller-Dokument öffnen
- Create-Panel liest `template_id`, `variant_id` und gespeicherte Projektparameter aus dem Project State
- wenn vorhanden, werden die zuletzt gespeicherten Projektparameter direkt in den Parameter-Editor geladen
- bei älteren Dokumenten ohne explizite Projektparameter versucht das Panel, Werte aus Legacy-Overrides wiederzuverwenden
- Parameter anpassen
- `Apply Parameters` ausführen
- Resolver erzeugt aus Template oder Variant und den aktuellen Projektwerten erneut einen konsistenten Zielzustand
- Controller-State und Geometrie werden danach gemeinsam regeneriert
- wenn die ursprüngliche Template-Quelle fehlt, bleibt das Dokument lesbar, aber die Re-Parameterisierung wird als nicht verfügbar markiert

## Workflow 10 – Select -> Edit -> Apply -> Validate

- Komponente im 3D-View oder in der Components-Liste auswählen
- Components-Panel liest die selektierte Komponente und ihr Library-Metadatenmodell
- Placement-Felder, generische Metadaten und typabhängige Property-Sektion werden aufgebaut
- Werte im Panel anpassen
- `Apply Changes` schreibt die Änderungen in den Project State
- placements- oder variant-relevante Änderungen laufen über den normalen Geometrie-/Sync-Pfad
- reine Metadatenänderungen bleiben state-only und vermeiden unnötige Voll-Rebuilds
- bei Bedarf Constraints erneut validieren oder Overlay-/Preview-Feedback prüfen

## Workflow 10a – Multi-Select Basics

- erste Komponente auswählen
- weitere Komponenten per modifier-basierter Auswahl hinzufügen oder entfernen
- die Auswahl behält eine Primary Selection für bestehende Single-Component-Flows
- Overlay zeigt Primary und Secondary Selection unterschiedlich an
- Components-Panel bearbeitet weiterhin die Primary Selection
- Info-/Status-Bereiche zeigen die Größe der aktuellen Auswahl
- Folgefeatures wie Bulk Edit, Align/Distribute oder Duplicate können dieselbe Selection-Menge später direkt wiederverwenden

## Stage A And Stage B Compatibility

- Stage A and Stage B use the same registry, template loader, and template inspector flow.
- Stage A remains the robust default import path because it only depends on saved YAML data.
- Stage B adds `controller.geometry.base.type = custom_fcstd` and keeps existing surface, layout, overlay, and sync behavior intact.
- Existing templates without `controller.geometry.base` continue through the standard builder path.
- If a `custom_fcstd` reference cannot be loaded, the builder fails fast and no partially built geometry is kept.

## Interactive Tool Lifecycle

- Only one view-interactive tool session may be active at a time.
- Tool start follows the same lifecycle: resolve view, register callbacks once, create or update overlay preview metadata, then wait for commit or cancel.
- Tool cleanup is idempotent: callback deregistration, preview metadata removal, overlay refresh, and session reset can run more than once without crashing.
- `ESC`, document close, active document change, unavailable view, and tool switching all flow through the same cancellation path.
- Successful commits clear transient preview state after the model mutation finishes.
- Failed preview updates or failed commits clear transient state and leave no active callbacks behind.

## Preview, Commit, And Undo

- Preview updates stay in metadata and overlay state only and never open a FreeCAD transaction.
- Preview validation also stays metadata-only and evaluates a hypothetical component set in memory, without a full document sync.
- Place and drag commits use one document transaction around state mutation and full sync.
- The transaction boundary is: open transaction, mutate committed project state, run full sync, close transaction.
- If the commit path raises an exception, the transaction is aborted and the previous project state is restored before control returns to the UI.
- Preview errors block place and drag commit; warning-level preview feedback remains visible but does not create undo entries on its own.
- Template Import Stage A is an external template-generation workflow: it produces a YAML file and reloads the template registry, but it does not mutate the active project document and therefore does not create a FreeCAD undo step.

## Parameter Model

- Parameters are declared in template YAML, not hidden in code.
- Parameter presets are named parameter sets that templates can ship directly.
- Runtime parameter values are applied through the template and variant resolver path before project generation.
- Supported parameter effects in the current implementation are:
  - direct controller or layout value binding
  - component field switching, for example `library_ref`
  - generated component grids, for example pad matrices
- Project state stores resolved parameter values and their source in `meta.parameters`.
- Pure parameter editing in the Create panel is UI-only until the user runs `Create` or `Apply Parameters`.

## Component Property Resolution

- Component property editing follows the same separation as the rest of the workbench:
  - selection chooses the active component
  - library metadata defines which fields are shown
  - the property panel maps UI values into component updates
  - state services persist the updates
  - sync services choose between full rebuild and state-only refresh
- The current panel keeps generic placement and metadata fields stable across all component families and adds a type-specific subsection for fader, display, encoder, and pad-like components.

## Selection Model

- Selection is now persisted as:
  - `meta.selection` for the primary selected component id
  - `meta.selected_ids` for the full ordered selection set
- Compatibility is preserved because older single-selection flows still read `meta.selection`.
- New APIs build on top of that model:
  - `get_selected_component_ids()`
  - `set_selected_component_ids(...)`
  - `clear_selection()`
  - `toggle_selection(...)`

## Project Parameter Roundtrip

- Project parameter persistence is intentionally split:
  - `meta.template_id` and `meta.variant_id` link the document back to its source schema
  - `meta.parameters` stores the effective project-scoped parameter values, their source, and the active preset id
  - `meta.overrides` remains a compatibility and preset payload container
- Reopening a document prefers `meta.parameters`.
- If `meta.parameters` is missing but legacy parameter overrides exist, the UI falls back to those values and marks the project as `legacy_fallback`.
- Regeneration always runs through the normal template or variant resolver path instead of mutating builder inputs directly from UI widgets.
