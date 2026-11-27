# Đặc tả use case phân hệ Insight & Report [26-11-06] [26-11-27]

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Task ID: TASK-106 · Upgrade Issue: `ISS-046` <!-- [26-11-27] -->

---

# 1. Tổng quan nghiệp vụ Phân tích & Báo cáo (Insight & Report)

Phân hệ **Insight & Report** hiện thực hóa nghiệp vụ **BUC-05 (Lập báo cáo)** và đóng vai trò cung cấp căn cứ định lượng cho **BUC-04 (Cập nhật, tối ưu chính sách rủi ro)**.

Khác với màn hình kết quả của từng phiên quét đơn lẻ (`SUC-16` ở phân hệ Detection) hay màn hình đánh giá mô hình trên tập kiểm thử tĩnh (`SUC-09`), phân hệ **Insight & Report** tổng hợp dữ liệu xuyên suốt toàn bộ vòng đời vận hành của dự án (**Detection Jobs $\rightarrow$ Project Fact Warehouse $\rightarrow$ Investigation Cases & Ground Truth Verdicts $\rightarrow$ Rules & Models**) để giải quyết **4 bài toán quản trị rủi ro cốt lõi** <!-- [26-11-27] -->:

1. **Đo lường Hiệu quả Bảo vệ Tài chính, Gian lận Lọt lưới & Ma sát Khách hàng (Financial Protection vs. Missed Fraud vs. Customer Insult):** <!-- [26-11-27] -->
	- Đặt song song **Tiền gian lận đã ngăn chặn (`Confirmed Fraud Prevented $` & `Value Detection Rate — VDR %`)**, **Tiền gian lận bị lọt lưới (`Missed Fraud $` & `Net Fraud Loss bps`)**, và **Ma sát khách hàng (`Customer Insult Rate = FP / (TN + FP)`)** tách rõ giữa **Chặn nhầm (`Hard False Decline` từ `REJECT`)** và **Xem xét nhầm (`Soft Review Friction` từ `REVIEW`)**, cùng **Tỷ lệ Cảnh báo trên mỗi Ca gian lận thật (`Alert-to-Fraud Ratio`)**.
2. **Đánh giá Hiệu năng Thực tế, Kiểm định Mô hình AI & Tối ưu Ngưỡng Kép (Post-Investigation Attribution, Model Validation & Dual-Threshold Optimization):** <!-- [26-11-27] -->
	- Đối chiếu phán quyết của từng `Rule` và từng `ModelVersion` với nhãn thực tế (`verified_label` ưu tiên, hỗ trợ fallback nhãn tập dữ liệu theo `BR-IR-02`) để chỉ ra:
		- **Rule Ground-Truth Leaderboard:** Phân biệt **High-Value Rules** (`Precision >= 70%`), **Noisy Rules** (`False Alert Rate — FAR >= 70%`), **Bắt Độc nhất (`Unique Catch $ & count`)** nhằm nhận diện luật dư thừa, gắn cờ **`Mẫu nhỏ (n < 30)`** tránh kết luận vội, kèm xem nhanh **Top mẫu giao dịch FP / FN**.
		- **AI-Exclusive Catch Rate:** Tỷ lệ gian lận mà chỉ mô hình học máy phát hiện được (không vi phạm luật thủ công nào).
		- **Model Validation & Drift:** Biểu đồ **Calibration Reliability Curve** (`Uniform` & `Equal-Count` + `Brier Score`, `ECE`), đường cong **Top-K Lift / Cumulative Gain** & **KS Statistic**, **So sánh phiên bản mô hình (`Model Version Comparison`)**, và **Score Drift (`PSI` — Population Stability Index)** theo từng khoảng điểm.
		- **Dual-Threshold & Cost-Aware Simulator:** Mô phỏng đồng thời 2 ngưỡng (`τ_review` cho `REVIEW`, `τ_reject` cho `REJECT`), hiển thị song song **cả 2 chế độ Kết hợp AI + Luật (Hybrid) và Chỉ AI (Model-only)** kèm 3 chế độ gợi ý tự động (Sức tải duyệt, Precision mục tiêu, Tối ưu Lợi ích ròng `Net Savings $`).
3. **Nhận diện Xu hướng, Phân khúc Thực thể Rủi ro & Tác động Watchlist (Typologies, Temporal & Multi-Entity Segment Hit-Rate):** <!-- [26-11-27] -->
	- Phân tích cơ cấu kịch bản gian lận (`FRAUD_REASONS`), nguyên nhân báo giả (`LEGITIMATE_REASONS`), phân bố 24 khung giờ (tách riêng đường `Confirmed Fraud Rate %` và `Flagged Rate %`), **Ma trận Phân khúc Rủi ro (`Segment Alert Hit-Rate`)** theo 6 chiều (`Khoảng số tiền`, `Ngành hàng MCC`, `Merchant`, `Thiết bị`, `Địa chỉ IP`, `Thẻ`), Top `user_id` rủi ro (với tổng giao dịch thật của user), và tác động chặn của `entity_blacklist`.
4. **Giám sát Vận hành Điều tra (Case SLA) & Xuất Báo cáo Tuân thủ (SAR / Executive Audit Reporting):** <!-- [26-11-27] -->
	- Theo dõi phễu chuyển đổi 4 tầng đơn điệu giảm (`Scanned → Flagged → Dispatched Cases → Resolved Cases`), tồn đọng hàng đợi theo trạng thái/ưu tiên/tuổi hồ sơ (**Backlog Aging**), **MTTR (`P50` / `P90`)**, **Tỷ lệ quá hạn SLA** (`CRITICAL ≤ 4h`, `HIGH ≤ 24h`, `MEDIUM ≤ 72h`), **Hiệu suất & độ đồng đều theo điều tra viên**, và xuất **SAR Dossier 5 phần** / **Executive Audit Report** ra HTML/In PDF chuẩn bảng biểu (`@media print`), `.md`, `.csv`, `.json`.

---

# 2. Tóm tắt danh mục Use Case hệ thống

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt |
| --- | --- | --- | --- |
| **SUC-22** | **View executive financial, missed-fraud & case SLA dashboard** | Risk Manager, Fraud Analyst | Xem 6 KPI điều hành (`Gross Volume`, `Prevented $ & VDR`, `Missed Fraud $ & bps`, `Customer Insult Rate` tách `REJECT`/`REVIEW`, `Precision & Alert:Fraud`, `Case SLA & MTTR`), xu hướng theo ngày giao dịch (`tx_timestamp`), phễu 4 tầng đơn điệu giảm, phân tích tuổi tồn đọng (`Backlog Aging`) và hiệu suất điều tra viên. <!-- [26-11-27] --> |
| **SUC-23** | **Analyze rule effectiveness, model validation & dual-threshold simulation** | Data Scientist, Risk Manager, Fraud Analyst | Phân tích đóng góp AI vs. Luật, bảng xếp hạng luật (`Precision`, `FAR`, `Unique Catch`, cờ `Mẫu nhỏ n < 30`, mẫu FP/FN), hiệu chỉnh xác suất (`Calibration Curve`, `Brier`, `ECE`), đường cong bắt Top-K (`Lift/Gain`, `KS`), so sánh phiên bản mô hình & `Score Drift (PSI)`, và bộ mô phỏng ngưỡng kép (`τ_review`, `τ_reject`) hiển thị song song **Hybrid** và **Chỉ AI** với ước tính `Net Savings $`. <!-- [26-11-27] --> |
| **SUC-24** | **Analyze fraud typologies, temporal profile & multi-entity risk segments** | Fraud Analyst, Risk Manager | Khám phá loại hình gian lận (`FRAUD_REASONS`), nguyên nhân FP (`LEGITIMATE_REASONS`), phân bố 24 giờ (2 đường tách biệt `Fraud Rate` vs `Flag Rate`), Ma trận Phân khúc (`Segment Hit-Rate`: Khoảng tiền, `MCC`, `Merchant`, `Device`, `IP`, `Card` kèm `Lift` & cờ `Mẫu nhỏ`), Top `user_id` rủi ro và tác động thực tế của `EntityBlacklist`. <!-- [26-11-27] --> |
| **SUC-25** | **Generate & export SAR and executive compliance reports** | Fraud Analyst, Risk Manager | Tự động tổng hợp và xuất hồ sơ Báo cáo Hoạt động Đáng ngờ (`SAR Dossier` chuẩn 5 phần) cho từng vụ việc hoặc Báo cáo Quản trị Rủi ro Định kỳ (`Executive Fraud & Policy Audit Report` đồng bộ đầy đủ KPI mới) ra định dạng HTML/In PDF chuẩn A4, Markdown (`.md`), CSV (`.csv`), JSON (`.json`). <!-- [26-11-27] --> |

---

# 3. Chi tiết đặc tả Use Case & Đồng bộ Kiến trúc (`[26-11-06]` · cập nhật `[26-11-27]`)

## 3.1. Kiến trúc Xử lý Dữ liệu (`ProjectWarehouse` + `DuckDBInsightEngine` + Repositories) <!-- [26-11-27] -->
- **Tầng OLAP (`usfds-core`):** Sử dụng `DuckDB` in-memory có giới hạn tài nguyên (`create_bounded_duckdb_connection`) đọc trực tiếp bảng sự kiện chuẩn hóa `ProjectWarehouse` (`warehouse/{project_id}/fact_transactions/job_{job_id}.parquet`, đã loại trùng theo lần quét mới nhất trên mỗi `event_id` và tích hợp sẵn 5 cột thực thể mở rộng `device_id`, `ip_address`, `card_id`, `merchant_id`, `merchant_category`), sau đó `LEFT JOIN` với `fraud_cases` theo `(project_id, event_id)`.
- **Đồng bộ Schema & Metadata (`[26-11-27]`):**
	- `fraud_cases` (`Case`): đại diện 1 giao dịch nghi vấn (`unique (project_id, event_id)`), lưu `amount`, `tx_timestamp`, `model_score`, `triggered_rules`, `feature_contributions`, `attributes`, `priority`, `created_at`, `resolved_at`, `resolved_by`, `resolution_reason`, `resolution_summary`, và `verified_label` (`1` khi `RESOLVED_FRAUD`, `0` khi `RESOLVED_LEGITIMATE`, `None` khi đang mở).
	- `entity_blacklist` (`ACTIVE` / `REMOVED`) và `audit_logs` (`entity_type = 'CASE'`).
	- `rules` / `rule_versions` (`RuleStatus ∈ {DRAFT, ACTIVE, INACTIVE}`, `RuleAction ∈ {ALLOW, REVIEW, REJECT}`).
	- `models` / `model_versions`: dùng để hiển thị tên & phiên bản mô hình thực tế thay vì hardcode tên thuật toán trên UI.

## 3.2. Quy tắc Nghiệp vụ (Business Rules)
- **BR-IR-01 (Cross-Project Isolation):** Toàn bộ số liệu thống kê, biểu đồ và báo cáo SAR chỉ được truy xuất trong phạm vi `project_id` đang làm việc (`BR-PM-06`).
- **BR-IR-02 (Ground-Truth Priority in Metrics):** Khi tính toán các chỉ số độ chính xác thực tế, hệ thống luôn ưu tiên nhãn đã được điều tra viên xác nhận (`verified_label` từ `fraud_cases`); với các giao dịch chưa qua điều tra thủ công nhưng tập dữ liệu gốc có sẵn cột nhãn kiểm thử (`label` / `is_fraud`), hệ thống hỗ trợ chế độ đối chiếu nhãn tập dữ liệu (*Dataset Ground-Truth Fallback*) kèm chú thích nguồn nhãn rõ ràng trên giao diện.
- **BR-IR-03 (SAR Audit Completeness):** Mỗi báo cáo SAR được xuất ra bắt buộc đính kèm mã định danh hồ sơ (`case_id`, `case_code`), dấu thời gian khởi tạo báo cáo (`generated_at`), và trích xuất nguyên vẹn lịch sử phán quyết (`audit_logs`) của chuyên viên để đảm bảo tính toàn vẹn kiểm toán.
- **BR-IR-04 (Label-Availability Honesty & Small-Sample Guard — `[26-11-27]`):**
	- Ở chế độ `VERIFIED_ONLY` (khi giao dịch không bị gắn cờ `is_flagged = 0` không có nhãn xác minh), các chỉ số phụ thuộc False Negative (`Missed Fraud $`, `VDR`, `Net Fraud Loss bps`) và True Negative (`Customer Insult Rate`) phải trả `null` (`ground_truth_coverage = "FLAGGED_ONLY"`) và hiển thị `—` kèm giải thích trên UI — tuyệt đối không trả `0` gây hiểu nhầm.
	- Mọi luật trong `Rule Leaderboard` hoặc phân khúc trong `Segment Hit-Rate` có số mẫu xác minh `< 30` (`n < 30`) phải được gắn cờ cảnh báo `Mẫu nhỏ (is_small_sample = true)`.
- **BR-IR-05 (Case SLA Thresholds — `[26-11-27]`):** Ngưỡng SLA mặc định đo lường thời gian từ lúc tạo hồ sơ đến lúc xử lý (`resolved_at - created_at`, hoặc tuổi hồ sơ hiện tại đối với case đang mở): `CRITICAL ≤ 4h`, `HIGH ≤ 24h`, `MEDIUM ≤ 72h` (`LOW` không tính quá hạn SLA cứng).

## 3.3. Từ điển Metrics & Công thức Chuẩn FDS (`[26-11-27]`)

| Nhóm | Metric | Công thức chuẩn | Ý nghĩa & Ngưỡng tham khảo |
| --- | --- | --- | --- |
| **Tài chính & Lọt lưới** | `Value Detection Rate (VDR)` | $\frac{\text{Prevented \$}}{\text{Prevented \$} + \text{Missed Fraud \$}}$ | Tỷ lệ giá trị tiền gian lận chặn được (tốt: `≥ 75–85%`). |
| **Tài chính & Lọt lưới** | `Net Fraud Loss (bps)` | $\frac{\text{Missed Fraud \$}}{\text{Gross Scanned Volume \$}} \times 10{,}000$ | Tỷ lệ thất thoát trên tổng doanh số (`1 bps = 0.01%`; chuẩn ngành thẻ `< 5–10 bps`). |
| **Ma sát Khách hàng** | `Customer Insult Rate` | $\frac{\text{FP}}{\text{TN} + \text{FP}}$ (tách `Hard False Decline` từ `REJECT` và `Soft Friction` từ `REVIEW`) | Tỷ lệ giao dịch của khách hàng hợp lệ bị làm phiền nhầm (`< 0.5–1%`). |
| **Hiệu quả Cảnh báo** | `Verified Precision` & `Alert:Fraud` | $\frac{\text{TP}}{\text{TP} + \text{FP}}$ và $\frac{\text{TP} + \text{FP}}{\text{TP}}$ | Độ sạch của hàng đợi cảnh báo (thực tế `2:1` – `5:1`). |
| **Vận hành Điều tra** | `MTTR (P50 / P90)` & `Backlog Aging` | Trung vị & P90 của `(resolved_at - created_at)` (giờ); phân nhóm tuổi `< 4h`, `4–24h`, `1–3d`, `> 3d` | Tốc độ xử lý hồ sơ & phát hiện hồ sơ tồn đọng quá SLA (`BR-IR-05`). |
| **Tập luật** | `False Alert Rate (FAR)` | $\frac{\text{FP}}{\text{TP} + \text{FP}} = 1 - \text{Precision}$ | Tỷ lệ báo giả trên các ca luật nổ (`≥ 70%` → `NOISY`). |
| **Tập luật** | `Unique Catch ($ & count)` | Gian lận có `len(triggered_rules) == 1` và `has_ai_hit == 0` | Đóng góp độc nhất của luật; `Unique Catch = 0` + `FP` cao → luật dư thừa. |
| **Mô hình AI** | `Calibration Curve`, `Brier`, `ECE` | `Observed Fraud Rate` vs `Mean Predicted Score` trên 10 bin (`Uniform` & `Equal-Count`); $\text{Brier} = \frac{1}{N}\sum(p_i - y_i)^2$ | Kiểm định độ tin cậy của điểm xác suất AI (`ECE < 0.05`, `Brier → 0`). |
| **Mô hình AI** | `Top-K Lift / Gain` & `KS Statistic` | `% Fraud $` & `% Fraud Count` tại Top `1%, 2%, 5%, 10%, 20%`; $\text{KS} = \max|\text{CDF}_{\text{fraud}} - \text{CDF}_{\text{legit}}|$ | Năng lực xếp hạng rủi ro của mô hình (`KS`: `0.2–0.4` đạt, `> 0.4` tốt). |
| **Giám sát Drift** | `Score Drift (PSI)` | $\sum (p_{\text{cur},i} - p_{\text{base},i}) \ln(p_{\text{cur},i} / p_{\text{base},i})$ (sàn `0.0001`, 10 bin) | Đo dịch chuyển phân phối điểm (`< 0.10` ổn định · `0.10–0.25` cảnh báo · `> 0.25` cần retrain). |
| **Mô phỏng Ngưỡng** | `Dual-Threshold` & `Net Savings ($)` | $\text{Prevented \$} - (\text{Review Count} \times C_{\text{review}}) - (\text{Hard FP \$} \times w_{\text{decline}})$ | So sánh song song **Hybrid (AI + Luật)** và **Chỉ AI** theo 2 ngưỡng `τ_review` / `τ_reject`. |
| **Phân khúc Rủi ro** | `Segment Alert Hit-Rate` & `Lift` | Theo từng chiều (`Amount`, `MCC`, `Merchant`, `Device`, `IP`, `Card`): `Alert Rate`, `Hit Rate`, `Detection Rate`, `Missed $`, `Lift` | Khoanh vùng điểm nóng gian lận (`Lift ≥ 2.0×`) hoặc ổ báo động giả. |

## 3.4. Quy chuẩn Tổ chức Hiển thị 4 Tab (`usfds-web` — `[26-11-27]`)
- **Nguyên tắc chung:** 100% tiếng Việt, bỏ toàn bộ tên thuật toán hardcode (như `XGBoost`), tuân thủ `docs/design-system.md` (Dual-Encoding icon + badge, `font-mono tabular-nums`), mọi KPI/Chart có nút **`MetricInfoTooltip`** giải thích công thức và cách đọc ngắn gọn. Giữ nguyên `ReportScopeToolbar` lọc theo khoảng thời gian giao dịch (`tx_timestamp`) và chế độ nguồn nhãn (`BR-IR-02`).
- **Tab 1 (`ExecutiveOverviewTab`):** 6 KPI Cards → Biểu đồ `ComposedChart` theo ngày giao dịch (`Prevented $`, `Missed $`, `FP Friction $`, `Alert Rate %`) → Phễu 4 tầng đơn điệu giảm (7/12) + Sức khỏe hàng đợi, Backlog Aging & Hiệu suất điều tra viên (5/12).
- **Tab 2 (`EffectivenessTab`):** Phân bổ AI vs. Luật + Dải Sức khỏe Mô hình (`KS`, `Brier`, `ECE`, `PSI`) → Bảng xếp hạng Luật (`FAR`, `Unique Catch`, `Mẫu nhỏ`) kèm xem nhanh Top 5 mẫu FP/FN → `Calibration Reliability Curve` (6/12) & `Top-K Gain / Lift` (6/12) → Bộ mô phỏng Ngưỡng kép (`τ_review`, `τ_reject`) hiển thị song song **Hybrid** và **Chỉ AI** cùng 3 nút gợi ý tự động → Bảng So sánh Phiên bản Mô hình (7/12) & Biểu đồ Phân rã PSI theo bin (5/12).
- **Tab 3 (`TypologiesPatternsTab`):** Loại hình gian lận vs. Nguyên nhân FP (6/6) → Biểu đồ 24 giờ tách 2 đường (`Fraud Rate %` & `Flag Rate %`) → Ma trận Phân khúc đa chiều (`Khoảng tiền | MCC | Merchant | Device | IP | Thẻ`) → Top `user_id` rủi ro (7/12) + Tác động `EntityBlacklist` (5/12).
- **Tab 4 (`ComplianceReportCenterTab`):** Preview & Export SAR 5 phần và Executive Audit Report đồng bộ toàn bộ KPI mới; xuất HTML/In PDF bằng template bảng biểu chuẩn A4 (`@media print`).
