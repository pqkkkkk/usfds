# USFDS As-Built Architecture
<!-- [26-11-27] Created. [26-11-28] English rewrite; single routing source; principles, INV-016, ERD added; research doc moved out. -->

`docs/arch/` is the **source of truth for the architecture as it runs today**. It serves human reviewers (checking plans and PRs against module boundaries, contracts and risks) and AI agents (context before `usfds-plan`, `usfds-task-workflow`, `usfds-review`).

This file is the **only routing table** for architecture docs. Other entry points (`AGENTS.md`, skills) link here instead of copying it.

## 1. Layers

| Layer | Document | Answers |
|---|---|---|
| 0 — Navigation | `README.md` (this file) | What do I read when I touch X? |
| 1 — Overview | [`01-context-and-runtime.md`](01-context-and-runtime.md) | Which packages, processes and storage exist; runtime modes; queues; storage key layout. |
| 1 — Overview | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) | Training and Inference → Investigation → Insight flows; shared contracts `C1–C5`; state machines. |
| 1 — Overview | [`04-data-model-erd.md`](04-data-model-erd.md) | Which tables exist, how they relate, which module owns them. |
| 2 — Modules | [`modules/`](modules/) (6 bounded contexts) | What each module owns, which contracts it provides, its state machines and traps. |
| 3 — Rules | [`03-system-invariants.md`](03-system-invariants.md) | Architecture principles (`P-NN`) and invariants (`INV-NNN`) that no change may break, and how each is enforced. |

[`docs/research/high-level-design.md`](../research/high-level-design.md) is the original research design (K8s, MinIO, Apache AGE). It is **not** as-built; when it disagrees with this folder, this folder wins.

## 2. Routing: touching X → read first

| Task touches... | Read (in order) | Business spec (`docs/features/`) |
|---|---|---|
| **Every task** (plan & review) | [`03-system-invariants.md`](03-system-invariants.md) | — |
| Auth, users, roles, RBAC, project membership, presigned storage auth | [`01`](01-context-and-runtime.md) → [`modules/auth-and-access.md`](modules/auth-and-access.md) | [`project_management/suc-spec.md`](../features/project_management/suc-spec.md) |
| Dataset ingestion, schema mapping, system metadata, feature management, preprocessing | [`02`](02-data-and-lifecycle-flows.md) → [`modules/data-and-features.md`](modules/data-and-features.md) | [`data_management/`](../features/data_management/), [`feature_management/context-modeling.md`](../features/feature_management/context-modeling.md), [`critical_changes.md`](../features/critical_changes.md) |
| Model training, built-in / plugin trainers, model versions, lineage, remote compute | [`01`](01-context-and-runtime.md) → [`02`](02-data-and-lifecycle-flows.md) → [`modules/training-and-models.md`](modules/training-and-models.md) | [`detection/suc-spec.md`](../features/detection/suc-spec.md) |
| Detection jobs, batch inference, rule engine, JsonLogic, backtest | [`02`](02-data-and-lifecycle-flows.md) → [`modules/detection-and-rules.md`](modules/detection-and-rules.md) | [`detection/suc-spec.md`](../features/detection/suc-spec.md) |
| Cases, blacklist, behavior profile, network graph | [`02`](02-data-and-lifecycle-flows.md) → [`modules/investigation-and-graph.md`](modules/investigation-and-graph.md) | [`investigation/suc-spec.md`](../features/investigation/suc-spec.md) |
| ProjectWarehouse, insight metrics, SAR / executive reports | [`02`](02-data-and-lifecycle-flows.md) → [`modules/insight-and-warehouse.md`](modules/insight-and-warehouse.md) | [`insight_report/suc-spec.md`](../features/insight_report/suc-spec.md) |
| Tables, columns, migrations | [`04-data-model-erd.md`](04-data-model-erd.md) → owning module | — |
| Worker queues, BullMQ, storage backend, Docker / env | [`01`](01-context-and-runtime.md) | — |

## 3. Stop Rule (level of detail)

- **Write in `docs/arch/`:**
  - Responsibility boundaries between packages and the 6 modules (who owns which table / storage prefix).
  - Shared contracts read or written by ≥ 2 modules (artifact formats, system columns, warehouse schema, queue payloads, `project_id` / `user_id` conventions).
  - State machines of core entities.
  - Principles, invariants, and known cross-module traps.
- **Do not write in `docs/arch/`:**
  - Every ORM column, function parameter, React component, or a function's internal algorithm (code, docstrings and `docs/features/**` own those).
  - Line numbers (`file.py:NNN`) — they drift. Name the file or symbol.
  - Bug details. Open bugs live only in `docs/issues/`; arch docs reference them by `ISS-NNN` and state the architectural consequence in one line.
- **Test:** if a line must change because an internal name changed inside one module → too detailed, remove it. If changing it could silently break another module while local tests stay green → it must be written here.

## 4. Doc-sync policy (`INV-015`)

Any PR that changes one of the following updates `docs/arch/` in the same PR, with a `[YY-MM-DD]` comment:
- Package, router, BullMQ queue/job, storage prefix, or runtime mode added/removed → `01-context-and-runtime.md`.
- Data flow, artifact / warehouse / schema contract, or state machine → `02-data-and-lifecycle-flows.md` and `modules/<module>.md`.
- Table or relation added/removed/renamed → `04-data-model-erd.md`.
- Principle or invariant added/changed/removed, or moved from review to an automated guard → `03-system-invariants.md`.
