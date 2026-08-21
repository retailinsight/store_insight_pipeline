# Code Quality Standards

## Core Principles

- Prefer maintainability over quick implementations
- Keep components small, focused, and reusable
- One responsibility per file/module
- Extract reusable utilities and custom hooks
- Prefer composition over deeply nested logic or inheritance
- Remove dead code, unused imports, and unused dependencies
- Avoid premature/unnecessary abstractions (apply YAGNI)
- Follow DRY, but only after a pattern repeats 3+ times

## Component Size Guidelines

- Aim for components under ~200 lines
- Split when JSX nesting exceeds ~3 levels
- Extract sub-components when a block is reused or has independent state
- Move data shaping/derivations into hooks or selectors, not the JSX tree

## Refactor Rules

- Simplify oversized components
- Move business logic out of UI components into hooks/utilities/thunks
- Reuse shared utilities (`src/lib`, `src/utils`)
- Reduce prop drilling — prefer Redux selectors or local context
- Centralize repeated formatting logic in `src/lib/formatting.ts`
- Co-locate types with the code they describe

## Imports

- Use path aliases (`@/*`, `@shared/*`) — never deep relative paths like `../../../`
- Group: external → aliased internal → relative → styles
- Prefer named exports; default-export only top-level pages/route components when required

## Error Handling

- Validate at boundaries (API responses, form input, route params)
- Use Zod schemas for runtime validation of untrusted input
- Surface user-facing errors via the toast system, not `alert()` or `console`
- Never swallow errors silently in `catch` blocks

## Verification

Before completing a task, run all of:

```bash
npm run typecheck
npm test
npm run build
npm run format.fix
```

Expected:

- 0 TypeScript errors
- All tests pass
- Successful production build
- No unused imports/variables/files
