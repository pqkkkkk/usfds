---
name: usfds-task-workflow
description: End-to-end lifecycle for implementing an approved USFDS task in one session, test-first, all milestones of the plan in order (checkpoints, not stop points), isolated worktree, verification with scripts/test.sh, and a final report with review hotspots so the user reviews tests and key logic instead of every line. Use when implementing an approved .plan/<task>.md.
---

# USFDS task workflow

The user reviews **tests and a few key logic points**, not the whole diff. Everything in this workflow exists to make that safe.

## 0. Preconditions
- An approved plan exists in `.plan/<task>.md` (skill `usfds-plan`). If not, plan first and stop.
- **1 task = 1 session = 1 plan file.** You implement the whole task yourself, every milestone in order. Do not hand parts to other agents, and do not open extra tasks.
- You work in your own git worktree and branch `task/<task_slug>`. Do not commit to `main`.
- Track progress only in your plan's §6 (tick each to-do item as you finish it). Do not edit `CHANGELOG.md` or `.plan/BOARD.md` in the task branch, and never add to `TODO.md` (frozen history). Report what should change; they are updated at merge.

## Milestone loop
Run sections 1–3 once per milestone (M1, M2, …) in plan order. Can stop early only when:
- an approved test is wrong;
- the plan turns out to be infeasible;
- a product decision is missing.

In those cases, report and wait.

At the end of each milestone:
- make sure all its to-do items in plan §6 are ticked, then tick the milestone;
- append one checkpoint-log line (date, test summary line, deviations);
- optionally commit with the message `M<n>: <name>`, so the user can check that point.

## 1. Tests first
1. Implement the plan §5 tests of the current milestone with the exact names. Follow skill `usfds-testing`.
2. Run them: `./scripts/test.sh <pkg>`. They must fail for the right reason (missing behavior, not import errors). For bugs, the reproducing test must fail on the current code.
3. Do not weaken, skip or delete an approved test to get green. If a test is wrong, stop and tell the user why.

## 2. Implement
- Follow `AGENTs.md` coding rules (tabs, semicolons in TS, 1TBS, minimal diff, no unrelated refactors, `DEPRECATED` instead of deleting).
- Backend changes: skill `usfds-backend-change`. Web changes: skill `usfds-frontend-change`.
- Stay inside plan §3 scope. If you must touch another file, note it in the report with the reason.
- Hot-spot files: append only.

## 3. Verify
- `./scripts/test.sh <every package you touched>` must be green, including the PostgreSQL-compatibility guards.
- Web: `npm run build && npm run lint && npm test` in `usfds-web`.
- Never claim green without pasting the summary line of the test output.

## 4. Final report (exact format)

```markdown
## Result: <task_slug> — <DONE | PARTIAL (stopped at M<n>) | BLOCKED>

**Milestones:** M1 ✅ <one line> · M2 ✅ ... (matches plan §6 checkpoint log)
**Tests:** <package>: <N passed, M failed> (paste summary lines)
**Acceptance tests:** all <K> from plan §5 implemented: yes/no (list deviations)

**Changed files:** <count>
- `<path>`: <one line>

**Review hotspots** (read these, skip the rest; tag each with its milestone):
1. `<path:line-range>` (M<n>): <what the logic decides, why it is risky, which test covers it>
2. ...

**Assumptions made:** <list or —>
**Not done / follow-ups:** <list or —, with proposed ISS entries>
**Merge notes:** Alembic revision `<id>` (down_revision `<id>`) · hot-spot edits: <files> · CHANGELOG/BOARD lines to add: <text>
```

### How to choose review hotspots (2–5 per milestone)
Choose code where a wrong decision would still let the tests pass, or would corrupt data:
- Authorization and permission checks, and ownership filters.
- Data deletion, overwrite, and state transitions (status enums, cancel, retry).
- Migrations and data backfills.
- Concurrency: locks, uniqueness, idempotency, queue retry behavior.
- Boundary conversions: serialization, timezones, NaN/Infinity, encodings.
- Anything you were unsure about, or implemented with an assumption.

Also copy the hotspots into plan §7.

## 5. After user approval (merge time)
Done by the merging agent or the user:
- Rebase onto `main`; if there is an Alembic revision, update `down_revision` to the current head and re-run tests.
- Update `CHANGELOG.md`, `.plan/BOARD.md`, and the ISS status in `docs/issues/` (both the dated file and `README.md`). Set the plan's status to `Done (YY-MM-DD)`.
