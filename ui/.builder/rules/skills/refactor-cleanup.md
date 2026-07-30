# Refactor & Cleanup Rules

## Cleanup Checklist

- Remove dead code (unreachable branches, commented-out blocks)
- Remove unused files, exports, imports, variables, parameters
- Remove unused npm dependencies (verify with `npm ls <pkg>`)
- Remove leftover `console.log` / debug statements
- Replace `TODO`s that no longer apply
- Delete empty folders left behind after moves

## Refactoring Principles

- Preserve behavior — refactors must not change observable output
- Make one kind of change per commit (rename, extract, inline) — don't mix
- Simplify oversized components by extracting:
  1. Sub-components for repeated/independent JSX
  2. Hooks for stateful logic
  3. Utilities for pure transforms
- Reduce prop drilling via Redux selectors or scoped context
- Replace duplicated literals with named constants
- Replace duplicated logic only after the 3rd occurrence

## Safety

- Run tests before and after each refactor — both must pass
- Use `vscode_renameSymbol` (or IDE rename) instead of text-replace for symbols
- Update path aliases — never leave broken `../../../` imports
- Don't bypass type errors with `any`, `as`, or `!` to make a refactor compile

## Validation

After every refactor run:

```bash
npm run typecheck
npm test
npm run build
```

Expected:

- 0 TypeScript errors
- All tests pass
- Successful production build
- No new Prettier diffs (run `npm run format.fix`)
