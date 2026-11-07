# Plan: Insight & Report Module (`SUC-22`, `SUC-23`, `SUC-24`, `SUC-25`) [26-11-06]

## 1. Phân tích Kiến trúc Xử lý Dữ liệu (Data Processing Engine & Libraries)

### 1.1. Bài toán Dữ liệu của Phân hệ Insight & Report
Phân hệ **Insight & Report** tổng hợp dữ liệu xuyên suốt vòng đời vận hành của một `Project` từ 2 tầng lưu trữ:
1. **Tầng Dữ liệu Giao dịch Lớn (Columnar Parquet Files trên `IFileStorage`):**
	- Mỗi `DetectionJob` (`COMPLETED`) lưu tệp kết quả chấm điểm toàn tập tại `job.output_path` (`predictions.parquet`), chứa toàn bộ giao dịch đã quét (cả `ALLOW`, `REVIEW`, `REJECT`), điểm `model_score`, `triggered_rules`, `amount`, `timestamp`, `user_id`, và cột nhãn gốc `label` / `is_fraud` (nếu tập dữ liệu đầu vào có nhãn kiểm thử).
2. **Tầng Trạng thái Nghiệp vụ & Phán quyết Điều tra (SQLite / SQLAlchemy qua Repositories):**
	- `fraud_cases` (`Case`): Chứa các giao dịch nghi vấn đã chuyển sang điều tra, trạng thái xử lý (`OPEN`, `IN_PROGRESS`, `PENDING_CUSTOMER`, `RESOLVED_FRAUD`, `RESOLVED_LEGITIMATE`), nhãn xác minh thực tế (`verified_label`: `1` = Fraud, `0` = Legitimate, `None` = Pending), kịch bản gian lận / lý do báo động giả (`resolution_reason`), ghi chú kết luận (`resolution_summary`), `priority`, `triggered_rules`, `feature_contributions` (SHAP).
	- `entity_blacklist` (`EntityBlacklist`): Chứa danh sách thực thể bị khóa (`ACTIVE` / `REMOVED`).
	- `audit_logs` (`AuditLog`): Lịch sử kiểm toán bất biến của từng hồ sơ điều tra.
	- `rules` / `rule_versions` & `models` / `model_versions`: Siêu dữ liệu tập luật và mô hình AI.

### 1.2. Lựa chọn Engine & Thư viện Xử lý (Tuân thủ Execution Ladder)
Không cài đặt thêm bất kỳ thư viện bên thứ ba mới nào; tận dụng tối đa hệ sinh thái đã có sẵn trong `usfds-core` và `usfds-web`:

| Tầng | Engine / Thư viện sử dụng | Vai trò cụ thể trong Insight & Report | Lý do lựa chọn |
| :--- | :--- | :--- | :--- |
| **Core OLAP & Aggregation (`usfds-core`)** | **`DuckDB` (`duckdb >= 0.10.0`) + `PyArrow` (`pyarrow >= 26.0.0`)** | Truy vấn OLAP in-memory trực tiếp trên các tệp `predictions.parquet` của các `DetectionJob` kết hợp (`LEFT JOIN`) với bảng Arrow/DataFrame của `fraud_cases` theo `(project_id, event_id)`. | • **Zero-copy & Column Projection:** Chỉ đọc đúng các cột cần thiết (`event_id`, `user_id`, `timestamp`, `amount`, `model_score`, `final_action`, `triggered_rules`, `label`) từ Parquet, không nạp hàng chục cột feature vào RAM.<br>• **Vectorized SQL:** Tính cực nhanh Phễu 4 tầng, Xu hướng theo phiên/thời gian, Phân rã `AI-Exclusive` vs `Rule-Exclusive`, Phân phối 24 khung giờ (`00h–23h`), 5 phân khúc số tiền (`<$10` đến `>$2,000`), và đường cong **What-If Threshold Simulator**. |
| **Domain & Report Builder (`usfds-core`)** | **Python Standard Library (`dataclasses`, `json`, `csv`, `io`, `math`, `datetime`) + `Pandas`** | Hợp nhất kết quả từ Repositories (`ICaseRepository`, `IDetectionJobRepository`, `IBlacklistRepository`, `IAuditRepository`, `IRuleRepository`, `IModelVersionRepository`) và kết xuất nội dung báo cáo SAR 5 phần / Executive Audit Report ra JSON, Markdown (`.md`), CSV (`.csv`), HTML. | • Giữ `usfds-core` hoàn toàn độc lập với SQLAlchemy và HTTP layer (Clean Architecture).<br>• Không cần thư viện sinh PDF nặng nề ở backend (như `wkhtmltopdf` hay `reportlab` dễ lỗi font tiếng Việt trên Windows). |
| **Charts & Export (`usfds-web`)** | **`Recharts` (`^3.10.1`) + `@tanstack/react-query` + Native Print-to-PDF / Blob Download** | Hiển thị các biểu đồ tương tác (Funnel/Bar, Stacked Bar + Line ComposedChart, Attribution Bar, Score Calibration & What-If Simulator, 24h Temporal Chart, Amount Bracket Chart) và xuất PDF chuẩn hành chính qua `@media print` / `window.print()`. | • Đã cài sẵn trong `usfds-web`, đồng bộ 100% với Dark Mode Design System (`docs/design-system.md`) và hỗ trợ tiếng Việt UTF-8 hoàn hảo khi in/lưu PDF. |

---

## 2. Đồng bộ Đặc tả với Hiện trạng Codebase (Assumptions & Alignments)

Để đảm bảo không phá vỡ kiến trúc của phân hệ **Detection** và **Investigation** (đã chốt ở `.plan/investigation.md` Revision 3–5):
1. **Cấu trúc bảng điều tra (`Case` 1–1 `Transaction`):**
	- Hiện tại `fraud_cases` (`CaseModel` / `Case`) đã lưu trực tiếp từng giao dịch nghi vấn (`unique (project_id, event_id)`), kèm `amount`, `tx_timestamp`, `model_score`, `triggered_rules`, `feature_contributions`, `attributes`, và thuộc tính suy dẫn `verified_label` (`1` khi `RESOLVED_FRAUD`, `0` khi `RESOLVED_LEGITIMATE`, `None` khi chưa đóng). Do đó không tạo bảng `case_transactions` dư thừa mà truy xuất trực tiếp từ `fraud_cases`.
2. **Chế độ Nguồn Nhãn Chuẩn (`BR-IR-02` — Ground-Truth Source Toggle):**
	- Hỗ trợ tham số `label_source: "VERIFIED_ONLY" | "VERIFIED_WITH_DATASET_FALLBACK"` (mặc định `"VERIFIED_WITH_DATASET_FALLBACK"`):
		- Luôn ưu tiên nhãn `verified_label` do điều tra viên phán quyết trong `fraud_cases`.
		- Với các giao dịch chưa có phán quyết thủ công nhưng trong `predictions.parquet` có sẵn cột nhãn kiểm thử (`label` / `is_fraud`), khi bật fallback hệ thống sử dụng nhãn kiểm thử này để tính toán đầy đủ các chỉ số (`Fraud Loss Prevented`, `AI-Exclusive Catch Rate`, `Rule Leaderboard`, `What-If Simulator`, `Hourly Fraud Rate`) và hiển thị huy hiệu chú thích rõ nguồn nhãn trên UI.
3. **Trạng thái Rule & Watchlist:**
	- Tập luật giữ nguyên `RuleStatus ∈ {DRAFT, ACTIVE, INACTIVE}` và `RuleAction ∈ {ALLOW, REVIEW, REJECT}`. Nhãn chẩn đoán `Policy Health Tag` trong `SUC-23` tự động gắn `HIGH_VALUE` (`Verified Precision >= 70%`), `NOISY` (`Verified FPR >= 70%`), `MODERATE`, hoặc `UNVERIFIED`, kèm nút mở nhanh Rule Studio (`/rules`).
	- Watchlist trong `SUC-24` và `SUC-25` thống kê trực tiếp từ `entity_blacklist` (`ACTIVE` vs `REMOVED` theo từng loại thực thể `USER_ID`, `CARD_ID`, `DEVICE_ID`, `IP_ADDRESS`, `MERCHANT_ID`).
4. **Phần IV của Báo cáo SAR (`SUC-25`):**
	- Vì `SUC-21` (AI Copilot) ngoài phạm vi, Phần IV của biên bản SAR tự động tổng hợp nhận định từ mã kịch bản gian lận (`resolution_reason`), danh sách điều kiện quy tắc vi phạm (`matched_clauses`), các đặc trưng SHAP đóng góp cao nhất (`feature_contributions`), và kết luận chính thức của điều tra viên (`resolution_summary`).

---

## 3. Các Bước Triển khai Chi tiết (Implementation Steps)

### Step 1: Tài liệu Đặc tả (`docs/features/insight_report/suc-spec.md`)
- Lưu nội dung đặc tả `SUC-22`, `SUC-23`, `SUC-24`, `SUC-25` vào `docs/features/insight_report/suc-spec.md` (kèm chú thích `[26-11-06]` sau khi người dùng phê duyệt).

### Step 2: Core Analytical Engine & Service (`usfds-core`)
- Tạo gói `usfds-core/src/usfds_core/services/insight_report/`:
	- `engine.py` (`DuckDBInsightEngine`):
		- Nạp danh sách `DetectionJob` (`COMPLETED`) theo bộ lọc (`job_ids`, `date_from`, `date_to`) và đọc các cột cần thiết từ `predictions.parquet` qua `IFileStorage` + `duckdb`.
		- Kết hợp (`LEFT JOIN`) với danh sách `Case` từ `ICaseRepository` theo `event_id`.
		- Cung cấp các hàm tính toán OLAP:
			1. `compute_executive_overview(...)` (`SUC-22`): 6 KPI cards, Phễu 4 tầng (`Scanned -> Flagged -> Dispatched -> Resolved`), chuỗi xu hướng theo `DetectionJob` / thời gian, phân bổ hàng đợi Case theo `status` × `priority`.
			2. `compute_effectiveness_analysis(...)` (`SUC-23`): Phân rã `AI-Exclusive` vs `Rule-Exclusive` vs `Consensus/Overlap` (số ca & tổng tiền `$`), bảng `Rule Ground-Truth Leaderboard` (`Total Hits`, `Hit Rate %`, `Verified Cases`, `Verified TP`, `Verified FP`, `Verified FPR %`, `Fraud Value Caught $`, `Policy Health Tag`), phân phối điểm `model_score` (10 bins `0.0–1.0` tách theo `Fraud` vs `Legitimate/FP`) và bảng đường cong **What-If Threshold Simulator** (cho các mức ngưỡng từ `0.05` đến `0.95`).
			3. `compute_typology_and_patterns(...)` (`SUC-24`): Cơ cấu kịch bản gian lận (`FRAUD_REASONS`) & lý do báo động giả (`LEGITIMATE_REASONS`), phân bố khối lượng & tỷ lệ gian lận theo 24 khung giờ (`00h–23h`), phân tích 5 phân khúc giá trị giao dịch (`<$10`, `$10–$100`, `$100–$500`, `$500–$2,000`, `>$2,000`), Top `user_id` rủi ro cao nhất và thống kê `EntityBlacklist`.
	- `report_builder.py` (`ComplianceReportBuilder` — `SUC-25`):
		- `build_sar_dossier(project, case, audit_logs, blacklist_entries, prepared_by, reviewer_notes)`: Dựng cấu trúc dữ liệu chuẩn 5 phần của **Báo cáo Hoạt động Đáng ngờ (SAR)** kèm trình xuất `.md`, `.json`, `.csv`, `.html`.
		- `build_executive_audit_report(project, overview, effectiveness, patterns, prepared_by, reviewer_notes)`: Dựng **Báo cáo Tổng hợp Quản trị Rủi ro Dự án** kèm trình xuất `.md`, `.json`, `.csv`, `.html`.
	- `service.py` (`InsightReportService`): Facade điều phối các repositories và `DuckDBInsightEngine` / `ComplianceReportBuilder`, đảm bảo cô lập dữ liệu theo `project_id` (`BR-IR-01`).

### Step 3: REST API Endpoints (`usfds-server`)
- Tạo `usfds-server/src/usfds_server/schemas/insight_report_api_schemas.py` và `usfds-server/src/usfds_server/routers/insight_report_router.py` (`/api/v1/reports`):
	- `GET /api/v1/reports/overview`: Trả dữ liệu Tab 1 (`SUC-22`) + danh sách `DetectionJob` phục vụ bộ lọc phạm vi (`Scope Filter`).
	- `GET /api/v1/reports/effectiveness`: Trả dữ liệu Tab 2 (`SUC-23`), hỗ trợ lọc theo `model_version_id`, `job_ids`, `date_from`, `date_to`, `label_source`.
	- `GET /api/v1/reports/patterns`: Trả dữ liệu Tab 3 (`SUC-24`).
	- `GET /api/v1/reports/sar/{case_id}`: Xem trước hồ sơ SAR 5 phần cho một `Case` (`SUC-25`).
	- `GET /api/v1/reports/executive-summary`: Xem trước báo cáo tổng hợp quản trị rủi ro dự án (`SUC-25`).
	- `GET /api/v1/reports/export`: Tải tệp báo cáo (`report_type = sar | executive`, `format = md | json | csv | html`) với `Content-Disposition: attachment`.
- Đăng ký `insight_report_router` vào `usfds-server/src/usfds_server/api.py` và `dependencies.py`.

### Step 4: Giao diện Người dùng 4 Tab (`usfds-web`)
- Tạo `src/types/insightReport.ts` và `src/api/insightReportApi.ts`.
- Xây dựng các component trong `src/components/modules/reports/` tuân thủ `docs/design-system.md` (Dark Mode OLED, Dual-Encoding badges, Tabular numerals `font-mono tabular-nums`, Lucide icons, không hiển thị mã `SUC-xx` lên UI):
	- `ReportScopeToolbar.tsx`: Thanh lọc phạm vi chung (Chọn `All Detection Jobs` hoặc từng `DetectionJob`, khoảng thời gian `Date Range`, và chế độ nhãn `Verified Only` vs `Verified + Dataset Fallback`).
	- `ExecutiveOverviewTab.tsx` (Tab 1): 6 thẻ KPI quản trị, Biểu đồ Phễu chuyển đổi 4 tầng, Biểu đồ cột chồng & đường xu hướng tài chính (`Confirmed Fraud $`, `False Positive $`, `Pending $`, `Fraud Rate %`), và Biểu đồ phân bổ trạng thái × mức độ ưu tiên của hàng đợi Case.
	- `EffectivenessTab.tsx` (Tab 2): Thanh phân rã đóng góp `AI-Exclusive` vs `Rule-Exclusive` vs `Overlap` (Số ca & `$`), Bảng xếp hạng `Rule Ground-Truth Leaderboard` (có nhãn `HIGH VALUE` / `NOISY RULE` và nút chuyển nhanh sang `/rules`), Biểu đồ phân phối điểm mô hình và thanh trượt **What-If Threshold Simulator** (`0.10` – `0.95`) cập nhật tức thì `Estimated Recall`, `FP Reduction %`, `Review Queue Volume`.
	- `TypologiesPatternsTab.tsx` (Tab 3): Biểu đồ cơ cấu kịch bản gian lận & lý do báo động giả, Biểu đồ kết hợp khối lượng & tỷ lệ gian lận theo 24 khung giờ (`00h–23h`), Biểu đồ rủi ro theo 5 phân khúc số tiền (`<$10` đến `>$2,000`), Bảng Top chủ thể rủi ro cao & tổng quan `Blacklist`.
	- `ComplianceReportCenterTab.tsx` (Tab 4): Bộ chọn mẫu báo cáo (`SAR Dossier` theo Case hoặc `Executive Fraud & Policy Audit Report`), ô nhập `Prepared By` / `Reviewer Notes`, khung xem trước tài liệu chuẩn hành chính (**Interactive Document Preview**), và thanh công cụ xuất bản (`Print / Save PDF`, `Download .md`, `Download .json`, `Download .csv`).
- Tích hợp nút tắt **Export SAR** từ màn hình `CaseWorkbenchView.tsx` (khi hồ sơ đã xác nhận gian lận) điều hướng thẳng sang `/reports?tab=compliance&caseId=<id>`.

### Step 5: Kiểm thử & Xác minh (Verification Criteria)
- [ ] Unit test tại `usfds-core/tests/test_insight_report_service.py`: Kiểm tra tính đúng đắn của các công thức KPI tài chính, phân rã `AI-Exclusive` vs `Rule-Exclusive`, `Verified FPR %`, What-If Simulator, phân bố 24h / 5 dải tiền, và đầy đủ 5 phần của SAR (`BR-IR-01`, `BR-IR-02`, `BR-IR-03`).
- [ ] Integration API test tại `usfds-server/tests/test_insight_report_api.py`: Kiểm tra toàn bộ endpoints `/api/v1/reports/*` và xuất file.
- [ ] `npm run build` (`tsc -b && vite build`) tại `usfds-web` pass 100% không lỗi TypeScript.
