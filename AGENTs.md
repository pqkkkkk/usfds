@README.md

> Read this `README.md` to understand overall context and purpose of the project.

---

## 0. Before You Start: Document Map

Identify the domain and read the corresponding documentation before implementing any request. Never edit code from memory or assumption.

| Request touches... | Read first |
| --- | --- |
| Architecture, modules, data model, principles & invariants | `docs/arch/README.md` — the single routing table for architecture docs <!-- [26-11-28] --> |
| Design system | `docs/design-system.md` |
| Use case specification | `docs/features/**/suc-spec.md`, and all sub items of Notion page [System use case specification](https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7) |
| Known issues / bugs | `docs/issues/README.md` (index, IDs `ISS-NNN`) |
| Task status, dependencies, file ownership | `.plan/BOARD.md`, master plan `.plan/parallel_agent_setup.md` |
| Writing / running tests | skill `usfds-testing` (`.claude/skills/usfds-testing/SKILL.md`) |

Every task must respect `docs/arch/03-system-invariants.md` (principles `P-01..P-04`, invariants `INV-001..016`). If a request does not clearly fall under any row, ask me for the relevant Notion link first; if Notion is unreachable, ask me to download the documentation into `docs/`. <!-- [26-11-28] -->

---

## 0.1 Parallel Agent Work

Several AI agents work on this repo at the same time. Follow these skills (in `.claude/skills/`, kept in sync with `.agents/skills/`):

| Phase | Skill | Output |
| --- | --- | --- |
| Plan | `usfds-plan` | `.plan/<task>.md` from the template, with `Design & Approach` (Mermaid + decisions/risks), Dependencies & Conflicts verdict, **§4.5 System Invariant & Blast-Radius Impact**, and acceptance tests. **Stop for user approval.** |
| Implement | `usfds-task-workflow` | Tests first, then code, in your own git worktree/branch `task/<slug>` |
| Review | `usfds-review` | Independent adversarial audit of diff against `docs/arch/03-system-invariants.md` & `modules/*.md` before Final Report |
| Backend | `usfds-backend-change` | Layer map, Alembic migrations, append-only hot spots |
| Frontend | `usfds-frontend-change` | Design system, Vietnamese UI copy, react-query, MSW tests |
| Tests | `usfds-testing` | `./scripts/test.sh` (no Docker), fixtures, PostgreSQL & architecture/route security guards |

- **Task model:** 1 task = 1 agent session = 1 plan file `.plan/<task_slug>.md`. The user decides which issues (`ISS-NNN`) form a task. The agent implements the whole task alone. Milestones are checkpoints inside the plan, not stop points. If the scope looks too broad or too small, propose splitting or merging **issues**; never split the task.
- **Review model:** the user reviews `Design & Approach`, §4.5 Invariant Impact, acceptance tests, adversarial review verdict (`usfds-review`), and the **Review hotspots** listed in the final report, not every line of code.
- **Board claiming for parallel runs:** when running multiple agents concurrently, mark the task `In progress` on `main`'s `.plan/BOARD.md` right after plan approval so other sessions' `C1` conflict checks detect owned files.
- **Single test entrypoint:** `./scripts/test.sh [core|infra|server|worker|web]`. Python is pinned to 3.12.
- **Hot-spot files** (shared registries) are append-only; see skill `usfds-plan` for the list.
- **Schema changes** only through Alembic revisions (`python -m usfds_infra.database.migrate revision "..."`), one per task.

---

# Coding Guidelines

Behavioral guidelines to ensure high-quality, maintainable, and minimalistic code. Bias toward caution over speed.

## 1. Development Workflow & Planning

* **Plan First:** Draft multi-step plans with verifiable success criteria in `.plan/<task_name>.md` prior to implementation. Loop until verified.
* **Think Before Coding:** State assumptions explicitly. Present multiple interpretations if they exist.
* **Proactive Minimal Payload:** Ship the minimal working version first for complex requests and question the complexity. If the user insists, build it without debate. Explicitly state omitted elements.
* **Clarify & Push Back:** Stop and ask if a request is ambiguous. Suggest simpler approaches.
* **Goal-Driven Execution:** Transform tasks into concrete, verifiable goals.

### 1.1 The Execution Ladder

Stop at the first true statement:

1. Does this need to be built at all? No? Skip it.
2. Does it already exist in this codebase? Reuse the helper, util, or pattern.
3. Does the standard library do it? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Do it.
7. Only then write the minimum code that works.

## 2. Simplicity & Minimalism

* **Minimum Viable Code:** Write only what is required to solve the problem. Default to the edge-case-correct option for ties.
* **No Speculation:** Zero unrequested features, single-use abstractions, or speculative flexibility.
* **Boundary Definition (When not to be lazy):** Never cut validation, error handling, security, accessibility, or data-loss protection. Never skip understanding; blind edits are prohibited.
* **Clean Logic:** Keep core logic linear and push implementation details to the edges. Boring beats clever.

## 3. Surgical & Iterative Changes

* **Iterate:** Implement step-by-step. Ban sweeping modifications. Touch the fewest files possible.
* **Minimal Footprint:** Every modified line must trace directly to the task. The shortest working diff wins.
* **Do not Fix Unbroken Things:** Never refactor adjacent code or reformat unrelated lines. Tag pre-existing issues with `TODO: ISS-NNN`.
* **Removing vs. Deprecating Code:** Delete obsolete code cleanly when a task explicitly removes a feature, endpoint, or column. Comment out with `DEPRECATED [YY-MM-DD]: reason` only when retaining temporary fallback or reference code.
* **Debug:** Fix root causes, not symptoms. Grep every caller end-to-end before editing. Fix the routing bottleneck once.
* **Testing:** Follow `usfds-testing` — write the approved acceptance tests in plan §5 (one focused test per requirement/SUC/BR/ISS). Avoid bloated tests for trivial one-liners.

## 4. Formatting & Naming Conventions

* **Formatting:**
  * **TypeScript / React (`usfds-web`):** Tabs in new files (follow the file's existing style when editing), semicolons mandatory, One True Brace Style (1TBS).
  * **Python (`usfds-core`, `usfds-infra`, `usfds-server`, `usfds-worker`):** Tabs in new files (follow the file's existing indentation when editing); no semicolons. Never reformat untouched lines.
* **Naming Conventions:**
  * `camelCase`: Variables and functions in `usfds-web`.
  * `snake_case`: Variables and functions in Python packages (`usfds-core`, `usfds-infra`, `usfds-server`, `usfds-worker`).
  * `UPPER_SNAKE_CASE`: Constants and globals.
  * `_prefix`: Internal or private functions.

## 5. HTML & CSS Design Philosophy

Follow current design system guidelines for consistency in UI components, typography, spacing, and color schemes in `docs/design-system.md`.

---

## Documentation Location

All documentation is maintained in the Notion page [Task](https://app.notion.com/p/325b99c6a9508074ba72e26e509260bf?v=325b99c6a9508078acdc000cad8d9232). Documentation in `docs/` is the local reference and is kept in sync with Notion. Architecture docs (`docs/arch/`), `AGENTS.md`, `README.md` and `docs/design-system.md` are written in English. <!-- [26-11-28] -->

**Agent Modification Policy:** Request user approval before editing any file in `docs/`. Append a `[YY-MM-DD]` comment to all approved edits.

---

# CRITICAL IMPORTANT: MANDATORY AGENT DIRECTIVE
<!-- [26-11-28] Deduplicated: workflow steps live in the skills of §0.1; Notion rules live in §0. -->

Before modifying codebase logic, databases, routes, or assets:

1. Ensure no custom UI for API keys is generated. Rely strictly on standard `.env.example` configurations.
2. Do not delete or rename `README.md` or this file. Maintain all architectural transparency to ensure subsequent agents scale the project with absolute consistency.
3. Follow the lifecycle in §0.1 end to end: `usfds-plan` (stop for approval) → `usfds-task-workflow` (tests first, final report, push after approval) → `usfds-review` before the final report. Never skip a phase.
4. **Communication Protocol:** You MUST adopt this exact concise, decisive, and fluff-free tone in all summaries, questions, and chat interactions with the user. Stop guessing; state the facts.
