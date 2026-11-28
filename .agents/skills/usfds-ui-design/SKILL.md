---
name: usfds-ui-design
description: Designing, shaping, hardening, clarifying, auditing, and polishing usfds-web screens and components in Operate mode — aligned with docs/design-system.md (Dark/Light tokens), Vietnamese UI copy, and usfds-frontend-change. Use when designing a new screen/flow, improving layout or UX copy, hardening data-dense views against extreme inputs/errors, or running a UI/a11y/theme/polish review on usfds-web. Replaces raw /chi-mode for this repository.
---

# USFDS UI/UX Design (Operate Mode)

## 0. Authority & Out-of-Scope Guardrails
- **Sources of truth:** `docs/design-system.md` (visual tokens, Dark/Light `--tw-*` RGB variables, `useTheme()` chart tokens, typography, WCAG 2.1 AA) and `usfds-frontend-change` (`Component → Hook → API`, react-query, Vietnamese UI copy, Vitest + MSW, append-only hot spots).
- **Workflow order stays unchanged:** `usfds-plan` → `usfds-task-workflow` (test-first) → `usfds-review`. Never edit `docs/` without explicit user approval.
- **Explicitly out of scope (do NOT run in USFDS):**
  - Never invoke `/chi-mode` CLI (`scripts/chi`), and never create `PRODUCT.md`, `DESIGN.md`, or `.chi/`.
  - Never run `init`, `document`, `live`, `generate`, `hooks`, `doctor`, `promote`, `adopt`, `extract`, `onboard`, `adapt`, `craft`, `bolder`, `quieter`, `colorize`, `typeset`, `animate`, `delight`, `overdrive`, or visual-world workshops (`new-work`).
  - No RTL/Arabic i18n, fluid `clamp()` typography, or marketing image/CDN optimization.

---

## 1. Operate-Mode Craft Floor (Always Active)
- **Posture:** `Operate` mode for Data Scientists and Fraud Analysts — predictability, scanability, and fast task completion outrank novelty.
- **Full state matrix:** every interactive control and data surface covers `default`, `hover`, `focus`, `active`, `disabled`, `loading`, `error`, and `empty`.
- **Theme & contrast:** body/placeholder contrast ≥ 4.5:1 and large text ≥ 3:1 in both Dark (`:root`) and Light (`html[data-theme="light"]`). Never use `text-white` on cards/panels (use `text-slate-100` / `text-slate-200`; reserve `text-white` for solid colored buttons/pills). Never hardcode hex colors in Recharts, Cytoscape, or custom SVG — read `chartTokens` from `useTheme()`.
- **Dual-encoding & icons:** every status (`PASSED`, `WARNING`, `FAILED`, `fraud`, `legit`, `alarm`) pairs color + Lucide SVG icon + Vietnamese label. Never use emoji or Unicode glyphs as UI icons.
- **Typography & motion:** use the fixed Tailwind type scale from `docs/design-system.md` (never fluid `clamp()`). Use `.tabular-nums` + `font-mono` strictly for IDs, UUIDs, checksums, canonical column names, and numeric/financial metrics (never as decoration). Keep transitions `150–250ms` for state feedback only, respecting `prefers-reduced-motion`.
- **Reuse & refusals:**
  - Reuse shared primitives (`Card`, `Button`, `Badge`, `EmptyState`, `PageHeader`, `WorkspaceStepper`, `InspectorDrawer`, `OwnerBadge`, `Spinner`) before creating one-offs.
  - Preserve established `docs/design-system.md` tokens (including `shadow-glow-*`).
  - Refuse: nested cards, eyebrow/kicker labels above headings, decorative `border-left` > 1px callouts, and modals when inline UI or `InspectorDrawer` suffices.

---

## 2. Phase 1: Shape, Layout & Distill (Before `usfds-plan`)
Run on new or significantly reworked screens before writing `.plan/<task>.md`.
- **Shape (concise UX brief, no code):** settle (1) primary user task & decision, (2) essential vs. secondary data, (3) required states (`loading`, `empty`, `error`, `permission/RBAC`, `polling`, `overflow`), and (4) scope boundaries. Ask at most 1 focused question round only for genuine product ambiguities — never ask for CSS values or aesthetic themes.
- **Layout (structure & hierarchy):**
  - Apply the squint test: primary reading/task path must be obvious at a glance.
  - Group related controls by proximity (`gap` and the 4px spacing scale) instead of wrapping every group in a card.
  - Keep responsive behavior structural: collapsible sidebar, sticky first table column, horizontal scroll container, `min-width: 0`.
- **Distill (cut clutter):** when a screen or drawer accumulates too many controls, trim redundant actions and move secondary configuration or diagnostics into progressive disclosure (`InspectorDrawer`, tabs, or collapsibles).

---

## 3. Phase 2: Harden & Clarify (During `usfds-frontend-change`)

### Harden (data-dense desktop/web)
- **Extreme inputs:** handle long dataset/model names, UUIDs, and SHA-256 checksums (`truncate` + full value on hover/copy, or `break-all`), large financial figures (`.tabular-nums` + `src/utils/formatters.ts`), `0`/`null`/`NaN`/`Infinity` guards, and 1,000+ row tables (virtual scrolling or pagination).
- **Containment:** add `min-width: 0` (and `min-height: 0` in nested grids) on flex/grid children so tables, JSON panels, and charts never overflow their container.
- **Error & async resilience:** handle `ApiClientError` (`400`, `401`, `403`, `404`, `409`, `500`), network failures, partial batch loads (`Promise.allSettled`), and terminal stop conditions for `refetchInterval` polling.

### Clarify (Vietnamese UX copy)
- **Actions:** use specific verb + object (*"Xóa bộ dữ liệu"*, *"Chạy huấn luyện"*), never vague *"OK"*, *"Xác nhận"*, or *"Gửi"*.
- **Destructive confirmations:** name both the target object and the consequence in the prompt message and the action button.
- **Errors:** state **(1) what failed**, **(2) why (when known)**, and **(3) recovery action** — never raw stack traces or internal codes as the primary message.
- **Empty states:** distinguish *first use*, *no filter matches*, *missing permission*, and *load failure*, always providing a concrete next step.
- **Terminology:** keep domain English terms consistent with `docs/design-system.md` (`Precision`, `Recall`, `Model`, `Dataset`, `Rule`, `Lineage`).

---

## 4. Phase 3: UI Audit, Targeted Perf & Polish (Before `usfds-review`)

### 4-Dimension Audit
Score `0–4` per dimension on full audits, or run as a checklist on changed files:
1. **Accessibility (WCAG 2.1 AA):** Dark & Light contrast, semantic HTML (`<button>` not clickable `<div>`), `.focus-ring` (`:focus-visible`), logical `Tab` order, form `<label>` + error announcement, table `caption`/`scope="col"`, `role="progressbar"` + `aria-valuenow`/`aria-valuemin`/`aria-valuemax`, `prefers-reduced-motion`.
2. **Theming (Dark + Light):** zero hardcoded hex or non-adaptive colors (`text-white` on cards/panels), `chartTokens` from `useTheme()` in Recharts/Cytoscape, clear borders/hover/selection under `html[data-theme="light"]`.
3. **Runtime Performance (only when slow/dense — measure first):** eliminate unnecessary re-renders on large tables/charts, avoid animating layout properties, avoid broad `will-change`, use virtual scrolling/pagination for large row sets, avoid heavy unused imports.
4. **UX Heuristics & Cognitive Load (distilled Nielsen 10):** visibility of async job status, domain terminology consistency, user control (cancel/back/reset filters), cross-module consistency, error prevention, recognition over recall; flag any view with > 4 competing primary options.

### Polish Triage Order
Refinement only — never concealed redesign, and stay strictly inside plan scope:
1. Blocked user tasks, misleading states, broken Light/Dark contrast, a11y blockers.
2. Missing `loading` / `empty` / `error` / `disabled` / `permission` states.
3. Drift from shared primitives (`Card`, `Button`, `Badge`, `EmptyState`, `PageHeader`, `InspectorDrawer`) or neighboring modules.
4. Spacing rhythm, optical alignment, overflow clipping, and copy consistency.
5. Remove dead CSS, unused imports, and debug logs; verify in `usfds-web` with `npm test && npm run build && npm run lint`.
