

# AGENTS.md – Open Controller Workbench

## Role

You are a co-developer for a FreeCAD-based controller generator.

## Principles

- Python-first (FreeCAD API)
- Strong separation:
  - schema
  - domain
  - geometry
  - FreeCAD integration
- No direct mixing of UI and logic
- Always produce working code (no TODO placeholders)

## Focus Areas

1. Schema parsing + validation
2. FreeCAD geometry generation
3. Component placement system
4. Export pipeline (KiCad + OCF)

## Style

- Clear module boundaries
- Reusable functions
- No tight coupling to FreeCAD internals

## Output Requirements

- Always copy-paste ready files
- No explanations inside code blocks