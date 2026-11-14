---
name: usfds-frontend-change
description: How to change the USFDS React web app (usfds-web) — layering (component → hook → api client), the hooks layer that owns state and data fetching, react-query, design-system tokens, Vietnamese UI copy, and vitest + MSW tests — while avoiding conflicts in shared shell files. Use when adding or changing screens, components, hooks, API clients or UI text in usfds-web.
---

# USFDS frontend change

Read first: `docs/design-system.md` (tokens, layout, accessibility) and the feature's `docs/features/**/user-flow-and-ui-design.md` if it exists.

## Layers (dependencies point downward only)

```
Component (src/components/modules/<module>/)   renders UI, handles user events, no fetching, no business state
   ↓ calls
Hook (src/hooks/use<Domain><Thing>.ts)         owns state, data fetching, mutations, derived data, polling
   ↓ calls
API client (src/api/<domain>Api.ts)            HTTP calls only; returns typed data
```
In new and changed code, a component never imports from `src/api/` directly, and a hook never renders JSX (except context providers such as `useProjects.tsx` / `useTheme.tsx`). Many existing components still call the API inline (ISS-032); migrate one only when your task already changes it.

## Layout
| What | Where |
|---|---|
| Feature UI | `src/components/modules/<module>/` (`data_management`, `detection`, `investigation`, `model`, `project_management`, `reports`, `rule`) |
| Hooks (state + data logic) | `src/hooks/use<Domain><Thing>.ts`, flat folder, re-exported from `src/hooks/index.ts` |
| Route wrappers | `src/pages/*Page.tsx` (nested routes per module) |
| API calls | `src/api/<domain>Api.ts` using the singleton `apiClient` (`src/api/client.ts`) |
| Types | `src/types/<domain>.ts` |
| Shared UI | `src/components/common/*`, `src/components/layout/*` (`PageHeader`, `Sidebar`, `Topbar`) |
| Tests | `*.test.tsx` / `*.test.ts` next to the code; helpers in `src/test/` |

## Hooks layer (keeps components small)
Move logic out of a component into a hook as soon as the component has any of: a `useQuery` / `useMutation`, more than two related `useState`s, a `useEffect` that fetches or polls, form or wizard state, or derived data (filters, sorting, grouping, totals). The component keeps only JSX and event wiring.

- **Naming and shape:** `use<Domain><Thing>` (e.g. `useDatasetList`, `useTrainingRunDetail`). One hook per screen concern; compose small hooks inside a larger one rather than writing one giant hook. Return a stable object: `{ data, isLoading, error, ...actions }`. Actions are named for intent (`startTraining`, `activateModel`), not for HTTP.
- **Queries and cache keys:** each domain exports its query-key constant or factory from its hook file (`DATASETS_QUERY_KEY` in `useDatasetList.ts`). Mutations invalidate affected keys by importing those constants. Never write key arrays inline in components.
- **Polling** (`PENDING` / `RUNNING` jobs): `refetchInterval` inside the hook, stopping when the status is terminal. Components never use `setInterval`.
- **Errors and messages:** the hook turns failures into a state the component can show (`error`, or `errorMessage` in Vietnamese). It does not call `alert` or show toasts itself unless the screen already has a shared notification hook.
- **IDs and identity:** never hardcode project IDs, user IDs or sample paths inside a hook. `useDatasetImport` has `defaultProjectId = '9a0a…'` and sample file paths: do not copy this. The project comes from `useProjects()`; the user comes from the auth context once RBAC lands.
- **Pure derivations** (sorting, grouping, formatting) go in `src/utils/*` as plain functions so they can be unit-tested without React; the hook calls them.
- **Barrel:** append the new export to `src/hooks/index.ts` (hot spot, one line).
- **Existing components that still fetch inline** (model, rule and parts of detection views): when your task changes such a component anyway, extract its fetching and state into a hook as part of the change. Do not refactor components the task does not touch.

## Rules
- **Shared shell files are hot spots** (append-only, one line per change): `src/App.tsx` (routes), `src/components/layout/Sidebar.tsx` (nav), `src/types/navigation.ts`, `src/api/client.ts`, and the barrel `index.ts` files. Do not restructure them inside a feature task.
- **Data fetching:** only in hooks (see Hooks layer). Use react-query (`useQuery` / `useMutation`) for new code. Use `refetchInterval` for polling, not `setInterval`. `apiClient` methods currently return `{success:false, error}` instead of throwing (ISS-028). Inside a `queryFn`, throw on `!res.success` (see the `unwrap` helpers in `investigationApi.ts`) so react-query enters the error state.
- **UI text is Vietnamese** (ISS-005). Every new or changed user-facing string, label, tooltip, toast and empty state is in Vietnamese. Keep technical terms commonly used in English (e.g. `Precision`, `Recall`, `Model`, `Dataset`) where the design system does. Format numbers and dates with `src/utils/formatters.ts`.
- **Design system:** use the semantic tokens and Tailwind classes from `docs/design-system.md`. They support both dark and light themes, so do not hardcode hex colors; charts take colors from `useTheme()`. Use Lucide icons, not emoji. Never signal state with color alone. Respect `prefers-reduced-motion`.
- **No UI for secrets or API keys.** Configuration comes from `.env` (`usfds-web/.env.example`).
- **Style:** tabs, semicolons, 1TBS for new code; follow the existing file's style when editing. No `any` in new code; avoid `console.log`.

## Tests (skill `usfds-testing`, Web section)
- Every new data-fetching screen has a test for its loaded state and its error state, using MSW handlers for every request it makes. Test through the component with `renderWithProviders` when the behavior is what the user sees.
- Hooks with real logic (state machines, polling, wizard steps, cache invalidation after a mutation) get their own test with `renderHook` from Testing Library, wrapped in a `QueryClientProvider` with `retry: false` (no shared helper exists yet; add `renderHookWithProviders` to `src/test/` when the first hook test needs it). Assert the returned state and actions, not implementation details.
- Pure helpers (`src/utils/*`) get plain vitest unit tests.

## Verify
In `usfds-web`: `npm test && npm run build && npm run lint`, all exit 0 (lint warnings that already existed are acceptable). `./scripts/test.sh web` runs `npm test`.
