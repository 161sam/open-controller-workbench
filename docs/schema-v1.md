
# Schema v1

## Ziel

Austauschformat für Hardware-Design.

## Beispiel

```yaml
schema_version: "1.0.0"

controller:
  id: "test"
  dimensions_mm:
    width: 120
    depth: 80

components:
  - id: "enc1"
    type: "encoder"
    library_ref: "alpha.rv112ff"
    position_mm:
      x: 30
      y: 40
````

## Struktur

### controller

* id
* dimensions_mm
* surface

### components

* id
* type
* library_ref
* position

## Prinzip

library_ref → Mechanik → Resolver → Geometry

## Validierung

* controller vorhanden
* Maße vorhanden
* Komponenten gültig
