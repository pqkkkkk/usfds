# Đặc tả use case phân hệ Insight & Report [26-11-06]

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Task ID: TASK-106

---

# 1. Tổng quan nghiệp vụ Phân tích & Báo cáo (Insight & Report)

Phân hệ **Insight & Report** hiện thực hóa nghiệp vụ **BUC-05 (Lập báo cáo)** và đóng vai trò cung cấp căn cứ định lượng cho **BUC-04 (Cập nhật, tối ưu chính sách rủi ro)**.

Khác với màn hình kết quả của từng phiên quét đơn lẻ (`SUC-16` ở phân hệ Detection) hay màn hình đánh giá mô hình trên tập kiểm thử tĩnh (`SUC-09`), phân hệ **Insight & Report** tổng hợp dữ liệu xuyên suốt toàn bộ vòng đời vận hành của dự án (**Detection Jobs $\rightarrow$ Investigation Cases & Ground Truth Verdicts $\rightarrow$ Rules & Models**) để giải quyết **4 bài toán quản trị rủi ro cốt lõi**:

1. **Đo lường hiệu quả bảo vệ tài chính & chi phí Ma sát Khách hàng (Financial Protection vs. Customer Friction / Insult Rate):**
	- Đặt song song **Tổng số tiền gian lận thực tế đã ngăn chặn được (`Confirmed Fraud Loss Prevented $`)** với **Tổng giá trị giao dịch hợp lệ bị làm phiền (`False Positive Friction Volume $`)** và **Tỷ lệ Cảnh báo trên mỗi Ca gian lận thật (`Alert-to-Fraud Ratio`)**.
2. **Đánh giá hiệu năng thực tế của Tập luật & Mô hình AI sau Điều tra (Post-Investigation Ground-Truth Attribution):**
	- Đối chiếu phán quyết ban đầu của từng `Rule` và từng `ML Model` với kết quả xác minh thực tế (`verified_label`: `RESOLVED_FRAUD = 1` vs. `RESOLVED_LEGITIMATE = 0`) từ bảng `fraud_cases` (kèm tùy chọn fallback sang nhãn kiểm thử của tập dữ liệu theo `BR-IR-02`) để chỉ ra:
		- **Top High-Value Rules:** Những quy tắc bắt trúng nhiều tiền gian lận thật nhất (`Verified Precision >= 70%`).
		- **Top Noisy Rules:** Những quy tắc có tỷ lệ báo động giả thực tế (`Verified FPR % >= 70%`) quá cao cần tinh chỉnh ngưỡng hoặc chuyển sang `INACTIVE`.
		- **AI-Exclusive Catch Rate:** Tỷ lệ các vụ gian lận tinh vi mà **chỉ mô hình học máy phát hiện được** (không vi phạm quy tắc thủ công nào).
3. **Nhận diện Xu hướng & Hình thái Kịch bản Gian lận (Fraud Typology & Behavioral/Temporal Intelligence):**
	- Phân tích cơ cấu các kịch bản tấn công đã xác nhận (`CARD_TESTING`, `VELOCITY_ATTACK`, `ACCOUNT_TAKEOVER`, `DEVICE_SHARING_RING`, `COLLUSIVE_MERCHANT`, `OTHER_FRAUD`), lý do báo động giả (`LEGITIMATE_REASONS`), phân bố rủi ro theo 24 khung giờ (`00h -> 23h`), 5 phân khúc giá trị giao dịch (`< $10` đến `> $2,000`), và danh sách thực thể rủi ro cao / `entity_blacklist`.
4. **Giám sát Vận hành Điều tra & Xuất Báo cáo Tuân thủ (Case Operations Funnel & SAR / Executive Compliance Reporting):**
	- Theo dõi phễu chuyển đổi 4 tầng từ lúc quét giao dịch đến khi đóng hồ sơ điều tra, tồn đọng hàng đợi theo mức độ ưu tiên, và tự động kết xuất **Báo cáo Hoạt động Đáng ngờ (SAR — Suspicious Activity Report)** chuẩn 5 phần cho từng vụ việc hoặc **Báo cáo Tổng hợp Quản trị Rủi ro (Executive Risk & Policy Audit Report)**.

---

# 2. Tóm tắt danh mục Use Case hệ thống

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt |
| --- | --- | --- | --- |
| **SUC-22** | **View executive financial & case operations dashboard** | Risk Manager, Fraud Analyst | Xem bảng điều khiển tổng quan về giá trị tổn thất gian lận đã ngăn chặn, tỷ lệ ma sát khách hàng (`False Positive Volume`), phễu chuyển đổi xử lý hồ sơ (`Detection-to-Resolution Funnel`) và tiến độ giải quyết hàng đợi điều tra. |
| **SUC-23** | **Analyze rule & model ground-truth performance** | Data Scientist, Risk Manager, Fraud Analyst | Phân tích độ chính xác thực tế (`Verified Precision`, `Verified FPR`) của từng quy tắc và từng phiên bản mô hình AI dựa trên nhãn xác nhận sau điều tra; đo lường tỷ lệ gian lận bắt độc quyền bởi AI (`AI-Exclusive Catches`) và mô phỏng ngưỡng quyết định (`What-If Threshold Simulator`). |
| **SUC-24** | **Analyze fraud typologies & temporal-behavioral patterns** | Fraud Analyst, Risk Manager | Khám phá xu hướng và hình thái gian lận theo kịch bản tấn công (`Fraud Typology`), phân bố 24 khung giờ trong ngày, 5 phân khúc giá trị giao dịch và thực thể rủi ro cao / `Blacklist`. |
| **SUC-25** | **Generate & export SAR and executive compliance reports** | Fraud Analyst, Risk Manager | Tự động tổng hợp và xuất hồ sơ Báo cáo Hoạt động Đáng ngờ (`SAR Dossier` chuẩn 5 phần) cho các ca gian lận hoặc xuất Báo cáo Quản trị Rủi ro Định kỳ (`Executive Fraud & Policy Audit Report`) ra định dạng PDF/HTML Print, Markdown (`.md`), CSV (`.csv`), JSON (`.json`). |

---

# 3. Chi tiết đặc tả Use Case & Đồng bộ Kiến trúc (`[26-11-06]`)

## 3.1. Kiến trúc Xử lý Dữ liệu (`DuckDBInsightEngine` + Repositories)
- **Tầng OLAP (`usfds-core`):** Sử dụng `DuckDB` in-memory kết hợp `PyArrow` đọc trực tiếp các cột cần thiết từ `predictions.parquet` của các `DetectionJob` (`COMPLETED`) thuộc dự án và `LEFT JOIN` với danh sách `Case` (`fraud_cases`) theo `(project_id, event_id)`.
- **Đồng bộ Schema với Phân hệ Investigation (`[26-11-06]`):**
	- Mỗi bản ghi trong `fraud_cases` (`Case`) đại diện cho 1 giao dịch nghi vấn (`unique (project_id, event_id)`), lưu trực tiếp `amount`, `tx_timestamp`, `model_score`, `triggered_rules`, `feature_contributions`, `attributes`, và thuộc tính suy dẫn `verified_label` (`1` khi `RESOLVED_FRAUD`, `0` khi `RESOLVED_LEGITIMATE`, `None` khi đang mở).
	- Danh sách chặn thực thể truy xuất từ `entity_blacklist` (`ACTIVE` / `REMOVED`).
	- Lịch sử kiểm toán truy xuất từ `audit_logs` (`entity_type = 'CASE'`).
	- Tập luật sử dụng `RuleStatus ∈ {DRAFT, ACTIVE, INACTIVE}` và `RuleAction ∈ {ALLOW, REVIEW, REJECT}`.

## 3.2. Quy tắc Nghiệp vụ (Business Rules)
- **BR-IR-01 (Cross-Project Isolation):** Toàn bộ số liệu thống kê, biểu đồ và báo cáo SAR chỉ được truy xuất trong phạm vi `project_id` đang làm việc (`BR-PM-06`).
- **BR-IR-02 (Ground-Truth Priority in Metrics):** Khi tính toán các chỉ số độ chính xác thực tế (`Verified Precision`, `Verified FPR`, `Confirmed Fraud Loss Prevented`), hệ thống luôn ưu tiên sử dụng nhãn đã được điều tra viên xác nhận (`verified_label` từ `fraud_cases`); đối với các giao dịch chưa qua điều tra thủ công nhưng tập dữ liệu gốc có sẵn cột nhãn kiểm thử (`label` / `is_fraud`), hệ thống hỗ trợ chế độ đối chiếu nhãn tập dữ liệu (*Dataset Ground-Truth Fallback*) kèm chú thích nguồn nhãn rõ ràng trên giao diện.
- **BR-IR-03 (SAR Audit Completeness):** Mỗi báo cáo SAR được xuất ra bắt buộc đính kèm mã định danh hồ sơ (`case_id`, `case_code`), dấu thời gian khởi tạo báo cáo (`generated_at`), và trích xuất nguyên vẹn lịch sử phán quyết (`audit_logs`) của chuyên viên để đảm bảo tính toàn vẹn kiểm toán.
