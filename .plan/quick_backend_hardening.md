# Plan: Quick Backend Hardening (ISS-016, ISS-018, ISS-019, ISS-022)

> **Task ID:** `quick_backend_hardening` · **Issues:** ISS-016, ISS-018, ISS-019, ISS-022 · **Spec:** — (bugfixes & hardening)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-17)

## 1. Context (facts)
- **ISS-018:** `SqliteCaseRepository.search` (`usfds-infra/src/usfds_infra/database/case_repositories.py:75-77`) filters `triggered_rule_codes` using SQLite-only `func.json_each(CaseModel.triggered_rule_codes)`. Already marked `@pytest.mark.xfail` in `usfds-infra/tests/test_pg_compat_guard.py:40-42`. On PostgreSQL `json_each` expects a JSON object (fails on JSON arrays; PostgreSQL requires `json_array_elements_text`).
- **ISS-019:** `upload_and_register_plugged_model` (`usfds-server/src/usfds_server/routers/training_router.py:226-293`) is declared `async def`, so it executes on Uvicorn's single asyncio event loop.
  - In `dispatch_backend == "queue"` (`training_router.py:270-286`), it calls `BullMQJobQueue.enqueue_and_wait(...)` (`usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py:104-149`), which runs `run_sync(...)` (`bullmq_queue.py:44-51`) → spawns a `ThreadPoolExecutor(max_workers=1)` and blocks synchronously on `.result()` while polling up to 300s (`timeout_seconds=300.0`).
  - In `dispatch_backend == "sync"` (`training_router.py:288-293`), it calls synchronous `service.register_plugged_model(...)` (which runs AST check, dry-run training/inference subprocesses, DB writes, and storage I/O) directly on the event loop.
  - Other routes calling `enqueue_and_wait` (`dataset_router.py`, `rule_router.py`, `register_plugged_model` at `training_router.py:165`) are plain `def`, so FastAPI runs them in AnyIO's worker threadpool.
- **ISS-016:** `upload_and_register_plugged_model` (`training_router.py:234`) calls `await request.body()`, reading arbitrarily large payloads into memory with no size limit check.
- **ISS-022:** Subprocess execution in `ScriptPluginTrainer.train` (`usfds-core/src/usfds_core/services/training/models/script_trainer.py:162`) and `execute_plugin_bundle_inference` (`usfds-core/src/usfds_core/services/inference/executor.py:226`) calls `subprocess.run(...)` with no `timeout`. `ModelPluginValidator` (`usfds-core/src/usfds_core/services/training/plugins/validator.py:289,366`) already passes `timeout=self.dry_run_timeout_seconds`, but does not catch `subprocess.TimeoutExpired` to return a structured `PluginValidationResult`.

## 2. Goal, scope verdict & non-goals
- **Goal:** Fix PostgreSQL compatibility of case rule-code filtering (`ISS-018`), enforce bounded streaming upload and offload blocking plugin registration off the asyncio event loop (`ISS-016`, `ISS-019`), and enforce explicit subprocess timeouts with clear error handling (`ISS-022`).
- **Scope:** OK
- **Non-goals / omitted:**
  - Not refactoring `enqueue_and_wait` itself into an async/webhook job pattern (`ISS-021`).
  - Not adding a global upload size limit middleware to unrelated endpoints or changing `POST /models/plugins` JSON `zip_base64` schema.
  - Not adding mid-flight user cancellation for training jobs (`ISS-011`).
- **Assumptions:**
  - Default max plugin upload size: `10 MB` (`USFDS_MAX_PLUGIN_UPLOAD_MB=10` in `Settings`), returning HTTP `413` when exceeded.
  - Default subprocess timeouts: `600s` for `ScriptPluginTrainer` and `300s` for `execute_plugin_bundle_inference` (overridable via constructor/function arguments).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/training/models/script_trainer.py` | M1 | Add `timeout_seconds` (default 600) + `TimeoutExpired` → `RuntimeError` |
| modify | `usfds-core/src/usfds_core/services/inference/executor.py` | M1 | Add `timeout_seconds` (default 300) in `execute_plugin_bundle_inference` + `TimeoutExpired` → `RuntimeError` |
| modify | `usfds-core/src/usfds_core/services/training/plugins/validator.py` | M1 | Catch `subprocess.TimeoutExpired` at lines 289 & 366 → `PluginValidationResult(is_valid=False, ...)` |
| modify | `usfds-core/tests/training/test_script_trainer.py` | M1 | Test timeout raises `RuntimeError` |
| modify | `usfds-core/tests/test_inference_service.py` | M1 | Test `execute_plugin_bundle_inference` timeout raises `RuntimeError` |
| modify | `usfds-core/tests/training/test_model_plugin_e2e.py` | M1 | Test validator dry-run timeout returns `is_valid=False` |
| modify | `usfds-infra/src/usfds_infra/database/case_repositories.py` | M2 | Dialect branch in `search()` for `rule_code`: `json_array_elements_text` on PostgreSQL, `sqlite_only()` + `json_each` on SQLite |
| modify | `usfds-infra/tests/test_pg_compat_guard.py` | M2 | Remove `xfail` on `test_case_search_by_rule_code_is_postgresql_compatible` + verify PG dialect compile |
| modify | `usfds-infra/tests/test_case_repositories.py` | M2 | Test `search({"rule_code": ...})` exact match filtering (`R1` vs `R10`) |
| modify | `usfds-server/src/usfds_server/config.py` | M3 | Append `max_plugin_upload_mb: int` (`USFDS_MAX_PLUGIN_UPLOAD_MB`, default 10) (hot-spot: append-only) |
| modify | `deploy/.env.example` | M3 | Append `USFDS_MAX_PLUGIN_UPLOAD_MB` comment/default if appropriate (hot-spot: append-only) |
| modify | `usfds-server/src/usfds_server/routers/training_router.py` | M3 | Bounded streaming body read (`413` on oversize) + `run_in_threadpool` for sync/blocking registration work |
| modify | `usfds-server/tests/test_training_api.py` | M3 | Tests for oversize upload `413` (Content-Length & streaming) and non-blocking event loop during `upload_and_register_plugged_model` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (all tasks on `.plan/BOARD.md` are `Done`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (no `In progress` tasks on `.plan/BOARD.md`) |
| C2 | Hot-spot files touched | `usfds-server/src/usfds_server/config.py`, `deploy/.env.example` (append-only) |
| C3 | Schema change | No |
| C4 | Public contract change | No breaking change; `POST /api/v1/training/models/plugins/upload` adds `413` response when exceeding `max_plugin_upload_mb` |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_script_training_timeout_raises_runtime_error` (`usfds-core/tests/training/test_script_trainer.py`) | A plugin script sleeping longer than `timeout_seconds=1` | `ScriptPluginTrainer(..., timeout_seconds=1).train(...)` is called | Raises `RuntimeError` mentioning timeout within ~1s instead of hanging | ISS-022 |
| M1 | `test_plugin_bundle_inference_timeout_raises_runtime_error` (`usfds-core/tests/test_inference_service.py`) | A plugin bundle whose `run_inference` sleeps longer than `timeout_seconds=1` | `execute_plugin_bundle_inference(..., timeout_seconds=1)` is called | Raises `RuntimeError` mentioning timeout | ISS-022 |
| M1 | `test_validator_dry_run_timeout_returns_invalid_result` (`usfds-core/tests/training/test_model_plugin_e2e.py`) | A plugin whose `run_training` sleeps longer than `dry_run_timeout_seconds=1` | `ModelPluginValidator(dry_run_timeout_seconds=1).validate(...)` is called | Returns `PluginValidationResult(is_valid=False)` with timeout error message and cleans temp dir | ISS-022 |
| M2 | `test_case_search_by_rule_code_is_postgresql_compatible` (`usfds-infra/tests/test_pg_compat_guard.py`) | Default SQLite test DB with `pg_compat` guard active | `SqliteCaseRepository(db_session).search(uuid4(), {"rule_code": "R1"}, "priority", 1, 20)` runs | Passes without `PostgresCompatibilityError`; PG branch compiles cleanly to `json_array_elements_text` | ISS-018 |
| M2 | `test_case_search_by_rule_code_filters_exact_code` (`usfds-infra/tests/test_case_repositories.py`) | Cases with `triggered_rule_codes=["R1"]` and `["R10"]` | `repo.search(project_id, {"rule_code": "R1"}, ...)` runs | Only returns the case containing exact `"R1"` (not `"R10"`) | ISS-018 |
| M3 | `test_plugin_upload_rejects_oversize_content_length_and_stream` (`usfds-server/tests/test_training_api.py`) | `settings.max_plugin_upload_mb` set low (or patched max bytes) | `POST /api/v1/training/models/plugins/upload` sends payload exceeding limit (both with and without `Content-Length`) | Returns HTTP `413` before buffering unbounded body in memory | ISS-016 |
| M3 | `test_plugin_upload_does_not_block_event_loop` (`usfds-server/tests/test_training_api.py`) | Slow blocking `enqueue_and_wait` (queue mode) or `register_plugged_model` (sync mode) sleeping ~0.3s | Concurrent `GET /health` is sent while `POST /models/plugins/upload` is in-flight on the same ASGI event loop | `GET /health` responds immediately (<0.1s) before the upload completes | ISS-019 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)

- [x] **M1 — Subprocess timeouts in training & inference** (`usfds-core`): Add timeouts and clean `TimeoutExpired` handling across all plugin/script `subprocess.run` sites.
  - [x] [tests] Write M1 tests from §5 and confirm they fail before the fix
  - [x] [core] Add `timeout_seconds` & `TimeoutExpired` handling in `script_trainer.py`, `inference/executor.py`, `plugins/validator.py`
  - [x] [verify] `./scripts/test.sh core`
- [x] **M2 — PostgreSQL-compatible case rule_code filter** (`usfds-infra`): Dialect-safe `rule_code` filtering in `SqliteCaseRepository.search`.
  - [x] [tests] Remove `xfail` in `test_pg_compat_guard.py` and add exact-match + PG compile tests in `test_case_repositories.py` / `test_pg_compat_guard.py`; confirm failure before fix
  - [x] [infra] Update `case_repositories.py` with PostgreSQL `json_array_elements_text` + `sqlite_only()` SQLite branch
  - [x] [verify] `./scripts/test.sh infra`
- [x] **M3 — Non-blocking & size-bounded plugin upload** (`usfds-server`): Bounded streaming read + `run_in_threadpool` offloading in `training_router.py`.
  - [x] [tests] Write M3 tests from §5 (`413` oversize rejection + concurrent `/health` non-blocking check) and confirm they fail before fix
  - [x] [server] Append `max_plugin_upload_mb` to `config.py` & `deploy/.env.example`; update `upload_and_register_plugged_model` in `training_router.py`
  - [x] [verify] `./scripts/test.sh core infra server`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-17 M1 done: `152 passed, 15 skipped, 169 warnings in 8.69s` (usfds-core); notes: —
- 26-11-17 M2 done: `37 passed in 4.04s` (usfds-infra); notes: —
- 26-11-17 M3 done: `core: 152 passed, 15 skipped; infra: 37 passed; server: 33 passed` (all 3 green); notes: default `max_plugin_upload_mb` set to 10 MB per user confirmation

## 7. Review hotspots (filled in after implementation)
1. `usfds-core/src/usfds_core/services/training/models/script_trainer.py:160-175` (M1): Default `timeout_seconds=600` wraps `subprocess.run`; catches `TimeoutExpired` and raises `RuntimeError` so `TrainingRunExecutor` marks the run `FAILED`. Covered by `test_script_training_timeout_raises_runtime_error`.
2. `usfds-core/src/usfds_core/services/inference/executor.py:158-166,225-228` (M1): Default `timeout_seconds=300` on `execute_plugin_bundle_inference`; catches `TimeoutExpired` and raises `RuntimeError` so batch inference fails cleanly instead of wedging worker slots. Covered by `test_plugin_bundle_inference_timeout_raises_runtime_error`.
3. `usfds-core/src/usfds_core/services/training/plugins/validator.py:289-306,365-385` (M1): Catches `subprocess.TimeoutExpired` for both dry-run training and dry-run inference and returns `PluginValidationResult(is_valid=False)` inside the `try/finally` cleanup block. Covered by `test_validator_dry_run_timeout_returns_invalid_result`.
4. `usfds-infra/src/usfds_infra/database/case_repositories.py:69-102` (M2): Dialect branch uses `json_array_elements_text` on `postgresql` and `sqlite_only()` + `json_each` on SQLite (wrapping execution only when `rule_code` is present so `pg_compat` still guards all other filters). Covered by `test_case_search_by_rule_code_is_postgresql_compatible` and `test_case_search_by_rule_code_filters_exact_code`.
5. `usfds-server/src/usfds_server/routers/training_router.py:221-349` (M3): `_read_bounded_body` checks `Content-Length` and streams `request.stream()` up to `max_plugin_upload_mb * 1024 * 1024` (returning `413` early before reading unbounded payload), then offloads `_register_uploaded_plugin_sync` (authz + multipart parse + `enqueue_and_wait`/`register_plugged_model`) via `run_in_threadpool` so the event loop stays responsive. Covered by `test_plugin_upload_rejects_oversize_content_length_and_stream` and `test_plugin_upload_does_not_block_event_loop`.

## 8. Open questions
- ~~Mức giới hạn mặc định cho `USFDS_MAX_PLUGIN_UPLOAD_MB` là `50` MB (trả HTTP `413`) đã phù hợp chưa?~~ → Chốt `10` MB.
- ~~Timeout mặc định cho `ScriptPluginTrainer` (`600` giây) và `execute_plugin_bundle_inference` (`300` giây)...~~ → Chốt giữ default + tham số truyền vào.
