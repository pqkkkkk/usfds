# UI/UX Design Foundation
<!-- [26-11-28] English translation (content unchanged). -->

This document defines the **Design System Foundations**, the **Global Layout Architecture**, the three-layer design token architecture, and the **Accessibility & Interaction Guidelines** for the whole **USFDS** (Unified System for Fraud Detection & Scoring).

> Based on the Fintech / data-dense design standards of the `ui-ux-pro-max` toolkit and the `design-system` Three-Layer Token Architecture.
>
> UI copy is Vietnamese (skill `usfds-frontend-change`); this document is English.

---

## 1. Design Philosophy & Visual Direction

### 1.1. Design Profile
- **Primary style:** **Dark Mode (OLED / Midnight Slate)** with **Emerald/Blue Accents**.
- **Usage context:** A complex financial analytics and fraud detection platform; users (Data Scientist, Fraud Analyst) work for hours with large data tables, confusion matrices, and lineage trees (DAG).
- **Design Dials:**
  - **Variance (6/10 - Balanced / Modern):** Balances the trustworthiness of a financial enterprise (Enterprise Gateway) with a modern AI-tech interface.
  - **Density (8/10 - Dense / Dashboard):** High data density, compact spacing (8px/12px padding), minimal meaningless whitespace, space optimized for tables and charts.
  - **Motion (4/10 - Subtle Micro-interactions):** Light micro-motion (150ms - 250ms); never overuse effects that slow the user down; respect `prefers-reduced-motion`.

### 1.2. Core Design Principles
1. **High Contrast & Low Eye-Strain:** Deep dark backgrounds (`#020617` / `#0B0F19`) protect eyesight and make fraud anomalies stand out.
2. **Dual-Encoding for Safety:** Never use color as the only status signal (color-blindness). Every important status (`PASSED`, `WARNING`, `FAILED`) always comes with a standard SVG icon and a text label.
3. **No Emoji as UI Icons:** All UI icons use a standard vector SVG library (`Lucide-React` or `Heroicons`), with `aria-hidden="true"` or a screen-reader label.
4. **Predictable & Traceable:** Every background task gives clear, non-blocking progress feedback; every data / model version links to an immutable lineage tree.

---

## 2. Three-Layer Token Architecture

Architecture: `Primitive Tokens` $\to$ `Semantic Tokens` $\to$ `Component Tokens`.

```
┌────────────────────────────────────────────────────────┐
│  Component Tokens (Layer 3: per-component variables)   │
│  --stepper-node-size, --table-row-height, --dag-border │
├────────────────────────────────────────────────────────┤
│  Semantic Tokens (Layer 2: business meaning & theme)   │
│  --color-background, --color-surface, --color-accent   │
├────────────────────────────────────────────────────────┤
│  Primitive Tokens (Layer 1: raw physical values)       │
│  --color-slate-900, --color-blue-500, --space-4        │
└────────────────────────────────────────────────────────┘
```

### 2.1. Layer 1: Primitive Tokens

```css
:root {
  /* Slate Scale (background and text) */
  --primitives-slate-950: #020617;
  --primitives-slate-900: #0F172A;
  --primitives-slate-850: #111827;
  --primitives-slate-800: #1E293B;
  --primitives-slate-700: #334155;
  --primitives-slate-600: #475569;
  --primitives-slate-500: #64748B;
  --primitives-slate-400: #94A3B8;
  --primitives-slate-300: #CBD5E1;
  --primitives-slate-100: #F1F5F9;
  --primitives-slate-50:  #F8FAFC;

  /* Accent & Functional Colors */
  --primitives-blue-500:    #3B82F6;
  --primitives-blue-600:    #2563EB;
  --primitives-emerald-400: #34D399;
  --primitives-emerald-500: #10B981;
  --primitives-amber-400:   #FBBF24;
  --primitives-amber-500:   #F59E0B;
  --primitives-red-500:     #EF4444;
  --primitives-red-600:     #DC2626;
  --primitives-purple-400:  #A78BFA;
  --primitives-purple-500:  #8B5CF6;

  /* 4px Base Spacing Scale */
  --space-0-5: 0.125rem; /* 2px */
  --space-1:   0.25rem;  /* 4px */
  --space-1-5: 0.375rem; /* 6px */
  --space-2:   0.5rem;   /* 8px */
  --space-3:   0.75rem;  /* 12px */
  --space-4:   1rem;     /* 16px */
  --space-5:   1.25rem;  /* 20px */
  --space-6:   1.5rem;   /* 24px */
  --space-8:   2rem;     /* 32px */
  --space-10:  2.5rem;   /* 40px */
  --space-12:  3rem;     /* 48px */

  /* Border Radii */
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* Elevation Shadows (Dark-optimized) */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -2px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.6);
  --shadow-glow-blue: 0 0 15px rgba(59, 130, 246, 0.25);
  --shadow-glow-green: 0 0 15px rgba(34, 197, 94, 0.25);

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

### 2.2. Layer 2: Semantic Tokens (business meaning & theme)

```css
:root {
  /* Surface & Background */
  --color-background:         var(--primitives-slate-950); /* #020617 - OLED Black */
  --color-surface:            var(--primitives-slate-900); /* #0F172A - Panel & Card */
  --color-surface-elevated:   var(--primitives-slate-800); /* #1E293B - Modal, Dropdown */
  --color-surface-hover:      rgba(255, 255, 255, 0.04);
  
  /* Borders */
  --color-border:             var(--primitives-slate-700); /* #334155 */
  --color-border-subtle:      rgba(255, 255, 255, 0.08);
  --color-border-focus:       var(--primitives-blue-500);

  /* Typography / Foreground */
  --color-text-primary:       var(--primitives-slate-50);  /* #F8FAFC - Headings, figures */
  --color-text-secondary:     var(--primitives-slate-400); /* #94A3B8 - Labels, descriptions */
  --color-text-muted:         var(--primitives-slate-500); /* #64748B - Placeholder */
  --color-text-inverse:       var(--primitives-slate-950);

  /* Brand Accents & Interactive */
  --color-primary:            var(--primitives-blue-500);  /* #3B82F6 - Primary Button / Stepper */
  --color-primary-hover:      var(--primitives-blue-600);
  --color-accent:             var(--primitives-emerald-500);/* #10B981 - Success / Run Action */
  
  /* Status Feedback (WCAG AA Compliant) */
  --color-success:            var(--primitives-emerald-400); /* #34D399 */
  --color-success-bg:         rgba(16, 185, 129, 0.12);
  --color-warning:            var(--primitives-amber-400);   /* #FBBF24 */
  --color-warning-bg:         rgba(245, 158, 11, 0.12);
  --color-danger:             var(--primitives-red-500);     /* #EF4444 */
  --color-danger-bg:          rgba(239, 68, 68, 0.12);

  /* Pipeline Stage Tokens (FDS data lifecycle identification) */
  --stage-raw-color:          var(--primitives-blue-500);
  --stage-raw-bg:             rgba(59, 130, 246, 0.12);
  --stage-mapped-color:       var(--primitives-emerald-400);
  --stage-mapped-bg:          rgba(16, 185, 129, 0.12);
  --stage-preprocessed-color: var(--primitives-purple-400);
  --stage-preprocessed-bg:    rgba(139, 92, 246, 0.12);
  --stage-trained-color:      var(--primitives-amber-400);
  --stage-trained-bg:         rgba(245, 158, 11, 0.12);

  /* Focus Indicator Ring */
  --focus-ring: 0 0 0 2px var(--color-background), 0 0 0 4px var(--color-primary);
}

/* [26-11-12] Light Mode Semantic Overrides */
html[data-theme="light"] {
  --color-background:         var(--primitives-slate-50);  /* #F8FAFC - App Canvas */
  --color-surface:            #FFFFFF;                     /* #FFFFFF - Panel & Card */
  --color-surface-elevated:   var(--primitives-slate-100); /* #F1F5F9 - Modal, Dropdown, Hover */
  --color-surface-hover:      rgba(15, 23, 42, 0.04);

  --color-border:             var(--primitives-slate-300); /* #CBD5E1 */
  --color-border-subtle:      rgba(15, 23, 42, 0.08);
  --color-border-focus:       var(--primitives-blue-600);

  --color-text-primary:       var(--primitives-slate-900); /* #0F172A - Headings, figures */
  --color-text-secondary:     var(--primitives-slate-600); /* #475569 - Labels, descriptions */
  --color-text-muted:         var(--primitives-slate-500); /* #64748B - Placeholder */
  --color-text-inverse:       #FFFFFF;

  --color-success:            #059669;                     /* Emerald-600 (WCAG AA on Light) */
  --color-warning:            #D97706;                     /* Amber-600 (WCAG AA on Light) */
  --color-danger:             var(--primitives-red-600);   /* #DC2626 */
}
```

---

### 2.3. Layer 3: Component Tokens

```css
:root {
  /* Layout Shell */
  --topbar-height:            56px;
  --sidebar-width:            240px;
  --sidebar-collapsed-width:  64px;
  --bottombar-height:         28px;

  /* Data Table */
  --table-header-height:      38px;
  --table-row-height:         42px;
  --table-row-hover-bg:       rgba(255, 255, 255, 0.03);
  --table-border-color:       var(--color-border-subtle);

  /* Workspace Stepper */
  --stepper-node-size:        28px;
  --stepper-track-thickness:  2px;

  /* DAG Lineage Canvas */
  --dag-canvas-bg:            #050811;
  --dag-node-min-width:       200px;
  --dag-node-radius:          var(--radius-lg);
  --dag-edge-stroke:          var(--primitives-slate-600);
  --dag-edge-active-stroke:   var(--color-primary);
}
```

---

## 3. Typography & Specialized Fonts

The system combines **2 complementary font families**:
1. **Interface & general text (UI copy):** `Inter`, `-apple-system`, `sans-serif`.
   - Excellent legibility at small sizes (11px - 13px); renders Vietnamese UTF-8 correctly.
2. **Financial figures, checksums, identifiers & schema (tabular code font):** `Fira Code` or `JetBrains Mono`.
   - **Mandatory:** `font-variant-numeric: tabular-nums;` so numbers align exactly in financial analysis tables.

### Type Scale

| Token | Size / Line-height | Weight | Usage |
| :--- | :--- | :--- | :--- |
| `text-display` | 24px / 32px | 700 (Bold) | Page title |
| `text-heading-lg`| 18px / 24px | 600 (Semi-bold) | Section title, modal header |
| `text-heading-md`| 15px / 20px | 600 (Semi-bold) | Card title, drawer inspector header |
| `text-body` | 13px / 18px | 400 (Regular) | Table content, descriptions, form text |
| `text-caption` | 11px / 16px | 500 (Medium) | Meta labels, tag badges, table headers (uppercase) |
| `text-code` | 12px / 16px | 500 (Mono) | UUID, SHA-256 checksum, canonical column names (`event_id`) |

---

## 4. Global Shell Architecture

```
+--------------------------------------------------------------------------------------------------------------------+
| TOPBAR (56px) - Fixed                                                                                              |
| [Shield Logo] USFDS | [Project Selector: "E-Commerce Fraud 2026" v] | [Omnisearch (Ctrl+K)] | [Worker: OK] [Noti] [DS]   |
+---------------+----------------------------------------------------------------------------------------------------+
| SIDEBAR       | MAIN VIEWPORT (scrolls independently)                                                              |
| (240px)       |                                                                                                    |
|               | [Breadcrumb / Page Action Toolbar]                                                                 |
| - Data Hub    |----------------------------------------------------------------------------------------------------|
| - Detection   |                                                                                                    |
| - Rules       |  WORKSPACE CONTENT                                                                                 |
| - Investigate |                                                                                                    |
| - Reports     |                                                                                                    |
|               |                                                                                                    |
| [Collapse <]  |                                                                                                    |
+---------------+----------------------------------------------------------------------------------------------------+
| BOTTOM STATUS BAR (28px) - Worker Engine: Healthy | Latency: 12ms | Storage: 4.2 GB / 50 GB | Active Jobs: 0           |
+--------------------------------------------------------------------------------------------------------------------+
```

### 4.1. Top Navigation Bar
- **Project Context Switcher:** Switches the working context between problems. All data below this bar is scoped to the selected project ID.
- **Global Omnisearch (`Ctrl + K` or `Cmd + K`):** Instant search for datasets, models, rules, or transaction IDs.
- **System Health Indicator:** Green / yellow / red dot for the background engine (`usfds-core` service).

### 4.2. Side Navigation Bar
- Collapsible (240px $\to$ 64px) to give more room to large tables or the lineage DAG.
- Functions grouped by lifecycle: **Data Preparation** $\to$ **Detection & Modeling** $\to$ **Investigation** $\to$ **Reporting & Insights**.

---

## 5. Shared Component Specifications

### 5.1. Workspace Stepper (linear & branching pipeline navigation)
- **Purpose:** Guides the user through data preparation steps (`RAW` $\to$ `MAPPED` $\to$ `PRE_PROCESSED`).
- **States:**
  - **`Completed`:** Green circle with a check icon (`✓`); clickable to review the previous step's result.
  - **`Active`:** Glowing blue-outlined circle (`box-shadow: var(--shadow-glow-blue)`) showing the current step number.
  - **`Locked`:** Dim gray (`--primitives-slate-700`), `cursor: not-allowed`.
  - **`Forked Badge`:** When the user branches from an older node, the stepper shows a secondary label: *"🌿 Branch: [Branch Name] (Forked from Artifact #X)"*.

### 5.2. Interactive High-Density Data Grid
- **Sticky Column:** The first column (transaction ID or dataset name) stays fixed on horizontal scroll.
- **Column Header Health Bar:** A 3px mini bar under each column name:
  - Green: share of valid values (`100% - null%`).
  - Gray / red: share of missing values (`null%`).
- **Virtual Scrolling:** Mandatory, to render lists of thousands of rows smoothly.

### 5.3. Interactive Lineage Canvas (DAG)
- Built on interactive Canvas / SVG:
  - Mouse: zoom with the wheel, pan by dragging, shortcut `Space + Drag`.
  - **Node Selection:** Clicking a node highlights its border (`--border-focus`) and opens the inspector drawer on the right.
  - **Edge Styling:** Smooth Bézier curves with arrowheads showing data flow direction.

### 5.4. Slide-over Inspector Drawer
- Width 480px - 560px, slides in from the right.
- Does not cover the whole screen, so the user can watch the lineage tree / table while comparing details.
- Standard tabs: `Overview`, `Data Profiling`, `Validation Report`, `Configuration JSON`.

### 5.5. Async Task Progress & Toast Feedback
- **Non-blocking UX:** During heavy tasks (feature engineering or model training), a small fixed progress bar shows in the bottom-right corner.
- The user can move to other screens without interruption.
- On completion: show a toast with the action button **`[ View Result ➔ ]`**.

---

## 6. Accessibility (WCAG 2.1 AA)

To meet enterprise standards and pass UX testing:

1. **Contrast Ratio:**
   - Primary text (`--color-text-primary` on `--color-surface`): at least **7:1** (AAA).
   - Secondary text (`--color-text-secondary` on `--color-surface`): at least **4.5:1** (AA).
2. **Keyboard Navigation:**
   - Every button, link, input, and DAG node is reachable with `Tab`.
   - Focus indicator (`:focus-visible`): use the clear double `--focus-ring`; never `outline: none` without a replacement.
3. **Motion Safety:**
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, ::before, ::after {
       animation-duration: 0.01ms !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```
4. **Screen Reader Support:**
   - Complex data tables have a `caption`; columns have `scope="col"`.
   - Progress bars carry `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`.
