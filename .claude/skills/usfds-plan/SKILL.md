---
name: usfds-plan
description: Writes the single plan file for a USFDS task (one task = one agent session = one plan file, covering the issues the user assigned), including scope sizing, Design & Approach with Mermaid diagrams, dependency and parallel-conflict analysis against .plan/BOARD.md, milestones as checkpoints, and acceptance tests the user reviews before any code is written. Use when a session starts with one or more issues (ISS-NNN), when asked to "plan", "phân tích", "lên kế hoạch", or before implementing a task.
---

# USFDS task planning

A plan is the contract between the user and the agent. The user reviews **Design & Approach (§2.5) and Acceptance tests (§5)**, not every line of code. Keep it short, factual, and complete enough that another agent could implement it without asking.

## Task model <!-- [26-11-14] -->

| Concept | Meaning |
|---|---|
| **Issue** `ISS-NNN` | A problem or need (bug, feature, tech-debt) in `docs/issues/`. It says *what* and *why*, not *how*. A new feature is also an issue. |
| **Task** | **1 task = 1 agent session = 1 plan file** `.plan/<task_slug>.md`. The user decides which issues form the task and lists them in the prompt. One agent implements the whole task independently, however wide it is. A task is never split across agents. |
| **Milestone** | A checkpoint inside the plan so the user can verify progress (tests green at that point). It is not a separate task, branch or session, and the agent does not stop at it. |

- The plan file name (`<task_slug>`) is the task ID used on `.plan/BOARD.md`.
- If one of the given issues already has a plan file (see its `Plan:` field), extend that plan instead of creating a second one.

### Scope sizing: push back on the issue, never split the task
After reading the sources, judge whether the given issues form a sensible single session. Report the result in plan §2 as `Scope: OK | TOO-BROAD | TOO-SMALL`.
- **TOO-BROAD** (e.g. needs a product decision that does not exist yet, or bundles unrelated problems): do **not** split the task or invent extra tasks. Propose how to **split the issue** into new issues (titles + what goes where), then stop for the user's decision.
- **TOO-SMALL** (e.g. a one-line fix): propose related open issues from `docs/issues/README.md` that could be **merged into this task** (same area or same files), then stop for the user's decision.
- Never change the task's issue list on your own; the user decides.

## Steps

1. **Collect sources.** Read in this order, stop when you have enough:
   - Every issue given in the prompt (`docs/issues/README.md` → dated file) and its existing plan, if any.
   - The related spec in `docs/features/**/suc-spec.md`. If none exists and the task changes behavior, ask the user for the Notion link (see `AGENTs.md`).
   - `.plan/BOARD.md` (who is doing what, which files are owned).
   - The code you will touch. Never plan from memory: cite `path:line`.
2. **Size the scope** (section above). If `TOO-BROAD` or `TOO-SMALL`, write only §1–§2 of the plan with the proposal and stop.
3. **Write Design & Approach (§2.5).** Summarize the architecture, API/RBAC/schema contracts, and edge cases/concurrency risks. Include as many Mermaid diagrams as needed when the task crosses layers or changes workflow/state/schema (see Mermaid rules below).
4. **Analyze dependencies & conflicts** against other tasks on the board (checklist below). This decides whether the task can run while other sessions are open.
5. **Define milestones and the to-do list** (§6). Order milestones so each one ends with all tests green, typically one per layer (core+infra → server → web). Give each milestone its own acceptance tests and a nested checklist of concrete items tagged `[tests] [core] [infra] [server] [worker] [web] [docs] [verify]`. The plan is the task's only to-do list.
6. **Write acceptance tests (§5)** as Given/When/Then with the exact test function names, plus **Manual E2E (§9)** for anything SQLite/mocks cannot cover.
7. **Write the plan** to `.plan/<task_slug>.md` using [template.md](template.md). Do not add extra top-level sections; write `—` for a section that does not apply.
8. **Stop and ask for approval with a concise Review Brief.** Output only what the user needs to decide quickly:
   - Plan path, scope verdict, conflict verdict (`PARALLEL-SAFE` / `NEEDS-SEQUENCING` / `BLOCKED`).
   - Goal + the Mermaid diagram(s) from §2.5.
   - 3–5 key design decisions, contracts (API/RBAC/schema), and top risks.
   - Milestone summary with acceptance test names (not the full file list).
   - Open questions (§8).
   Do not write code before approval.

## Mermaid diagram rules (§2.5)

- **When to draw vs. skip (`—`):**
  - Skip (`—`) for small bug fixes, UI copy/style tweaks, or 1–2 file local changes that do not alter control/data flow.
  - Draw as many diagrams as the task warrants (no fixed cap) for tasks spanning 2+ layers (`core`/`infra`/`server`/`worker`/`web`), new decision/auth branches, state-machine changes, or schema/graph model changes.
- **Pick the right diagram type:**
  - Multi-component / API / Queue interactions → `sequenceDiagram`
  - Decision branching / data pipelines → `flowchart LR`
  - Entity lifecycle transitions → `stateDiagram-v2`
  - New/modified table relations → `erDiagram`
- **Keep diagrams readable and valid:**
  - Cap at ~15 nodes per diagram; split into separate focused diagrams instead of cramming one large chart.
  - Use real repo symbols, endpoints, and services; show only what changes or interacts with the change (never generic `FE -> BE -> DB` boxes).
  - Always quote labels containing special characters (`/`, `(`, `)`, `:`, punctuation) as `["..."]` so Mermaid renders cleanly in IDEs, GitHub, and `DocsDashboardPage`.

## Dependency & conflict checklist

Answer each item in the plan's §4 table. "Yes" answers must name the file or task.

| # | Question | How to check |
|---|---|---|
| D1 | Does this task need code/schema/API from an unfinished task? | `.plan/BOARD.md` status + grep for the symbols you need |
| D2 | Will an unfinished task need what this task produces? | BOARD "Depends on" column |
| C1 | Which files will be **modified**? Do any belong to an `In progress` task? | BOARD "Owned files" column |
| C2 | Does it touch a **hot-spot file**? | Hot-spot list below |
| C3 | Does it change the DB schema? | If yes: needs its own Alembic revision; note it |
| C4 | Does it change a public contract (REST endpoint, response schema, job payload, entity field) used by another task? | grep `usfds-web/src/api`, `usfds-worker`, other routers |
| C5 | Does it change shared UI shell (routes, sidebar, `client.ts`, shared types)? | Hot-spot list below |

Verdict rules:
- `BLOCKED`: D1 is yes and the dependency is not merged.
- `NEEDS-SEQUENCING`: C1 overlaps an in-progress task, or C4/C5 is yes while a dependent task is in progress.
- `PARALLEL-SAFE`: everything else. C2 and C3 alone do not block, but the plan must use append-only edits for hot-spot files and its own migration revision.

## Hot-spot files (edit = append only, never reformat)

- **Backend:** `usfds-core/src/usfds_core/domain/entities/enums.py`, `usfds-core/src/usfds_core/*/__init__.py`, `usfds-infra/src/usfds_infra/database/models.py`, `usfds-infra/src/usfds_infra/database/repositories.py`, `usfds-infra/src/usfds_infra/database/__init__.py`, `usfds-infra/src/usfds_infra/database/seed_rbac.py`, `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` (job constants), `usfds-server/src/usfds_server/api.py` (router registration), `usfds-server/src/usfds_server/dependencies.py`, `usfds-server/src/usfds_server/providers/repos.py`, `usfds-server/src/usfds_server/config.py`, `usfds-worker/src/usfds_worker/main.py` (handler maps), `deploy/.env.example`.
- **Web:** `usfds-web/src/App.tsx`, `usfds-web/src/components/layout/Sidebar.tsx`, `usfds-web/src/types/navigation.ts`, `usfds-web/src/api/client.ts`, `usfds-web/src/lib/feature-policy.ts`, all barrel `index.ts` files.
- **Process files:** `CHANGELOG.md`, `.plan/BOARD.md`, issue status in `docs/issues/`. Agents never edit these inside a task branch during implementation; they are updated at PR/merge time (or on `main` when claiming a parallel task). `TODO.md` is frozen history.

## Plan quality bar

- Every claim about current behavior cites `path:line`.
- §2.5 makes the approach, API/RBAC/schema contracts, and edge cases clear without reading §3.
- Scope lists files to **create** and files to **modify**; anything else is out of scope.
- Each acceptance test maps to one requirement (SUC/BR ID or issue ID).
- Bugs need a reproducing test that is red before the fix.
- State assumptions and anything deliberately omitted (minimal version first).
- Write in the same language as the user's request (Vietnamese is the default); code identifiers stay in English.
