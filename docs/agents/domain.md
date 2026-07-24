# Domain Documentation Configuration

## Layout Type
Multi-context

## Context Structure
This repository uses a multi-context layout with separate domain documentation for different components:

- Root `CONTEXT-MAP.md` - Maps all available contexts in the repository
- Component-specific `CONTEXT.md` files - Domain language for each major component

## Reading Rules
Skills that read domain documentation should:

1. First read `CONTEXT-MAP.md` at the repository root
2. Identify the relevant context(s) for the current task
3. Read the appropriate `CONTEXT.md` file(s) for those contexts
4. Look for ADRs in `docs/adr/` directories within each context

## ADR Locations
Architectural Decision Records may be located in:
- `docs/adr/` at the repository root (cross-cutting decisions)
- Component-specific `docs/adr/` directories (component-specific decisions)

## Known Contexts
Based on repository structure, potential contexts include:
- `pipeline/` - Core pipeline processing logic
- `ui/` - React frontend application  
- `api/` - Express API backend
- `api2/` - Python API backend
- `mcp/` - MCP server implementation

The `CONTEXT-MAP.md` should be updated to reflect the actual available contexts and their purposes.
