# Testing Standards

## Tooling

- **Runner**: Vitest (`npm test`)
- **DOM**: `@testing-library/react` + `@testing-library/jest-dom` (when component tests are added)
- **Mocks**: `vi.fn()`, `vi.mock()` from Vitest

## File Conventions

- Co-locate tests with the unit under test
- Naming: `*.spec.ts` for utilities, `*.spec.tsx` for components
- One `describe` block per module; nested `describe` per function/behavior

## What to Test

Priority order:

1. Pure utilities and selectors (`lib/`, slice selectors, formatters)
2. Reducers and thunks (state transitions, error paths)
3. Custom hooks (with `renderHook`)
4. Components with branching logic or accessibility-critical behavior

Do NOT test:

- Third-party libraries
- Trivial pass-through components
- Implementation details (internal state, private helpers)

## Component Tests

- Query by accessible role/label, not by `data-testid` (use `testid` only as a last resort)
- Assert from the user's perspective \u2014 visible text, aria attributes, navigation
- Wrap with required providers (Router, Redux store) via a `renderWithProviders` helper

## Async

- Use `findBy*` queries or `waitFor` \u2014 never arbitrary `setTimeout` waits
- Mock axios instances, not `axios` directly, to respect the project's interceptors

## Coverage

- Aim for meaningful coverage of business logic; do not chase a percentage
- Every bug fix should land with a regression test

## Validation

```bash
npm test
```

Expected: all tests pass, no `.only` or `.skip` left in committed code.
