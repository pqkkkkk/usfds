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
| ISS-003 | In-use datasets can still be deleted | bug | data-management | P1 | Resolved (26-11-15) | [quick_bugfix_and_cors_hardening](../../.plan/quick_bugfix_and_cors_hardening.md) | [11-01](11-01-2026.md) |
| ISS-004 | Double transfer via `uploads/` staging (presigned URL) | improvement | storage | P3 | Open | — | [11-11](11-11-2026.md) |
| ISS-005 | Mixed Vietnamese/English in usfds-web | improvement | web | P2 | Resolved (26-11-14) | — <!-- [26-11-14] --> | [11-13](11-13-2026.md) |
| ISS-006 | No user management / authentication / RBAC | feature | auth | **P0** | Resolved (26-11-15) | [user_management_rbac](../../.plan/user_management_rbac.md) | [11-13](11-13-2026.md) |
| ISS-007 | System metadata (system columns) not manageable | feature | data-management | P2 | Resolved (26-11-21) | [system_metadata_management](../../.plan/system_metadata_management.md) <!-- [26-11-21] --> | [11-13](11-13-2026.md) |
| ISS-008 | No lineage visualization for model versions | feature | training, web | P2 | Resolved (26-11-14) | [model_version_lineage](../../.plan/model_version_lineage.md) <!-- [26-11-14] --> | [11-13](11-13-2026.md) |
| ISS-009 | Training only on local dedicated worker | feature | training, worker | P3 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-010 | Model versioning has no semantics; duplicate versions possible | improvement | training | P2 | Resolved (26-11-21) | [model_versioning_scheme](../../.plan/model_versioning_scheme.md) <!-- [26-11-21] --> | [11-13](11-13-2026.md) |
| ISS-011 | Training jobs cannot be stopped | feature | training, worker | P2 | Needs spec | — | [11-13](11-13-2026.md) |
| ISS-012 | Large-data analytics in API process with pandas | improvement | insight-report, inference | P2 | Resolved (26-11-22) | [large_data_analytics_duckdb](../../.plan/large_data_analytics_duckdb.md) <!-- [26-11-22] --> | [11-13](11-13-2026.md) |
| ISS-013 | Third-party API key committed to git | security | agent, devex | **P0** | Resolved (26-11-15) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-014 | CORS `*` with credentials | security | server | P1 | Resolved (26-11-15) | [quick_bugfix_and_cors_hardening](../../.plan/quick_bugfix_and_cors_hardening.md) | [11-14](11-14-2026.md) |
| ISS-015 | Server reads arbitrary client-supplied file paths | security | server, worker | P1 | Resolved (26-11-15) | [presigned_upload_and_file_io_guard](../../.plan/presigned_upload_and_file_io_guard.md) <!-- [26-11-15] --> | [11-14](11-14-2026.md) |
| ISS-016 | Plugin upload has no size limit | security | server, training | P2 | Resolved (26-11-17) | [quick_backend_hardening](../../.plan/quick_backend_hardening.md) | [11-14](11-14-2026.md) |
| ISS-017 | `delete_dataset` never deletes artifact files | bug | data-management | P1 | Resolved (26-11-15) | [quick_bugfix_and_cors_hardening](../../.plan/quick_bugfix_and_cors_hardening.md) | [11-14](11-14-2026.md) |
| ISS-018 | Case filter by rule code only works on SQLite | bug | investigation, infra | P1 | Resolved (26-11-17) | [quick_backend_hardening](../../.plan/quick_backend_hardening.md) | [11-14](11-14-2026.md) |
| ISS-019 | Async plugin upload blocks event loop | bug | server | P1 | Resolved (26-11-17) | [quick_backend_hardening](../../.plan/quick_backend_hardening.md) | [11-14](11-14-2026.md) |
| ISS-020 | No schema migrations (create_all only) | bug | infra | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-021 | Queue request/reply jobs leak on timeout, no retry | bug | infra, worker | P2 | Resolved (26-11-22) | [large_data_analytics_duckdb](../../.plan/large_data_analytics_duckdb.md) <!-- [26-11-22] --> | [11-14](11-14-2026.md) |
| ISS-022 | Plugin/script subprocesses have no timeout | bug | training, inference | P2 | Resolved (26-11-17) | [quick_backend_hardening](../../.plan/quick_backend_hardening.md) | [11-14](11-14-2026.md) |
| ISS-023 | Missing FKs / uniqueness constraints | bug | infra | P2 | Resolved (26-11-22) | [own_scope_access_control](../../.plan/own_scope_access_control.md) <!-- [26-11-22] --> | [11-14](11-14-2026.md) |
| ISS-024 | Dev env not pinned; parts of suite broken | tech-debt | devex | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-025 | Test setup duplicated, depends on global state | tech-debt | devex | **P0** | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-026 | Hot-spot files cause merge conflicts | tech-debt | devex | P1 | Resolved backend (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-027 | System column aliases duplicated in 5 places | tech-debt | inference, insight-report | P2 | Resolved (26-11-21) | [system_metadata_management](../../.plan/system_metadata_management.md) <!-- [26-11-21] --> | [11-14](11-14-2026.md) |
| ISS-028 | Web API client swallows errors | bug | web | P1 | Resolved (26-11-16) | [web_api_client_error_propagation](../../.plan/web_api_client_error_propagation.md) <!-- [26-11-16] --> | [11-14](11-14-2026.md) |
| ISS-029 | Inconsistent server ports (8000 vs 8200) | bug | web, server | P3 | Resolved (26-11-14) | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-030 | Ad-hoc HTTP error mapping, swallowed exceptions | tech-debt | server | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-031 | List endpoints not paginated; N+1 in reports | improvement | server | P3 | Partial (26-11-22 — 8 core list endpoints paginated; reports/blacklist deferred) | [resource_owner_and_cursor_pagination](../../.plan/resource_owner_and_cursor_pagination.md) <!-- [26-11-22] --> | [11-14](11-14-2026.md) |
| ISS-032 | Web data fetching/typing inconsistent | tech-debt | web | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-033 | `usfds-agent` not runnable | tech-debt | agent | P3 | Open | — | [11-14](11-14-2026.md) |
| ISS-034 | Documentation inconsistencies (SUC IDs, links) | docs | docs | P2 | In progress | [parallel_agent_setup](../../.plan/parallel_agent_setup.md) | [11-14](11-14-2026.md) |
| ISS-035 | Reading a model with `risk_level` raises NameError | bug | training, infra | P2 | Resolved (26-11-15) | [quick_bugfix_and_cors_hardening](../../.plan/quick_bugfix_and_cors_hardening.md) | [11-14](11-14-2026.md) |
| ISS-036 | Dataset import & exports inconsistent across S3 presigned and Electron local modes | bug | web, storage, server | P1 | Resolved (26-11-15) | [presigned_upload_and_file_io_guard](../../.plan/presigned_upload_and_file_io_guard.md) <!-- [26-11-15] --> | [11-15](11-15-2026.md) |
| ISS-037 | Feature visibility gating by ActorContext and missing router permission enforcement | feature | auth, server, web | P1 | Resolved (26-11-16) | [rbac_feature_visibility](../../.plan/rbac_feature_visibility.md) <!-- [26-11-16] --> | [11-16](11-16-2026.md) |
| ISS-038 | Training evaluation metrics misaligned with TASK-105 specification | improvement | training, web | P2 | Planned | [training_evaluation_metrics](../../.plan/training_evaluation_metrics.md) <!-- [26-11-17] --> | [11-17](11-17-2026.md) |
| ISS-039 | No AutoML (Optuna Bayesian Optimization) in model training flow | feature | training, server, web | P2 | Planned | [automl_training_integration](../../.plan/automl_training_integration.md) <!-- [26-11-17] --> | [11-17](11-17-2026.md) |
| ISS-040 | Feature management capability not specified or implemented | feature | data-management, web | P2 | Needs spec | [feature_management](../../.plan/feature_management.md) <!-- [26-11-17] --> | [11-17](11-17-2026.md) |
| ISS-041 | Graph exploration capability not specified or implemented | feature | investigation, web | P2 | Needs spec | [graph_exploration](../../.plan/graph_exploration.md) <!-- [26-11-17] --> | [11-17](11-17-2026.md) |
| ISS-042 | Missing `project_id` enforcement and cross-project authorization bypasses on list, get-by-id, and related endpoints | security | auth, server, training, data-management, rule-engine, detection, storage, web | **P0** | Resolved (26-11-22) | [project_scoped_access_control](../../.plan/project_scoped_access_control.md) <!-- [26-11-21] [26-11-22] --> | [11-21](11-21-2026.md) |
| ISS-043 | `GrantScope.OWN` access control not enforced across routers and missing `owner_id` on domain tables | bug | auth, server, infra, training, rule-engine, detection, investigation | P1 | Resolved (26-11-22 — Investigation deferred to redesign) | [own_scope_access_control](../../.plan/own_scope_access_control.md) <!-- [26-11-22] --> | [11-21](11-21-2026.md) |
| ISS-044 | Data Management & Feature Engineering load full datasets with pandas | improvement | data-management, training | P2 | Open <!-- [26-11-21] --> | — | [11-21](11-21-2026.md) |
| ISS-045 | Investigation Assign flow has no owner role and Workbench loads full source files | improvement | investigation, server, web | P2 | Resolved (26-11-22) <!-- [26-11-22] --> | [investigation_redesign](../../.plan/investigation_redesign.md) <!-- [26-11-22] --> | [11-22](11-22-2026.md) |

Older resolved bugs (pre-ISS numbering) are kept in [`docs/bugs.md`](../bugs.md).
