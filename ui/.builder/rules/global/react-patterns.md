# React Component Patterns

## Component Rules

- Function components only — no class components
- Type props with an explicit `interface` (or `type` for unions/intersections)
- Avoid `React.FC` — declare props inline:

```tsx
interface KpiWidgetProps {
  title: string;
  value: number;
  onSelect?: (id: string) => void;
}

export function KpiWidget({ title, value, onSelect }: KpiWidgetProps) {
  // ...
}
```

- Destructure props in the signature, not the body
- Prefer early returns over nested ternaries
- Keep JSX nesting ≤ 3 levels — extract sub-components otherwise

## Hooks

- Custom hooks must start with `use` and return a stable shape
- Extract logic into hooks when it has its own state, effects, or is reused
- Type hook return values explicitly when not trivially inferred
- Hook order: state → derived → effects → callbacks → return
- Follow the rules of hooks — no conditional or looped hook calls

## State Management

- Local UI state → `useState` / `useReducer`
- Cross-component shared state → Redux Toolkit slice
- Server data → async thunks (or RTK Query if introduced later)
- Use React Context only for low-frequency values (theme, auth user, feature flags) — never for high-frequency updates
- Lift state only as far as needed; do not promote everything to Redux

## Performance

- Don't reach for `memo`/`useMemo`/`useCallback` by default — only when profiling shows benefit or when passing referentially-stable callbacks to memoized children
- Always provide `key` for list items — never use array index when items can reorder
- Avoid creating object/array literals inline as props to memoized components
- Lazy-load heavy or rarely-visited routes via `React.lazy` + `Suspense`

## Effects

- Treat `useEffect` as a synchronization primitive, not a lifecycle hook
- Always include the full dependency array — never disable the lint rule
- Clean up subscriptions, timers, and aborts in the return function
- Prefer event handlers over effects for user-driven side effects

## Forms

- Use `react-hook-form` + `zod` (`@hookform/resolvers`)
- Centralize schemas; infer TS types via `z.infer<typeof Schema>`
- Disable submit buttons while submitting; surface errors via toast or inline

## Accessibility

- Use semantic HTML (`button`, `nav`, `main`, `header`)
- Every interactive element must be keyboard-reachable
- Provide `aria-label` for icon-only buttons
- Maintain visible focus styles
- Associate form controls with `<label htmlFor>`

## Styling

- TailwindCSS utility classes are the default styling layer
- Combine conditional classes with `cn()` from `@/lib/utils`
- Theme tokens live in `src/global.css` and `tailwind.config.ts` — never hardcode hex colors
- Use the `components/ui/*` primitives (Radix-based) before building custom ones

## Assets

- Centralize SVG/icon exports in `src/components/icons/index.tsx`
- Avoid duplicated inline SVG markup
- Prefer `lucide-react` icons for standard glyphs

## App Structure

`App.tsx` should remain minimal and contain only:

- Providers (Redux, Router, Toaster, Tooltip, etc.)
- Layout shell
- Route mounting (`<AppRoutes />`)

No data fetching, no business logic, no inline route definitions.
