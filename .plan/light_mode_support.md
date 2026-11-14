# Plan: Light Mode Support for `usfds-web`

## 1. Current State Analysis (Facts)
- **Codebase Footprint (`usfds-web/src`)**:
	- `dark-*` utilities (`bg-dark-950/900/850/800/700`, `border-dark-800/700/600`, `divide-dark-800/850`): **768 occurrences** across layout, modals, cards, tables, and workspaces.
	- `slate-*` utilities (`text-slate-100..500`, `border-slate-800/700`, `bg-slate-800`): **1,269 occurrences**.
	- Accent pastel text utilities (`text-emerald-300/400`, `text-amber-300/400`, `text-rose-300/400`, `text-brand-300/400`, `text-purple-300/400`): **~600 occurrences** designed for dark backgrounds (fail WCAG AA 4.5:1 contrast on light backgrounds).
	- `text-white` utilities: **132 occurrences** (~85 on solid colored buttons like `bg-brand-600 text-white` which must stay white; ~47 on headings/table cells/tabs in `reports/*`, `rule/*`, `Button.tsx`, `ProjectManagementView.tsx` which become invisible on light surfaces).
	- Hardcoded hex colors in Charts & Canvas: **~50 occurrences** in `WorkbenchPanels.tsx`, `TrainingRunDetailView.tsx`, `EffectivenessTab.tsx`, `ExecutiveOverviewTab.tsx`, `TypologiesPatternsTab.tsx`, and `LineageCanvasView.tsx` (Recharts `Tooltip`, `CartesianGrid`, `XAxis`/`YAxis`, SVG strokes, radial-gradient canvas dots).
	- Global CSS (`src/index.css`): Hardcoded dark scrollbar (`#020617`, `#1e293b`) and `.focus-ring` (`#020617`).
- **Design System (`docs/design-system.md`)**:
	- Currently defines only Dark Mode tokens in Section 2 (`Primitive Tokens` -> `Semantic Tokens` -> `Component Tokens`).

## 2. Architectural Strategy (Minimal Footprint)
Instead of rewriting 2,000+ Tailwind class strings with `dark:*` variants across 70+ files, use **CSS Custom Property RGB Channels (`rgb(var(...) / <alpha-value>)`)** in `tailwind.config.js` and `src/index.css`:
1. **Tokenized Surface & Text Scale (`src/index.css` + `tailwind.config.js`)**:
	- Define RGB channel variables for `:root` (Dark default) and `html[data-theme="light"]` (Light mode):
		- `dark-950` (App canvas): `#020617` (Dark) $\leftrightarrow$ `#F8FAFC` (Light `slate-50`)
		- `dark-900` (Primary surface / Topbar / Sidebar / Card): `#0B1120` (Dark) $\leftrightarrow$ `#FFFFFF` (Light pure white)
		- `dark-850` (Subtle surface / Header / Input bg): `#0F172A` (Dark) $\leftrightarrow$ `#F1F5F9` (Light `slate-100`)
		- `dark-800` (Elevated / Hover / Neutral badge): `#1E293B` (Dark) $\leftrightarrow$ `#E2E8F0` (Light `slate-200`)
		- `dark-750` / `dark-700` (Primary border): `#334155` (Dark) $\leftrightarrow$ `#CBD5E1` (Light `slate-300`)
		- `dark-600` (Strong border / DAG edge): `#475569` (Dark) $\leftrightarrow$ `#94A3B8` (Light `slate-400`)
	- Invert `slate` foreground/border variables under `html[data-theme="light"]`:
		- `slate-50` / `slate-100` (Primary text): `#0F172A` (`slate-900`)
		- `slate-200` / `slate-300` (Body / Secondary text): `#1E293B` / `#334155` (`slate-800` / `slate-700`)
		- `slate-400` (Label / Muted text): `#475569` (`slate-600` — WCAG AA > 7:1 on white)
		- `slate-500` (Placeholder / SubLabel): `#64748B` (`slate-500` — WCAG AA 4.6:1 on white)
		- `slate-700` / `slate-800` (Used as borders/dividers in 95 places): `#CBD5E1` / `#E2E8F0`
	- Remap pastel status text shades (`300`/`400` of `emerald`, `amber`, `rose`, `red`, `brand`, `purple`, `sky`, `cyan`) under `html[data-theme="light"]` to darker high-contrast shades (`600`/`700`) so badges and status indicators remain legible and WCAG AA compliant without touching component files.
2. **Theme State & Provider (`src/hooks/useTheme.tsx`)**:
	- Create `ThemeProvider` and `useTheme()` hook supporting 2 modes (`'dark' | 'light'`, defaulting to `'dark'`), persisted in `localStorage` (`usfds_theme`), syncing `data-theme` and class on `document.documentElement`.
	- Expose computed chart/canvas theme tokens (`gridStroke`, `axisTick`, `tooltipBg`, `tooltipBorder`, `tooltipText`, `canvasDot`, `edgeStroke`) from `useTheme()` for Recharts and SVG views.
3. **Theme Toggle UI**:
	- Add a Sun/Moon toggle button in `Topbar.tsx` (Workspace shell) and `ProjectManagementView.tsx` (Standalone Project Portal header).
4. **Surgical Component Fixes**:
	- Convert non-button `text-white` headings, metric values, and hover text (~47 occurrences in `reports/*`, `RuleDryRunWorkspace.tsx`, `Button.tsx`, `InvestigationModule.tsx`, `InsightReportModule.tsx`, `WorkbenchResolutionColumn.tsx`, `ProjectManagementView.tsx`) to `text-slate-100` (which resolves to `#F1F5F9` in Dark Mode and `#0F172A` in Light Mode). Keep `text-white` on solid fills (`bg-brand-500/600`, `bg-emerald-600`, `bg-rose-600`, avatar badge).
	- Replace hardcoded hex values in Recharts & SVG components (`WorkbenchPanels.tsx`, `TrainingRunDetailView.tsx`, `EffectivenessTab.tsx`, `ExecutiveOverviewTab.tsx`, `TypologiesPatternsTab.tsx`, `LineageCanvasView.tsx`) with theme-aware tokens from `useTheme()` or CSS variables.
5. **Documentation (`docs/design-system.md`)**:
	- Upon user approval, update `docs/design-system.md` Section 2.2 with Light Mode Semantic Tokens and append `[26-11-12]`.

## 3. Verification & Success Criteria
- [x] `ThemeProvider` persists theme selection in `localStorage` and updates `<html data-theme="...">` without page reload.
- [x] Toggle button works in both Project Portal (`/projects`) and Workspace Shell (`Topbar`).
- [x] All cards, tables, modals, drawers, badges, and buttons render with WCAG AA contrast ($\ge 4.5:1$) in both Dark Mode and Light Mode.
- [x] Recharts tooltips/axes/grids and `LineageCanvasView` DAG background/edges adapt dynamically when switching themes.
- [x] Solid buttons (`bg-brand-500/600`, etc.) retain white text (`text-white`) in both modes.
- [x] Unit test tripwire verifies theme toggling and persistence; `npm run build` (`tsc -b && vite build`) passes with zero errors.

