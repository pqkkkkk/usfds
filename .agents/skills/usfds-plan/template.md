# Plan: <Title>

> **Task ID:** `<task_slug>` (= this file name) · **Issues:** ISS-NNN, ISS-NNN (chosen by the user) · **Spec:** <docs/features/... · Notion link · —>
> **Conflict verdict:** <PARALLEL-SAFE | NEEDS-SEQUENCING | BLOCKED> · **Status:** Draft | Approved (YY-MM-DD) | In progress (M<n>) | Done (YY-MM-DD)

## 1. Context (facts)
- <current behavior with `path:line`>
- <root cause for bugs>

## 2. Goal, scope verdict & non-goals
- **Goal:** <one sentence, verifiable>
- **Scope:** OK | TOO-BROAD → <proposed issue split> | TOO-SMALL → <issues proposed to merge in>
- **Non-goals / omitted:** <what is deliberately not done>
- **Assumptions:** <explicit assumptions; open questions go to §8>

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| create | `<path>` | M1 | |
| modify | `<path>` | M2 | append-only if hot-spot |
| migration | `.../migrations/versions/<rev>_<slug>.py` | M1 | or — |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No / Yes: <task> |
| D2 | Needed by unfinished task? | No / Yes: <task> |
| C1 | Modified files owned by in-progress task? | No / Yes: <file → task> |
| C2 | Hot-spot files touched | — / <files> (append-only) |
| C3 | Schema change | No / Yes: <tables/columns> |
| C4 | Public contract change | No / Yes: <endpoint/payload> → consumers: <...> |
| C5 | Shared UI shell change | No / Yes: <file> |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_<behavior_sentence>` (`<test file>`) | <state> | <action> | <observable result> | <ISS/SUC/BR> |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [ ] **M1 — <name>** (<packages>): <what exists after this checkpoint>
  - [ ] [tests] Write the M1 tests from §5; confirm they fail for the right reason
  - [ ] [core] ...
  - [ ] [infra] ...
  - [ ] [verify] `./scripts/test.sh <pkgs>`
- [ ] **M2 — <name>** (<packages>): ...
  - [ ] [tests] ...
  - [ ] [server] ...
  - [ ] [verify] ...

Checkpoint log (the agent appends one line per finished milestone):
- <YY-MM-DD> M1 done: <test summary line>; notes: <deviations or —>

## 7. Review hotspots (filled in after implementation)
- `<path:line>`: <why this logic matters / what could go wrong> (M<n>)

## 8. Open questions
- <question for the user, or —>
