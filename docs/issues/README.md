# Issue Index
<!-- [26-11-14] Created. Single entry point for all issues. -->

Every issue has a stable ID `ISS-NNN` and lives in exactly one dated file `docs/issues/MM-DD-YYYY.md` (the date it was detected). This index is the place to search, filter and prioritize.

Search tips: `grep -rn "ISS-017" docs/ .plan/` · `grep -n "| P0" docs/issues/README.md` · `grep -n "auth" docs/issues/README.md`

## Conventions

**Entry format** (in the dated file):
```markdown
## ISS-NNN: <Short title, problem-oriented>
- **Status:** Open | Open — needs spec | Planned | In progress | Resolved (YY-MM-DD) | Won't fix
- **Type:** bug | security | feature | improvement | tech-debt | docs · **Area:** <areas> · **Priority:** P0..P3
- **Plan:** `.plan/<file>.md` or — (with phase/task hint)
- **Impact / Root cause / Facts:** ... (with `path:line` references)
- **Direction / Fix:** ... (optional)
```

**Priority:** `P0` blocks other work or exposes secrets/data · `P1` incorrect behavior or security gap in a main flow · `P2` important but not blocking · `P3` polish.

**Areas:** `auth`, `data-management`, `training`, `inference`, `rule-engine`, `investigation`, `insight-report`, `storage`, `server`, `worker`, `infra`, `web`, `agent`, `devex`, `docs`.

**Rules:**
- New issue: take the next free ID, add it to today's dated file, and add a row to the table below.
- Never renumber or delete an issue. When resolved, set `Status: Resolved (YY-MM-DD)` in both places.
- Plans and task notes reference issues by ID (`ISS-017`) so `grep` finds every mention.
- **Plan / Task** links the plan file of the task that covers the issue (1 task = 1 plan file = 1 agent session; the user decides which issues form a task). `—` = backlog. Hints like "Phase 1 · A3" or "with ISS-011" in the dated files are only suggestions.

## Index

| ID | Title | Type | Area | Pri | Status | Plan / Task (plan file) | File |
|---|---|---|---|---|---|---|---|
| ISS-001 | Model artifact format is implicit (training ↔ inference) | bug | training, inference | P1 | Open | — | [11-01](11-01-2026.md) |
| ISS-002 | In-use rules can still be deleted | bug | rule-engine | P1 | Open | — | [11-01](11-01-2026.md) |
| ISS-003 | In-use datasets can still be deleted | bug | data-management | P1 | Open | — | [11-01](11-01-2026.md) |
| ISS-004 | Double transfer via `uploads/` staging (presigned URL) | improvement | storage | P3 | Open | — | [11-11](11-11-2026.md) |
| ISS-005 | Mixed Vietnamese/English in usfds-web | improvement | web | P2 | Resolved (26-11-14) | — <!-- [26-11-14] --> | [11-13](11-13-2026.md) |
| ISS-006 | No user management / authentication / RBAC | feature | auth | **P0** | Planned | [user_management_rbac](../../.plan/user_management_rbac.md) | [11-13](11-13-2026.md) |
| ISS-007 | System metadata (system columns) not manageable | feature | data-management | P2 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-008 | No lineage visualization for model versions | feature | training, web | P2 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-009 | Training only on local dedicated worker | feature | training, worker | P3 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-010 | Model versioning has no semantics; duplicate versions possible | improvement | training | P2 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-011 | Training jobs cannot be stopped | feature | training, worker | P2 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-012 | Large-data analytics in API process with pandas | improvement | insight-report, inference | P2 | Open | — | [11-13](11-13-2026.md) |
| ISS-013 | Third-party API key committed to git | security | agent, devex | **P0** | In progress (rotate key) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-014 | CORS `*` with credentials | security | server | P1 | Open | — | [11-14](11-14-2026.md) |
| ISS-015 | Server reads arbitrary client-supplied file paths | security | server, worker | P1 | Open | — | [11-14](11-14-2026.md) |
| ISS-016 | Plugin upload has no size limit | security | server, training | P2 | Open | — | [11-14](11-14-2026.md) |
| ISS-017 | `delete_dataset` never deletes artifact files | bug | data-management | P1 | Open | — | [11-14](11-14-2026.md) |
| ISS-018 | Case filter by rule code only works on SQLite | bug | investigation, infra | P1 | Open | — | [11-14](11-14-2026.md) |
| ISS-019 | Async plugin upload blocks event loop | bug | server | P1 | Open | — | [11-14](11-14-2026.md) |
| ISS-020 | No schema migrations (create_all only) | bug | infra | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-021 | Queue request/reply jobs leak on timeout, no retry | bug | infra, worker | P2 | Open | — | [11-14](11-14-2026.md) |
| ISS-022 | Plugin/script subprocesses have no timeout | bug | training, inference | P2 | Open | — | [11-14](11-14-2026.md) |
| ISS-023 | Missing FKs / uniqueness constraints | bug | infra | P2 | Open | — | [11-14](11-14-2026.md) |
| ISS-024 | Dev env not pinned; parts of suite broken | tech-debt | devex | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-025 | Test setup duplicated, depends on global state | tech-debt | devex | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-026 | Hot-spot files cause merge conflicts | tech-debt | devex | P1 | Resolved backend (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-027 | System column aliases duplicated in 5 places | tech-debt | inference, insight-report | P2 | Open | — | [11-14](11-14-2026.md) |
| ISS-028 | Web API client swallows errors | bug | web | P1 | Open (assessed) | — | [11-14](11-14-2026.md) |
| ISS-029 | Inconsistent server ports (8000 vs 8200) | bug | web, server | P3 | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-030 | Ad-hoc HTTP error mapping, swallowed exceptions | tech-debt | server | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-031 | List endpoints not paginated; N+1 in reports | improvement | server | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-032 | Web data fetching/typing inconsistent | tech-debt | web | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-033 | `usfds-agent` not runnable | tech-debt | agent | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-034 | Documentation inconsistencies (SUC IDs, links) | docs | docs | P2 | In progress | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-035 | Reading a model with `risk_level` raises NameError | bug | training, infra | P2 | Open | — | [11-14](11-14-2026.md) |

Older resolved bugs (pre-ISS numbering) are kept in [`docs/bugs.md`](../bugs.md).
