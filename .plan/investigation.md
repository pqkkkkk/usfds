# Plan: Investigation [26-10-31]

## Revision 3: Phạm vi cuối cùng đã duyệt
- Một giao dịch được gửi từ Detection tạo đúng một `Case`; unique `(project_id, event_id)`. Retry bỏ qua, không thay bằng chứng hoặc phán quyết.
- Ba entity/bảng: `Case`/`fraud_cases`, `EntityBlacklist`/`entity_blacklist`, `AuditLog`/`audit_logs` dùng chung.
- `verified_label` suy ra từ status: fraud = 1, legitimate = 0, chưa đóng = null. Mở lại lưu phán quyết cũ trong audit, nhãn hiện tại trở về null.
- Không gom, merge/split, gắn nhãn từng phần hoặc đóng hàng loạt, kể cả các case cùng user.
- Workbench truy vấn lịch sử và case cùng user; cảnh báo analyst khác chỉ có ý nghĩa khi bổ sung danh tính người dùng sau này.
- Rule Engine giữ nguyên JsonLogic, action ALLOW/REVIEW/REJECT, status DRAFT/ACTIVE/INACTIVE; không thêm risk_weight/SHADOW.
- Chỉ blacklist; gỡ chặn đổi REMOVED, không xóa vật lý. Không whitelist.
- Detection ở workstream riêng, chỉ dùng REST `POST /api/v1/cases/intake`; không chỉnh code/UI Detection, không tính model/SHAP tại Investigation.
- Network, Copilot, usfds-agent POC, auth/authz ngoài scope. Backend cung cấp actor cố định `local-analyst`; API không nhận `X-Actor`.

### Schema và REST Contract
- Case: UUID/code/project/event/user, timestamp/amount, model_score nullable, final_action, snapshots triggered_rules/contributions/attributes; artifact/job/model nguồn; status/priority/assignee/reason/summary/resolved_at/by/version/timestamps.
- Blacklist: UUID/project/type/value/status/reason/source_case_id/created_at/by/removed_at/by; partial unique active `(project_id, entity_type, entity_value)`.
- Audit: UUID/project nullable/entity_type/id/action/actor/note/details/timestamp; append/list, cùng DB transaction với thao tác chính. Scope hiện tại chỉ ghi Investigation.
- Intake: artifact cùng project với cột canonical event_id/user_id/timestamp/amount, 1–5000 transactions, final_action REVIEW/REJECT, finite score [0,1]. HTTP 201, ApiResponse với created_case_ids/accepted_count/skipped_event_ids.
- DTO sai → 422; artifact/project sai → 400/404; stale version/claim/blacklist conflict → 409. Ghi all-or-nothing.
- Priority tính trên từng transaction; heuristic theo score/action/rule count/amount, giả định artifact cùng đơn vị tiền, không phải xác suất.

### Trình tự và tiêu chí kiểm chứng
1. Đồng bộ spec/TODO và chạy focused test Case trong môi trường đã chuẩn bị.
2. Core repo interfaces + lifecycle/priority/blacklist/behavioral profile/feedback/rule draft. Reuse test_cases.py: reason validation, state/version conflict, history strictly before event, cold-start, verified feedback.
3. Infra ba ORM/repositories: unique intake và CAS update; focused check audit rollback cùng thay đổi trạng thái.
4. Server intake/list/KPIs/claim/pending/escalate/resolve/reopen/notes/workbench/feedback/draft, blacklist list/add/remove; project scope, actor backend `local-analyst`, ApiResponse. API tripwire SQLite + artifacts tạm, không cần Detection thật.
5. Frontend types/api/queries; queue filter/sort/pagination; responsive workbench với timeline/contributions/related cases; policies blacklist/feedback; Rule Studio prefill và dry-run có sẵn. Actor hiện tại cố định local-analyst, không kiểm thử nhiều danh tính qua header.
6. Focused pytest core/infra/server + npm run build + browser desktop/mobile empty/error/conflict; chạy dev server và cung cấp URL.

### Tiến độ
- [x] Spec/TODO đồng bộ; entity test pass.
- [x] Core services và focused tests pass.
- [x] Infra schema/repositories và focused tests pass.
- [x] REST contract và API tests pass (6 focused checks core/infra/server).
- [x] Frontend queue/workbench/policies tích hợp, Rule Studio prefill và source artifact.
- [x] Frontend build pass; browser empty/cache Case/chart checks và UI detector pass.
- [ ] Browser desktop/mobile mutations và Rule Studio handoff chưa kiểm chứng đầy đủ do shared browser đổi route giữa các bước. Không ghi dữ liệu giả vào DB thật.

### Điều kiện hoàn thành
- Retry không tạo case thứ hai; mỗi case phán quyết độc lập, audit cùng transaction, feedback không xem case mở là legitimate.
- Không có merge/bulk/whitelist/network/copilot trong triển khai; không sửa Detection/agent.
- Thiếu SHAP/lịch sử thể hiện unavailable, không tạo số liệu giả.
- Xin duyệt sau verification trước khi cập nhật CHANGELOG/xóa TODO.

---
## Lưu trữ: Revision 1–2 (không còn áp dụng)
Toàn bộ nội dung bên dưới là lịch sử thảo luận, không phải yêu cầu cài đặt.

## 1. Context & Facts (hiện trạng codebase)

### 1.1 Upstream Detection (SUC-15/16) — chưa đủ để sinh Case
- `BatchInferenceExecutor` chỉ ghi `fraud_probability` ra parquet; **chưa** chạy Rule Engine trong batch (hybrid), không có `total_risk_score`, `triggered_rules`, `highest_severity_action`, `rule_execution_logs`.
- Không có `detection_router` ở `usfds-server`; không có SQLite model cho `DetectionJob` (chỉ `InMemoryDetectionJobRepository`).
- `DetectionJobModule.tsx` (FE) là placeholder; chưa có nút **Send to Investigation**.

### 1.2 Rule Engine thực tế khác spec Investigation
- Rule = `Rule` + `RuleVersion` (JsonLogic), `RuleAction = ALLOW | REVIEW | REJECT`, `RuleStatus = DRAFT | ACTIVE | INACTIVE`.
- **Không có** `risk_weight`, `ALERT`, `SHADOW`, `CompositeCondition`, `condition_snapshot`, `rule_execution_logs`. Spec rule management đã được cập nhật theo JsonLogic (`[26-10-25]`), spec Investigation chưa.
- Có sẵn `RuleExecutor.backtest_dataframe` + `POST /api/v1/rules/backtest` (dùng lại cho Quick Dry-run SUC-20).

### 1.3 Investigation hiện có = POC cho agent
- `InvestigationService` (core) gắn cứng đường dẫn parquet (`test_enriched`, `eval_predictions`, model, pipeline); `event_id: int`, `user_id: int`; `CaseSummary` hardcode cột của 1 dataset e-commerce (`country`, `avs_match`, `cvv_result`...).
- `InvestigationCase` là 1 case = 1 event; không có `case_transactions`, watchlist, audit log. `IInvestigationRepository` không có bản SQLite.
- `ModelExplainabilityService` (SHAP `TreeExplainer`) — chỉ hỗ trợ tree model, gắn cứng path.
- `usfds-agent`: Google ADK + Gemini, 4 tool gọi `InvestigationService` POC qua path cứng trong `config.py`.

### 1.4 Khác
- Không có user/auth/role → `assigned_to`, `current_user`, quyền `case: review`, `rule: propose/deploy` chưa có nền.
- Router convention: `prefix="/api/v1/<resource>"`, `project_id` là query param; response `ApiResponse[T]`.
- FE: route `/investigation` + menu đã có, `InvestigationModule.tsx` là placeholder; có `recharts`, `@tanstack/react-query`, `axios`; **không có** thư viện graph; không có primitive `Modal`/`Tabs`/`Table` chung (modal viết riêng lẻ trong module).
- Enum trạng thái không thống nhất: core `InvestigationStatus` (`PENDING/UNDER_INVESTIGATION/...`), FE `types/detection.ts` (`NEW/UNDER_REVIEW/...`), spec (`OPEN/IN_PROGRESS/...`).

---

## 2. Điều chỉnh / bổ sung Use Case (đề xuất — cần duyệt trước khi sửa `docs/`)

| # | Điều chỉnh | Lý do |
| --- | --- | --- |
| A1 | **Thêm SUC-17a `Generate cases from detection result`** (hoặc chuyển rõ vào SUC-16 bước 7): input = `detection_job_id` + danh sách `event_id` (hoặc "all flagged"), gom theo `user_id`, nếu subject đã có Case `OPEN/IN_PROGRESS` thì **append** thay vì tạo mới, tính `priority_score` (BR-IV-01), snapshot SHAP + rule evidence. | Không SUC nào sở hữu logic tạo Case; BR-IV-01 cần nơi thực thi. |
| A2 | Thêm `dataset_artifact_id` vào `fraud_cases`. | Workbench (baseline, timeline) và Network cần biết đọc parquet nào khi chưa có Detection Job hoàn chỉnh. |
| A3 | Đồng bộ thuật ngữ rule theo implementation: bỏ `risk_weight`, `ALERT`, `SCORE_BOOST`, `SHADOW`, `CompositeCondition`, `mapped.*/feature.*` → dùng JsonLogic, `ALLOW/REVIEW/REJECT`, `DRAFT/ACTIVE/INACTIVE`. `max_rule_score` → `max_rule_hits` (số rule REJECT/REVIEW bị kích hoạt) **hoặc** giữ nếu Phase 0 thêm `risk_weight`. `condition_snapshot` → giá trị các `var` trong JsonLogic tại thời điểm đánh giá (`matched_clauses` đã có trong backtest). | Spec Investigation đang lệch với Rule Engine đã cài đặt. |
| A4 | Chuẩn hoá trạng thái: `status ∈ {OPEN, IN_PROGRESS, PENDING_CUSTOMER, RESOLVED_FRAUD, RESOLVED_LEGITIMATE, MERGED}`; `resolution_verdict` bỏ (suy ra từ status); `resolution_reason` là enum duy nhất, tập giá trị phụ thuộc verdict (fraud typology / false-positive reason). DEPRECATE `InvestigationStatus` cũ. | Spec có 3 bộ trạng thái chồng chéo (`CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `LEGITIMATE`, `BLOCKED`). |
| A5 | Trạng thái chủ thể (`ACTIVE/BLOCKED/WATCHLISTED`) là **giá trị suy ra** từ `entity_watchlists`, không lưu cột riêng. "Block" = bản ghi `BLACKLIST` `ACTIVE`. | Tránh 2 nguồn sự thật. |
| A6 | Thêm cột `version` (optimistic lock) vào `fraud_cases`; claim gửi `expected_version`. | Hiện thực 5c. |
| A7 | Escalate (4b) = `priority=CRITICAL` + `assigned_to` mới + audit `ESCALATED`; không thêm status. Reopen chỉ từ `RESOLVED_*` → `IN_PROGRESS`, bắt buộc lý do (BR-IV-02). | Làm rõ chuyển trạng thái. |
| A8 | Thêm `triggered_rule_codes` vào `case_transactions`. | SUC-20 kịch bản 2 (TP/FP theo rule) cần tính per-rule. |
| A9 | Defer: SUC-19 alt 3a (GNN overlay), SUC-20 1a (phân quyền propose/deploy), "watchlist tự động REJECT ở lần detection sau" (thuộc SUC-15). | Phụ thuộc hạ tầng chưa có (GNN, RBAC, hybrid detection). |
| A10 | Actor: chưa có auth → `actor` lấy từ header `X-Actor` (FE cấu hình tên analyst, mặc định `local-analyst`). | Desktop single-user; đủ cho audit log. |

---

## 3. Phân pha (minimal-first)

| Phase | Nội dung | Phụ thuộc |
| --- | --- | --- |
| **P0** | Nguồn dữ liệu cho Case (xem Câu hỏi Q1) | — |
| **P1 (MVP)** | SUC-17a + SUC-17 + SUC-18 (queue, claim, workbench, resolve, verified_label, block → watchlist, audit) | P0 |
| **P2** | SUC-20 (watchlists CRUD, rule feedback table, quick rule draft → Rule Studio) | P1 |
| **P3** | SUC-19 (network graph) | P1 |
| **P4** | SUC-21 (AI Copilot, refactor `usfds-agent`) | P1 |

---

## 4. Back-end

### 4.1 `usfds-core`
- **Entities** `domain/entities/investigation.py` (dataclass, pure):
	- `FraudCase`, `CaseTransaction`, `WatchlistEntry`, `CaseAuditLog`.
	- `InvestigationCase` → comment `DEPRECATED` (agent POC còn dùng tới P4).
- **Enums** `enums.py`: `CaseStatus`, `CaseResolutionReason`, `WatchlistType`, `WatchlistStatus`, `WatchlistEntityType`, `CaseAuditAction`; tái dùng `RiskLevel` cho `priority`. `InvestigationStatus` → `DEPRECATED`.
- **Repository interfaces** `repositories/`:
	- `base_case_repo.py` → `ICaseRepository`: `save`, `get_by_id`, `list_by_project(filters, sort, page)`, `get_kpis`, `find_active_by_subject`, `next_case_code`, `save_transactions`, `list_transactions`, `add_audit_log`, `list_audit_logs`.
	- `base_watchlist_repo.py` → `IWatchlistRepository`: `save`, `list_by_project`, `find_active(entity_type, entity_value)`, `update_status`.
	- In-memory impl trong `in_memory_repos.py` cho test.
- **Services** `services/investigation/`:
	- `priority.py`: `compute_priority_score(...) -> (score, RiskLevel)` — hàm thuần BR-IV-01.
	- `case_service.py` `CaseManagementService` (SUC-17a, 17): `generate_cases`, `list_cases`, `get_kpis`, `claim` (version check → `CaseConflictError`), `assign`, `merge` (re-link tx, recompute aggregates, mark `MERGED`), `bulk_resolve`, `reopen`.
	- `case_review_service.py` `CaseReviewService` (SUC-18): `get_workbench` (subject + baseline + evidence + timeline + deviation), `add_note`, `set_pending_customer`, `escalate`, `label_transaction` (4a), `resolve` (BR-IV-03 validate ≥10 ký tự; set `verified_label` cho tx chưa gắn tay; tạo watchlist BLACKLIST; audit; 1 transaction DB).
	- `behavior_profile.py`: tính baseline từ DataFrame đã map (cột canonical `event_id/timestamp/amount/user_id` + optional `device_id/ip_address/merchant_id/merchant_category`), cửa sổ 30/90 ngày tính **trước** timestamp giao dịch nghi vấn; cold-start → peer baseline toàn tập (1a). Thay cho `DuckDBInvestigationEngine` hardcode.
	- `explainability.py`: tổng quát hoá `ModelExplainabilityService` nhận model + pipeline từ `ModelVersion` artifact; SHAP tính **lúc tạo case** và lưu vào `transaction_snapshot.shap_top_features`; model không phải tree → trả `explanation_available=False`.
	- `watchlist_service.py` (P2): add/remove/list, BR-IV-07, hết hạn theo `expires_at` (lọc khi đọc).
	- `rule_feedback_service.py` (P2): aggregate `case_transactions.triggered_rule_codes` × status → `cases_triggered / TP / FP / verified_fpr`; `build_rule_draft(case_id)` → JsonLogic `and` từ các feature lệch baseline nhất.
	- `network_service.py` (P3): `build_subgraph(project_id, artifact_id, seed_type, seed_value, hops∈{1,2}, time_from, time_to, entity_types, hide_supernodes)`; cạnh user–entity gộp `tx_count`, `total_amount`; overlay trạng thái node từ cases + watchlist; phát hiện hub (degree ≥ N trong window); cắt top-50 khi expand super-node, tổng ≤ 200 node (BR-IV-05); thiếu cột thực thể → lỗi có thông điệp 2a.
	- `copilot.py` (P4): `ICaseCopilot` interface + `CaseInvestigationContext` builder (đóng gói từ workbench).

### 4.2 `usfds-infra`
- `database/models.py`: `FraudCaseModel` (`__mapper_args__ = {"version_id_col": version}`), `CaseTransactionModel`, `EntityWatchlistModel` (partial unique index `sqlite_where=status=='ACTIVE'` — hiện thực BR-IV-07 ở tầng DB), `CaseAuditLogModel`. UUID → `String(36)`, JSONB → `JSON`.
- `database/repositories.py`: `SqliteCaseRepository`, `SqliteWatchlistRepository`; map `StaleDataError` → `CaseConflictError`.
- Test: `tests/test_case_repositories.py` (SQLite `:memory:`).

### 4.3 `usfds-server`
- `routers/investigation_router.py` (`/api/v1/cases`), `routers/watchlist_router.py` (`/api/v1/watchlists`, P2), `routers/network_router.py` (`/api/v1/network`, P3); schema `schemas/investigation_api_schemas.py`; wiring trong `dependencies.py`; header `X-Actor`.

| Method | Path | SUC |
| --- | --- | --- |
| POST | `/api/v1/cases/generate` | 17a |
| GET | `/api/v1/cases?project_id&status&priority&assigned_to&rule_code&min_score&max_score&min_amount&max_amount&q&sort&page&size` | 17 |
| GET | `/api/v1/cases/kpis?project_id` | 17 |
| POST | `/api/v1/cases/merge` · `/api/v1/cases/bulk-resolve` | 17 (5a, 5b) |
| POST | `/api/v1/cases/{id}/claim` (409 khi conflict) · `/assign` · `/escalate` · `/pending-customer` · `/reopen` | 17, 18 |
| GET | `/api/v1/cases/{id}` · `/workbench` · `/audit-logs` | 18 |
| POST | `/api/v1/cases/{id}/notes` · `/resolve` | 18 |
| PATCH | `/api/v1/cases/{id}/transactions/{tx_id}/label` | 18 (4a) |
| GET/POST/DELETE | `/api/v1/watchlists` | 20 |
| GET | `/api/v1/cases/rule-feedback?project_id` · `/api/v1/cases/{id}/rule-draft` | 20 |
| GET | `/api/v1/network/subgraph` · POST `/api/v1/cases/{id}/transactions/add-linked` · POST `/api/v1/watchlists/bulk` | 19 |
| POST | `/api/v1/cases/{id}/copilot` (503 nếu thiếu `GOOGLE_API_KEY`) | 21 |

### 4.4 `usfds-agent` (P4)
- `GeminiCaseCopilot(ICaseCopilot)`: nhận `CaseInvestigationContext` (không đọc file), trả JSON 3 phần (`why_flagged`, `key_anomalies`, `next_steps_and_draft`). Tool cũ + `config.py` path cứng → `DEPRECATED`.
- Server wiring: agent là optional dependency; `GOOGLE_API_KEY` khai báo trong `.env.example`. BR-IV-08: endpoint chỉ ghi `ai_investigation_brief`, không đổi status.

### 4.5 Tests (1 tripwire / logic không tầm thường)
- core: `test_case_management.py` (priority bucket, claim conflict, merge recompute, generate append vào case mở), `test_case_review.py` (resolve validate + verified_label + blacklist, partial label), `test_behavior_profile.py` (baseline + cold-start), `test_watchlist_service.py` (BR-IV-07), `test_rule_feedback.py`, `test_network_service.py` (2-hop, cap 200).
- infra: `test_case_repositories.py`. server: `test_investigation_api.py`.

---

## 5. Front-end (`usfds-web`)

### 5.1 Data layer
- `src/types/investigation.ts` (FraudCase, CaseTransaction, CaseKpis, CaseFilters, Workbench, Watchlist, RuleFeedbackRow, Subgraph, CopilotBrief). `InvestigationStatus/FraudAlert` trong `types/detection.ts` → `DEPRECATED`.
- `src/api/investigationApi.ts`, `watchlistApi.ts`, `networkApi.ts` theo pattern `apiClient`; interceptor gắn `X-Actor`.
- Hooks react-query: `useCases`, `useCaseKpis`, `useCaseWorkbench`, mutations (`claim/resolve/merge/...`) với invalidate.

### 5.2 Routes (`InvestigationModule.tsx` → nested routes)
- `/investigation` → `CaseQueueView`
- `/investigation/cases/:caseId` → `CaseWorkbenchView` (tab **Evidence** | **Network**)
- `/investigation/network` → `NetworkExplorerView` (seed tự nhập)
- `/investigation/policies` → `PolicyWatchlistView` (tab **Watchlists** | **Rule Feedback**)

### 5.3 Components `src/components/modules/investigation/`
- **SUC-17**: `CaseKpiCards`, `CaseFilterBar` (debounce search, `useDebounce` có sẵn), `CaseQueueTable` (checkbox multi-select, model/rule score bar, priority/status badge có icon + text), `MergeCasesModal`, `BulkResolveModal`; toast khi claim 409.
- **SUC-18** (grid 25/50/25): `SubjectBaselinePanel` (cold-start badge), `TriggerEvidencePanel` (`ShapBarChart` – recharts `BarChart` ngang; rule list + snapshot), `TransactionTimelineChart` (recharts `ScatterChart`, xám/đỏ), `BaselineComparisonTable` (tô đỏ + icon cảnh báo), `ResolutionPanel` (verdict → reason enum, mitigation checkbox, summary ≥10 ký tự, validate client + server), `CaseAuditTrail`, auto-advance toggle.
- **SUC-20**: `WatchlistTable`, `AddWatchlistModal`, `RuleFeedbackTable` (FPR > 80% highlight → link Rule Studio), nút **Create Rule from Case** → điều hướng `/rules` với JsonLogic prefill (tái dùng `RuleStudioWorkspace` + `RuleDryRunWorkspace`, không build builder mới).
- **SUC-19**: `NetworkGraphCanvas` (thư viện graph — Q3), `GraphToolbar` (hops, entity type filter, time slider, hide super-nodes), `EdgeTransactionInspector` (tái dùng `InspectorDrawer`), action bar **Add to Case** / **Block Selected**.
- **SUC-21**: `CopilotPanel` trong cột phải (generate, loading, 3 section, **Copy to Resolution Notes**, nhãn "Advisory only").
- **Detection** (sau P0): nút **Send to Investigation** trong `DetectionJobModule` result step.

### 5.4 Verification
- `npm run build` (tsc -b && vite build) sạch lỗi; kiểm tra UI thủ công trên dữ liệu seed.

---

## 6. Câu hỏi mở (chặn trước khi code)
- **Q1 (P0)** Nguồn tạo Case: (a) hoàn thiện tối thiểu SUC-15/16 hybrid (batch chạy model + active rules, lưu kết quả, detection router) rồi mới làm Investigation; (b) tạm thời: `generate_cases` nhận trực tiếp `dataset_artifact_id` + `model_version_id`, tự chạy model + `RuleExecutor` trên artifact; (c) chỉ seed từ artifact POC hiện có.
- **Q2** Actor/auth: dùng header `X-Actor` + bỏ qua phân quyền?
- **Q3** Thư viện graph: `cytoscape` (box/lasso select, layout phong phú) hay `react-force-graph-2d` (nhẹ, canvas)?
- **Q4** Phạm vi lượt này: chỉ P1 (MVP) hay P1→P4?
- **Q5** Giữ `max_rule_score` (cần thêm `risk_weight` vào `RuleVersion`) hay đổi thành `max_rule_hits`?
- **Q6** Duyệt cập nhật `docs/features/investigation/suc-spec.md` theo mục 2?

## 7. Success Criteria
- [ ] Spec Investigation cập nhật theo mục 2 (sau duyệt, tag `[26-10-31]`).
- [ ] P1: tạo case từ nguồn P0, queue lọc/sort/KPI, claim có optimistic lock, workbench 3 cột, resolve ghi `verified_label` + blacklist + audit; test core/infra/server pass.
- [ ] P2–P4 theo phạm vi duyệt ở Q4.
- [ ] `pytest` (core, infra, server) và `npm run build` không lỗi.
