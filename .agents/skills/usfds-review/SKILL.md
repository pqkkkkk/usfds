---
name: usfds-review
description: Independent adversarial code & risk review for a completed USFDS task before presenting the Final Report to the user. Audits the diff against docs/arch/03-system-invariants.md, relevant docs/arch/modules/*.md, shared contracts (C1-C5), and the approved plan to catch silent bugs, auth/scope bypasses, contract drift, OOM risks, weak tests, and missing doc-sync. Use after ./scripts/test.sh is green and before step 4 (Final report) of usfds-task-workflow, or whenever asked to review a branch/PR/diff.
---

# USFDS adversarial review

Tests prove that *intended* paths pass. This review exists to catch **everything that still lets tests pass while introducing silent risk** (auth bypasses, silent data corruption, cross-module contract drift, OOM regressions, formula bugs, missing cleanup, weak/tautological tests, or stale architecture docs).

## Execution rule: Independent perspective
- **Prefer a fresh subagent / clean context** (e.g., `research` or a fresh `self` reviewer subagent) that did **not** write the implementation, so it does not inherit the author's blind spots.
- If no subagent tool is available, explicitly switch to an adversarial mindset and inspect the raw `git diff` line by line from scratch — never review from memory.

## Required inputs (read in this order)
1. `.plan/<task_slug>.md` (goal, §2.5 contracts/decisions, §4.5 invariant impact, §5 acceptance tests).
2. `docs/arch/03-system-invariants.md` (principles `P-01`..`P-04` and invariants `INV-001`..`INV-016`). <!-- [26-11-28] -->
3. Relevant `docs/arch/modules/<module>.md` and `docs/arch/02-data-and-lifecycle-flows.md` (Shared Contracts `C1–C5`).
4. The full diff: `git diff origin/main...HEAD` (or `git diff main...HEAD` / working-tree diff) + test output summary.

## Adversarial audit checklist (check every applicable item)

### 1. Security, RBAC & Project Isolation (`INV-001` – `INV-004`)
- **Auth & Public exposure:** Are any new routes missing `get_actor_context` / `require_system_permission`? Did CORS or presigned URL authorization weaken?
- **Project isolation & Anti-404-oracle:** On `GET /{id}` and mutations, is `project_id` verified *before* leaking existence? Can a caller pass a resource ID from Project B while authenticated in Project A?
- **`GrantScope.OWN` parity:** Do list endpoints filter by `owner_id` (`resolve_project_list_owner`), and do single-get/update/delete endpoints check `owner_id=record.user_id`?
- **Untrusted input & sandbox:** Any raw path from client read on server filesystem (S3 violation)? Any new subprocess/code-eval path without AST validation + timeout? Any credential leaked to remote compute?

### 2. Silent Data Corruption & Cross-Module Contracts (`C1–C5`, `INV-009`, `INV-010`, `INV-013`)
- **Silent fallbacks:** Look closely for `COALESCE(..., 0)`, `except Exception: return -1/None/0`, or `.fillna(0)` that silently masks malformed labels, timestamps, IDs, or metrics while returning `PASSED` / HTTP `200`.
- **Shared contracts (`C1–C5`):** If the diff touches `SystemColumnMetadata` / `non_ml_columns` (`C1`), artifact `output_paths` (`C2`), model artifacts/bundles (`C3`), binary labels (`C4`), or `ProjectWarehouse` facts (`C5`), did it update **every** producer and consumer listed in `02-data-and-lifecycle-flows.md`?
- **Data leakage & Two-Tier Prep:** Does `FEATURE_ENGINEERED` still preserve `event_id`, `user_id`, `timestamp`? Does train/test split happen *before* fitting cleansers/encoders/scalers?
- **Domain formulas:** For FDS metrics, thresholds, or rule logic, verify denominators, boundary conditions (`0`, `n=1`, `NaN`/`Inf`), monotonicity, and `BR-DT-07` precedence.

### 3. Resource Lifecycle, Concurrency & Scale (`INV-006`, `INV-007`, `INV-008`, `INV-011`, `INV-012`)
- **Delete & In-Use guards:** Can an in-use entity be deleted? Does deleting a DB record leave orphan files on `IFileStorage`? Does deletion work identically on SQLite **and** PostgreSQL?
- **Large data / RAM (`INV-007`, `INV-016`):** Did any API/analytics/data-management/investigation path re-introduce full-file `pd.read_csv`/`pd.read_parquet`, a new `pandas` import, or unbounded DuckDB connections?
- **Principles (`P-01`..`P-04`):** Any new hardcoded business value instead of system metadata? New `if/else` on a type instead of port + registry? New computation in a router instead of a job? New concrete engine import in `usfds-core`? **Was `PANDAS_IMPORT_ALLOWLIST` or `CORE_ENGINE_IMPORT_ALLOWLIST` extended?** Any addition is a `BLOCKER` (allowlists only shrink). <!-- [26-11-28] -->
- **Concurrency & Queue safety:** Are state transitions idempotent on redelivery? Are `Case` updates checked with `expected_version`? Is any DB session held open across network/subprocess I/O? Are deterministic errors marked non-retryable (`UnrecoverableError`)?
- **PostgreSQL & Migrations:** If schema changed, is there a single Alembic head, proper `ON DELETE` FKs, and zero SQLite-only SQL?

### 4. Test Integrity & Architecture Doc-Sync (`INV-014`, `INV-015`)
- **Test quality:** Did the implementation weaken, skip, or mock away the core behavior of an approved §5 acceptance test? Are edge cases and negative paths (403, 404, 409, malformed input) actually asserted, not just happy paths?
- **Frontend layering:** Did new `usfds-web` components bypass hooks to call `api/*` directly, swallow `ApiClientError`, or drift from `feature-policy.ts`?
- **Doc-Sync (`INV-015`):** If the diff changes any contract (`C1–C5`), state machine, queue/storage prefix, or invariant, is the corresponding `docs/arch/` update included (or flagged for step 5)?

## Output format (concise, evidence-backed)

```markdown
### Adversarial Review: <task_slug> — <PASS | PASS WITH NOTES | CHANGES REQUIRED>

**Invariants checked:** <list of INV-NNN audited>
**Findings:**
- **[BLOCKER]** `<path:line>` (`INV-NNN`): <concrete failure scenario & minimal fix>
- **[RISK]** `<path:line>` (`INV-NNN` / `C<n>`): <silent risk or edge case & recommended action>
- **[NIT]** `<path:line>`: <optional minor improvement>
*(Write `None` if no findings.)*

**Test coverage gaps:** <missing negative/edge cases or `—`>
**Doc-Sync (`INV-015`):** <`docs/arch/` files needing update, or `No arch doc change needed`>
```

## Verdict rules
- **`CHANGES REQUIRED`:** Any `BLOCKER` finding (auth/project/OWN bypass, silent data corruption, broken invariant, weakened acceptance test, Postgres/OOM regression). The implementing agent **must fix all `BLOCKER`s and re-verify** before presenting the Final Report to the user.
- **`PASS WITH NOTES`:** Zero `BLOCKER`s, one or more `RISK`s or doc-sync reminders — surface every `RISK` explicitly in the Final Report's **Review hotspots** so the user sees them immediately.
- **`PASS`:** Clean across all applicable invariants.
