# Đặc tả use case phân hệ Insight & Report

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Stage: 3. Design
Status: In progress
Task ID: TASK-106

<!-- [26-11-06] Đồng bộ với kiến trúc đã cài đặt ở Detection & Investigation ([26-10-31], [26-11-01]):
1. Một giao dịch nghi vấn = một bản ghi trong bảng `fraud_cases` (không có bảng `case_transactions` riêng).
2. `verified_label` suy dẫn từ `Case.status` (`RESOLVED_FRAUD -> 1`, `RESOLVED_LEGITIMATE -> 0`, trạng thái mở -> `None`).
3. Rule Engine sử dụng `RuleStatus = DRAFT | ACTIVE | INACTIVE` và `RuleAction = ALLOW | REVIEW | REJECT` (không có `SHADOW`).
4. Danh sách theo dõi chỉ gồm `BLACKLIST` (`entity_blacklist`), không có `WHITELIST`; nhật ký kiểm toán dùng bảng `audit_logs` (`entity_type = "CASE"`).
5. Ngưỡng cảnh báo `NOISY RULE` tại `SUC-23` thống nhất ở mức `Verified FPR > 80%` đồng bộ với Bảng 4.1 và `SUC-20`.
6. Phần IV của biên bản SAR (`SUC-25`) lấy từ `resolution_reason`, `resolution_summary`, ghi chú điều tra trong `audit_logs` và `reviewer_notes` (do `SUC-21` AI Copilot được hoãn ở workstream riêng). -->

# 0. Tài liệu liên quan

- [Tìm hiểu quy trình nghiệp vụ FDS](https://app.notion.com/p/3e5b99c6a95080568644ec2069d8d6d4)
- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/3e7b99c6a950801db925e4077d521232)
- [Đặc tả use case hệ thống phân hệ Detection](https://app.notion.com/p/3f9b99c6a95080e8a8f8e8f4f21c2728)
- [Đặc tả use case hệ thống phân hệ Investigation](https://app.notion.com/p/b4ab99c6a95082ccacd101bf7c6ae63a)
- [Thiết kế kiến trúc high-level](https://app.notion.com/p/374b99c6a9508089972acd6060691d9a)

---

# 1. Tổng quan nghiệp vụ Phân tích & Báo cáo (Insight & Report)

Phân hệ **Insight & Report** hiện thực hóa nghiệp vụ **BUC-05 (Lập báo cáo)** và đóng vai trò cung cấp căn cứ định lượng cho **BUC-04 (Cập nhật, tối ưu chính sách rủi ro)**.

Khác với màn hình kết quả của từng phiên quét đơn lẻ (`SUC-16` ở phân hệ Detection) hay màn hình đánh giá mô hình trên tập kiểm thử tĩnh (`SUC-09`), phân hệ **Insight & Report** tổng hợp dữ liệu xuyên suốt toàn bộ vòng đời vận hành của dự án (**Detection Jobs $\rightarrow$ Investigation Cases & Ground Truth Verdicts $\rightarrow$ Rules & Models**) để giải quyết **4 bài toán quản trị rủi ro cốt lõi** trong thực tế ngân hàng và thanh toán điện tử:

1. **Đo lường hiệu quả bảo vệ tài chính & chi phí Ma sát Khách hàng (Financial Protection vs. Customer Friction / Insult Rate):**
	- Trong nghiệp vụ FDS, chặn được nhiều gian lận chưa chắc đã tốt nếu hệ thống chặn nhầm quá nhiều khách hàng hợp lệ (*False Positive Friction / Customer Insult Rate*). Cấp quản lý cần nhìn thấy rõ: **Tổng số tiền gian lận thực tế đã ngăn chặn được (`Confirmed Fraud Loss Prevented $`)** đặt cạnh **Tổng giá trị giao dịch hợp lệ bị làm phiền (`False Positive Friction Volume $`)** và **Tỷ lệ Cảnh báo trên mỗi Ca gian lận thật (`Alert-to-Fraud Ratio`)**.
2. **Đánh giá hiệu năng thực tế của Tập luật & Mô hình AI sau Điều tra (Post-Investigation Ground-Truth Attribution):**
	- Đối chiếu phán quyết ban đầu của từng `Rule` và từng `ML Model` với kết quả xác minh thực tế (`verified_label`: `RESOLVED_FRAUD` vs. `RESOLVED_LEGITIMATE`) từ phân hệ **Investigation** để chỉ ra:
		- **Top High-Value Rules:** Những quy tắc bắt trúng nhiều tiền gian lận thật nhất (`Verified Precision >= 70%`).
		- **Top Noisy Rules:** Những quy tắc phát sinh nhiều hồ sơ điều tra nhưng có tỷ lệ báo động giả thực tế (`Verified FPR % > 80%`) quá cao cần tinh chỉnh hoặc chuyển sang `INACTIVE`. *[26-11-06]*
		- **AI-Exclusive Catch Rate:** Tỷ lệ các vụ gian lận tinh vi mà **chỉ mô hình học máy phát hiện được** (không có quy tắc thủ công nào bắt trúng) — chỉ số chứng minh trực tiếp giá trị gia tăng của AI so với hệ thống Rule truyền thống.
3. **Nhận diện Xu hướng & Hình thái Kịch bản Gian lận (Fraud Typology & Behavioral/Temporal Intelligence):**
	- Phân tích cơ cấu các kịch bản tấn công đã xác nhận (*Card Testing / Micro-probing*, *Velocity Attack*, *Account Takeover*, *Device-Sharing Fraud Ring*, *Merchant Collusion*), khung giờ cao điểm tội phạm hoạt động (*Hour-of-Day Distribution*) và phân khúc giá trị giao dịch bị nhắm tới.
4. **Giám sát Vận hành Điều tra & Xuất Báo cáo Tuân thủ (Case Operations Funnel & SAR / Executive Compliance Reporting):**
	- Theo dõi phễu chuyển đổi từ lúc quét giao dịch đến khi đóng hồ sơ điều tra, tồn đọng hàng đợi theo mức độ ưu tiên, và tự động kết xuất **Báo cáo Hoạt động Đáng ngờ (SAR — Suspicious Activity Report)** chuẩn hóa cho từng vụ việc hoặc **Báo cáo Tổng hợp Quản trị Rủi ro (Executive Risk Summary)**.

---

# 2. Tóm tắt danh mục Use Case hệ thống

Dưới đây là danh mục Use Case hệ thống (SUC) cho phân hệ **Insight & Report** (tiếp nối mã số từ `SUC-21` của phân hệ Investigation):

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt |
| --- | --- | --- | --- |
| **SUC-22** | **View executive financial & case operations dashboard** | Risk Manager, Fraud Analyst | Xem bảng điều khiển tổng quan về giá trị tổn thất gian lận đã ngăn chặn, tỷ lệ ma sát khách hàng (`False Positive Volume`), phễu chuyển đổi xử lý hồ sơ (`Detection-to-Resolution Funnel`) và tiến độ giải quyết hàng đợi điều tra. |
| **SUC-23** | **Analyze rule & model ground-truth performance** | Data Scientist, Risk Manager, Fraud Analyst | Phân tích độ chính xác thực tế (`Verified Precision`, `Verified FPR`) của từng quy tắc và từng phiên bản mô hình AI dựa trên nhãn xác nhận sau điều tra; đo lường tỷ lệ gian lận bắt độc quyền bởi AI (`AI-Exclusive Catches`). |
| **SUC-24** | **Analyze fraud typologies & temporal-behavioral patterns** | Fraud Analyst, Risk Manager | Khám phá xu hướng và hình thái gian lận theo kịch bản tấn công (`Fraud Typology`), phân bố khung giờ trong ngày, phân khúc giá trị giao dịch và chủ thể rủi ro cao. |
| **SUC-25** | **Generate & export SAR and executive compliance reports** | Fraud Analyst, Risk Manager | Tự động tổng hợp và xuất hồ sơ Báo cáo Hoạt động Đáng ngờ (`SAR Dossier`) cho các ca gian lận đã xác nhận, hoặc xuất Báo cáo Quản trị Rủi ro Định kỳ (`Executive Risk Audit Report`) ra định dạng PDF/HTML Print, Markdown, CSV, JSON. |

---

# 3. Chi tiết đặc tả Use Case

## SUC-22: View executive financial & case operations dashboard (Xem bảng điều khiển tài chính & vận hành điều tra)

### Thông tin chung

- **Mã Use Case:** SUC-22
- **Tên Use Case:** View executive financial & case operations dashboard
- **Tác nhân chính (Primary Actor):** Risk Manager, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** `InsightReportService`, `IDetectionJobRepository`, `ICaseRepository`
- **Mô tả:** Cung cấp bức tranh toàn cảnh cấp điều hành về hiệu quả bảo vệ tài chính của hệ thống FDS trong dự án đang chọn, đặt song song lợi ích ngăn chặn thất thoát (`Fraud Loss Prevented`) với chi phí làm phiền khách hàng hợp lệ (`False Positive Friction`), đồng thời giám sát hiệu suất xử lý hồ sơ tại phân hệ Investigation.
- **Tiền điều kiện:** Người dùng đã chọn một Dự án (`Active Project`) có ít nhất một `DetectionJob` hoàn tất hoặc các `Case` (`fraud_cases`) đã khởi tạo.
- **Hậu điều kiện:** Các thẻ chỉ số KPI tài chính, biểu đồ xu hướng và phễu vận hành hiển thị chính xác theo bộ lọc phạm vi (toàn dự án hoặc theo các đợt `DetectionJob` được chọn).
- **Sự kiện kích hoạt (Trigger):** Người dùng truy cập mục **Insight & Report** (`/reports`) trên thanh điều hướng chính (Tab mặc định: **Executive & Operations Overview**).

### Luồng sự kiện chính (Basic Flow)

1. Người dùng mở màn hình **Insight & Report** (Tab 1: **Executive & Operations Overview**).
2. Hệ thống truy vấn dữ liệu tổng hợp từ các bảng `detection_jobs` và `fraud_cases` (kèm tệp `predictions.parquet` khi cần) của dự án hiện tại, tính toán và hiển thị **6 Thẻ KPI Quản trị Cốt lõi** *[26-11-06]*:
	- **Gross Scanned Volume (`$` & `Tx Count`):** Tổng giá trị tiền và tổng số lượng giao dịch đã đi qua động cơ rà soát của dự án.
	- **Total Exposure / Amount at Risk (`$`):** Tổng giá trị tiền của các giao dịch bị hệ thống gắn cờ (`REJECT` + `REVIEW`).
	- **Confirmed Fraud Loss Prevented (`$ Saved`):** Tổng giá trị tiền của các giao dịch gian lận đã được điều tra viên xác nhận (`RESOLVED_FRAUD` / `verified_label = 1`).
	- **False Positive Friction Volume (`$ Insulted` & `Insult Rate %`):** Tổng giá trị và tỷ lệ các giao dịch hợp lệ bị hệ thống gắn cờ nhầm đã được xác minh là `RESOLVED_LEGITIMATE` (`verified_label = 0`).
	- **Verified Precision / Alert-to-Fraud Ratio:** Tỷ lệ phần trăm cảnh báo đúng trên tổng số hồ sơ đã giải quyết ($\text{TP} / (\text{TP} + \text{FP})$) và tỷ lệ bao nhiêu cảnh báo đã xác minh thì bắt được 1 ca gian lận thật (ví dụ `1.8 : 1`).
	- **Case Resolution SLA & Backlog:** Tỷ lệ hồ sơ đã đóng trên tổng số hồ sơ điều tra, kèm số lượng hồ sơ `CRITICAL` / `HIGH` đang tồn đọng (`OPEN` / `IN_PROGRESS` / `PENDING_CUSTOMER`).
3. Hệ thống hiển thị **3 Biểu đồ Phân tích Điều hành**:
	- **Biểu đồ 1 — End-to-End Risk & Investigation Funnel (Phễu chuyển đổi 4 tầng):**
		- `Tầng 1: Total Transactions Scanned` $\rightarrow$ `Tầng 2: Flagged by Engine (REJECT / REVIEW)` $\rightarrow$ `Tầng 3: Dispatched to Investigation Cases` $\rightarrow$ `Tầng 4: Resolved Outcomes (Confirmed Fraud vs. False Positive vs. Pending)`.
	- **Biểu đồ 2 — Financial Protection vs. Friction Trend (Biểu đồ Cột chồng & Đường theo các phiên quét / chuỗi thời gian):**
		- Trục hoành: Các phiên `DetectionJob` (hoặc mốc thời gian giao dịch); Trục tung: Giá trị tiền (`Confirmed Fraud $`, `False Positive $`, `Pending Review $`) và đường `Fraud Rate %`.
	- **Biểu đồ 3 — Case Queue Status & Priority Breakdown:**
		- Phân bổ số lượng hồ sơ theo trạng thái (`OPEN`, `IN_PROGRESS`, `PENDING_CUSTOMER`, `RESOLVED_FRAUD`, `RESOLVED_LEGITIMATE`) và mức độ ưu tiên (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
4. Người dùng có thể sử dụng thanh **Scope Filter** trên đầu trang để lọc số liệu theo:
	- Toàn bộ Dự án (`All Detection Jobs`) hoặc chọn một tập hợp `DetectionJob` cụ thể.
	- Khoảng thời gian tạo (`Date Range`).
	- Chế độ đối chiếu nhãn tập dữ liệu (`Dataset Ground-Truth Fallback` theo `BR-IR-02`).

---

## SUC-23: Analyze rule & model ground-truth performance (Phân tích hiệu năng thực chiến của tập luật và mô hình AI)

### Thông tin chung

- **Mã Use Case:** SUC-23
- **Tên Use Case:** Analyze rule & model ground-truth performance
- **Tác nhân chính (Primary Actor):** Data Scientist, Risk Manager, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** `InsightReportService`, `IRuleRepository`, `IModelVersionRepository`, `ICaseRepository`
- **Mô tả:** Đo lường và so sánh hiệu quả thực tế của từng quy tắc nghiệp vụ cũng như từng phiên bản mô hình học máy dựa trên **nhãn chuẩn đã xác minh từ quá trình điều tra (`verified_label`)** và/hoặc nhãn thực tế của tập dữ liệu (`BR-IR-02`), giúp đội ngũ rủi ro biết chính xác luật nào đang gây nhiễu, mô hình nào bắt được nhiều gian lận độc quyền nhất và ngưỡng điểm nào cần điều chỉnh.
- **Tiền điều kiện:** Dự án đã có kết quả chạy `DetectionJob` và/hoặc các hồ sơ điều tra đã được gắn nhãn phán quyết (`RESOLVED_FRAUD` / `RESOLVED_LEGITIMATE`).
- **Hậu điều kiện:** Hiển thị đầy đủ ma trận đóng góp của từng Rule và từng Model kèm khuyến nghị tối ưu hóa chính sách.
- **Sự kiện kích hoạt (Trigger):** Người dùng chọn Tab **2. Rule & Model Effectiveness** trong phân hệ **Insight & Report**.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng chuyển sang Tab **Rule & Model Effectiveness**.
2. Hệ thống tổng hợp dữ liệu giao thoa giữa kết quả chấm điểm (`triggered_rules`, `model_score`) và nhãn xác thực (`verified_label`) để hiển thị **3 Khu vực Phân tích Chuyên sâu** *[26-11-06]*:
	- **Khu vực 1 — Ma trận Đóng góp Giữa AI Model và Rule Engine (`AI vs. Rule Catch Attribution`):**
		- Phân rã toàn bộ các giao dịch gian lận bắt được thành 3 tập hợp:
			1. **AI-Exclusive Catches (Chỉ Mô hình AI bắt được):** Các ca gian lận có `model_score >= threshold` nhưng không vi phạm bất kỳ quy tắc thủ công nào.
			2. **Rule-Exclusive Catches (Chỉ Tập luật bắt được):** Các ca gian lận bị chặn bởi Rule nhưng điểm mô hình AI dưới ngưỡng (hoặc đợt quét chỉ dùng Rule).
			3. **Consensus / Overlap Catches (Cả AI và Rule cùng bắt):** Các ca gian lận bị cả hai động cơ phát hiện đồng thời.
		- Hiển thị trực quan bằng biểu đồ thanh phân tách (Attribution Bar) kèm giá trị tiền gian lận cứu được bởi từng nguồn.
	- **Khu vực 2 — Bảng Xếp hạng Hiệu quả Thực chiến của Tập luật (`Rule Ground-Truth Leaderboard & Noisy Rule Detector`):**
		- Bảng thống kê từng quy tắc (`rule_code`, `rule_name`, `status` [`ACTIVE`/`DRAFT`/`INACTIVE`], `action` [`REJECT`/`REVIEW`]):
			- Tổng số lần kích hoạt (`Total Hits` & `Hit Rate %`).
			- Tổng số hồ sơ đã qua điều tra xác minh (`Verified Cases`).
			- Số ca gian lận thật (`Verified TP`) và **Tổng tiền gian lận chặn được nhờ quy tắc này (`Fraud Value Caught $`)**.
			- Số ca báo động giả (`Verified FP`) và **Tỷ lệ Báo động giả Thực tế (`Verified FPR % = FP / Verified Cases`)**.
			- **Nhãn Chẩn đoán Chính sách Tự động (`Policy Health Tag`):** *[26-11-06]*
				- `HIGH VALUE` (Màu Xanh): `Verified Precision >= 70%`.
				- `NEEDS TUNING / NOISY` (Màu Đỏ/Cam): `Verified FPR > 80%` (đồng bộ với Bảng 4.1 và `SUC-20`) — kèm nút điều hướng nhanh sang chỉnh sửa ngưỡng quy tắc tại `/rules`.
	- **Khu vực 3 — Phân phối Điểm Mô hình & Độ nhạy Ngưỡng Quyết định (`Model Score Calibration & Threshold Trade-off`):**
		- Biểu đồ so sánh phân phối xác suất `model_score` giữa nhóm `Confirmed Fraud`, nhóm `False Positive / Legitimate`, và nhóm `Unverified` trên 10 dải điểm (`0.0–0.1`, ..., `0.9–1.0`).
		- Bảng mô phỏng **What-If Threshold Simulator** ngay trên dữ liệu thực tế: Khi kéo thanh trượt ngưỡng từ `0.10` đến `0.95`, hệ thống tính ngay tỷ lệ ca gian lận giữ lại được (`Estimated Recall %`), tỷ lệ cảnh báo giả giảm đi (`FP Reduction %`), và khối lượng hồ sơ đẩy vào hàng đợi điều tra (`Review Queue Volume`).

---

## SUC-24: Analyze fraud typologies & temporal-behavioral patterns (Phân tích hình thái kịch bản & xu hướng gian lận)

### Thông tin chung

- **Mã Use Case:** SUC-24
- **Tên Use Case:** Analyze fraud typologies & temporal-behavioral patterns
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Risk Manager
- **Tác nhân phụ (Secondary Actor):** `InsightReportService`, `ICaseRepository`, `IDetectionJobRepository`, `IBlacklistRepository`
- **Mô tả:** Cung cấp góc nhìn phân tích hành vi và hình thái tội phạm để trả lời câu hỏi ở Bước 4 của quy trình nghiệp vụ FDS (*"Kẻ gian dạo này đang dùng chiêu trò gì mới? Tấn công vào khung giờ nào, phân khúc số tiền nào?"*).
- **Tiền điều kiện:** Dự án đã có kết quả phát hiện gian lận và hồ sơ điều tra.
- **Hậu điều kiện:** Các biểu đồ phân bổ kịch bản gian lận, phân bố khung giờ và phân khúc rủi ro được hiển thị trực quan.
- **Sự kiện kích hoạt (Trigger):** Người dùng chọn Tab **3. Fraud Typologies & Patterns** trong phân hệ **Insight & Report**.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng mở Tab **Fraud Typologies & Patterns**.
2. Hệ thống phân tích tập giao dịch nghi vấn và các hồ sơ đã xác nhận gian lận để hiển thị **4 Khung Phân tích Hình thái** *[26-11-06]*:
	- **Khung 1 — Phân bổ Kịch bản Gian lận & Lý do Báo động giả (`Fraud Typology & False Positive Reason Breakdown`):**
		- Biểu đồ thứ nhất thống kê tỷ trọng các kịch bản gian lận (`resolution_reason` của các ca `RESOLVED_FRAUD`): `CARD_TESTING`, `VELOCITY_ATTACK`, `ACCOUNT_TAKEOVER`, `DEVICE_SHARING_RING`, `COLLUSIVE_MERCHANT`, `OTHER_FRAUD`.
		- Biểu đồ thứ hai thống kê nguyên nhân gây báo động giả phổ biến nhất (của các ca `RESOLVED_LEGITIMATE`): `LEGITIMATE_UNUSUAL_SPENDING`, `CUSTOMER_CONFIRMED`, `OVERLY_STRICT_RULE`, `MODEL_FALSE_ALARM`, `OTHER_LEGITIMATE`.
	- **Khung 2 — Phân tích Rủi ro theo Khung giờ Giao dịch (`Temporal Fraud Distribution — Hour of Day`):**
		- Biểu đồ kết hợp thể hiện khối lượng giao dịch và **Tỷ lệ gian lận (`Fraud Rate %`) theo 24 khung giờ trong ngày (`00h -> 23h`)**, làm nổi bật các khung giờ nhạy cảm.
	- **Khung 3 — Phân tích theo Dải Giá trị Giao dịch (`Amount Bracket Risk Profile`):**
		- Chia toàn bộ giao dịch thành 5 phân khúc giá trị (`Micro < $10`, `Small $10–$100`, `Medium $100–$500`, `Large $500–$2,000`, `High-Value >= $2,000`), hiển thị song song số lượng giao dịch bị gắn cờ và tổng tiền rủi ro ở mỗi phân khúc.
	- **Khung 4 — Danh sách Thực thể Rủi ro Cao & Blacklist Summary (`Top Flagged Subjects & Active Blacklist Impact`):** *[26-11-06]*
		- Thống kê các `user_id` có tổng giá trị rủi ro hoặc số lần vi phạm cao nhất cùng tổng quan số lượng thực thể đang bị khóa trong `entity_blacklist` (`ACTIVE` vs. `REMOVED` theo `USER_ID`, `CARD_ID`, `DEVICE_ID`, `IP_ADDRESS`, `MERCHANT_ID`).

---

## SUC-25: Generate & export SAR and executive compliance reports (Khởi tạo và xuất báo cáo giao dịch đáng ngờ SAR & báo cáo tổng hợp)

### Thông tin chung

- **Mã Use Case:** SUC-25
- **Tên Use Case:** Generate & export SAR and executive compliance reports
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Risk Manager
- **Tác nhân phụ (Secondary Actor):** `InsightReportService`, `ICaseRepository`, `IAuditRepository`, `IBlacklistRepository`
- **Mô tả:** Hiện thực hóa trọn vẹn nghiệp vụ **BUC-05 (Lập báo cáo)**: cho phép chuyên viên lựa chọn các hồ sơ đã xác nhận gian lận (`RESOLVED_FRAUD`) để tự động kết xuất **Hồ sơ Báo cáo Hoạt động Đáng ngờ (SAR — Suspicious Activity Report)** theo mẫu chuẩn của tổ chức tài chính, hoặc xuất **Báo cáo Tổng hợp Quản trị Rủi ro Dự án (Executive Risk & Policy Audit Report)** để lưu trữ, in ấn (PDF/HTML) hoặc nộp cho cơ quan kiểm toán.
- **Tiền điều kiện:** Dự án đã có các hồ sơ điều tra (đối với báo cáo SAR) hoặc kết quả chạy Detection Job (đối với báo cáo tổng hợp).
- **Hậu điều kiện:** Bản xem trước báo cáo chuẩn hóa được hiển thị trực tiếp trên giao diện và cho phép tải xuống dưới định dạng `.html`/Print-to-PDF, `.md` (Markdown), `.json` hoặc `.csv`.
- **Sự kiện kích hoạt (Trigger):** Người dùng mở Tab **4. Compliance & Report Center (SAR Export)** trong phân hệ **Insight & Report** (hoặc nhấn nút **Export SAR** từ một hồ sơ đã xác nhận gian lận trong `SUC-18`).

### Luồng sự kiện chính (Basic Flow)

1. Người dùng mở Tab **Compliance & Report Center**.
2. Người dùng chọn **Loại Báo cáo cần khởi tạo (`Report Template Type`)**:
	- **Mẫu 1 — `Suspicious Activity Report (SAR) Dossier` (Báo cáo Hoạt động Đáng ngờ theo Hồ sơ Điều tra):**
		- Người dùng chọn một (hoặc nhiều) hồ sơ có trạng thái `RESOLVED_FRAUD` (hoặc bất kỳ hồ sơ đáng ngờ nào cần lập biên bản) từ danh sách.
		- Hệ thống tự động tổng hợp dữ liệu từ `fraud_cases`, `audit_logs` và `entity_blacklist` để dựng **Bản thảo Báo cáo SAR chuẩn 5 phần** *[26-11-06]*:
			1. *Phần I — Thông tin Định danh Hồ sơ & Chủ thể (`Subject & Case Identification`):* Mã hồ sơ (`case_id`, `case_code`), `user_id`, mức độ rủi ro (`priority`, `priority_score`), thời gian phát hiện, chuyên viên thụ lý (`assigned_to`, `resolved_by`).
			2. *Phần II — Chi tiết Giao dịch Đáng ngờ & Tổn thất Tài chính (`Suspicious Activity & Financial Summary`):* Bảng liệt kê mã giao dịch (`event_id`), thời điểm (`tx_timestamp`), số tiền (`amount`), thuộc tính giao dịch (`attributes`) và các hồ sơ liên quan cùng `user_id`.
			3. *Phần III — Bằng chứng Kỹ thuật từ Động cơ Phát hiện (`Automated Detection Evidence`):* Điểm xác suất từ mô hình AI (`model_score`), các đặc trưng đóng góp hàng đầu (`feature_contributions` + đối chiếu Baseline lịch sử), và danh sách các quy tắc nghiệp vụ bị vi phạm kèm mệnh đề khớp (`triggered_rules` / `matched_clauses`).
			4. *Phần IV — Diễn giải Điều tra & Kịch bản Gian lận (`Investigation Narrative & Typology`):* Mã kịch bản gian lận (`resolution_reason`), kết luận chính thức của điều tra viên (`resolution_summary`), ghi chú điều tra trong `audit_logs` và ghi chú người duyệt (`reviewer_notes`).
			5. *Phần V — Hành động Ngăn chặn & Lịch sử Kiểm toán (`Mitigation Actions & Audit Trail`):* Trạng thái khóa thực thể (`entity_blacklist`), lịch sử các bước xử lý có dấu thời gian (`audit_logs`).
	- **Mẫu 2 — `Executive Fraud & Policy Audit Report` (Báo cáo Tổng hợp Quản trị Rủi ro Dự án):**
		- Hệ thống tự động tổng hợp toàn bộ KPI tài chính (`SUC-22`), bảng hiệu năng thực chiến của tập luật và mô hình (`SUC-23`), thống kê hình thái gian lận (`SUC-24`) và danh sách thực thể trong Blacklist thành một báo cáo quản trị hoàn chỉnh.
3. Hệ thống hiển thị bản xem trước trực quan (**Interactive Document Preview**) ngay trên màn hình; cho phép người dùng bổ sung ghi chú người lập báo cáo (`Prepared By`, `Reviewer Notes`).
4. Người dùng nhấn một trong các nút xuất báo cáo:
	- **Print / Save as PDF:** Mở chế độ in định dạng chuẩn tài liệu hành chính.
	- **Download Markdown (`.md`) / JSON (`.json`) / CSV (`.csv`) / HTML (`.html`):** Tải tệp báo cáo về máy trạm để lưu trữ hoặc đính kèm hồ sơ kiểm toán.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IR-01 (Cross-Project Isolation):** Toàn bộ số liệu thống kê, biểu đồ và báo cáo SAR chỉ được truy xuất trong phạm vi `project_id` đang làm việc (`BR-PM-06`).
- **BR-IR-02 (Ground-Truth Priority in Metrics):** Khi tính toán các chỉ số độ chính xác thực tế (`Verified Precision`, `Verified FPR`, `Confirmed Fraud Loss Prevented`), hệ thống ưu tiên sử dụng nhãn đã được điều tra viên xác nhận (`verified_label` suy ra từ `fraud_cases.status`); đối với các giao dịch chưa qua điều tra thủ công nhưng tập dữ liệu gốc có sẵn cột nhãn kiểm thử (`label` / `is_fraud`), hệ thống cho phép bật chế độ đối chiếu nhãn tập dữ liệu (*Dataset Ground-Truth Fallback*) kèm chú thích rõ nguồn nhãn trên giao diện.
- **BR-IR-03 (SAR Audit Completeness):** Mỗi báo cáo SAR được xuất ra bắt buộc phải đính kèm mã định danh hồ sơ (`case_id`), dấu thời gian khởi tạo báo cáo (`generated_at`), và trích xuất nguyên vẹn lịch sử phán quyết của chuyên viên (`audit_logs`) để đảm bảo tính toàn vẹn pháp lý.

---

# 4. Từ điển Chỉ số Nghiệp vụ (Domain Metrics Dictionary) & Bố cục Giao diện

## 4.1. Từ điển Công thức & Ý nghĩa Nghiệp vụ của các Chỉ số Cốt lõi

| Tên Chỉ số (Metric) | Công thức Tính toán | Ý nghĩa Quyết định Nghiệp vụ (Why it matters) |
| --- | --- | --- |
| **Gross Scanned Volume ($\$$)** | $$\sum_{i=1}^{N} \text{amount}_i$$ | Quy mô dòng tiền thanh toán đi qua hệ thống bảo vệ của dự án. |
| **Amount at Risk ($\$$)** | $$\sum_{i \in \text{Flagged}} \text{amount}_i$$ | Tổng giá trị giao dịch nằm trong diện nghi vấn (`REJECT` + `REVIEW`) cần hệ thống hoặc con người can thiệp. |
| **Confirmed Fraud Loss Prevented ($\$$)** | $$\sum_{i \in \text{Verified Fraud}} \text{amount}_i$$ | **Chỉ số ROI quan trọng nhất của FDS:** Số tiền thất thoát thực tế đã cứu được cho ngân hàng và chủ thẻ. |
| **False Positive Friction Volume ($\$$) & Insult Rate ($\%$)** | $$\text{Friction } \$ = \sum_{i \in \text{Verified Legit Flagged}} \text{amount}_i$$ | Đo lường thiệt hại trải nghiệm khách hàng: bao nhiêu tiền giao dịch hợp lệ của khách hàng tốt bị hệ thống chặn/gắn cờ nhầm. |
| **Alert-to-Fraud Ratio** | $$\dfrac{\text{Total Investigated Alerts}}{\text{Confirmed Fraud Cases}}$$ | Đo lường năng suất vận hành: Điều tra viên phải tốn công rà soát bao nhiêu cảnh báo để bắt được 1 vụ gian lận thật (chuẩn tốt trong ngành: $< 3:1$ đến $5:1$). |
| **Verified Rule FPR ($\%$)** | $$\dfrac{\text{FP}_{\text{rule}}}{\text{TP}_{\text{rule}} + \text{FP}_{\text{rule}}} \times 100\%$$ | Chỉ ra các quy tắc gây nhiễu (`Noisy Rules`): nếu một Rule có `Verified FPR > 80%`, cần nới ngưỡng hoặc chuyển sang `INACTIVE`. *[26-11-06]* |
| **AI-Exclusive Catch Rate ($\%$)** | $$\dfrac{\text{Fraud Caught ONLY by ML}}{\text{Total Fraud Caught}} \times 100\%$$ | Chứng minh giá trị cốt lõi của Học máy: Tỷ lệ các ca gian lận mới/ẩn danh vượt qua mọi quy tắc tĩnh nhưng bị mô hình AI bắt giữ. |

## 4.2. Đặc tả Bố cục Giao diện 4 Tab (UI/UX Layout)

| Tab Giao diện | Thành phần Hiển thị Chính (Widgets & Charts) | Đối tượng Sử dụng Chính |
| --- | --- | --- |
| **Tab 1: Executive & Operations Overview (`SUC-22`)** | • **6 Thẻ KPI Tài chính & Vận hành:** *Gross Volume*, *Amount at Risk*, *Fraud Loss Prevented ($)*, *False Positive Friction ($)*, *Alert-to-Fraud Ratio*, *Resolution Rate*.<br/>• **Biểu đồ Phễu 4 tầng:** *Scanned $\rightarrow$ Flagged $\rightarrow$ Dispatched $\rightarrow$ Confirmed vs. False Positive*.<br/>• **Biểu đồ Xu hướng theo Phiên/Thời gian** & **Phân bổ Trạng thái Hàng đợi Case**. | Risk Manager, Lead Fraud Analyst |
| **Tab 2: Rule & Model Effectiveness (`SUC-23`)** | • **Thanh Phân rã Đóng góp (Attribution Breakdown):** *AI-Exclusive Catches* vs. *Rule-Exclusive* vs. *Overlap*.<br/>• **Bảng Rule Ground-Truth Leaderboard:** Cột `Hits`, `Verified TP`, `Verified FP`, `Verified FPR %`, `Fraud Value Caught ($)` và nhãn cảnh báo `NOISY RULE` (`> 80%`).<br/>• **Biểu đồ Phân phối Điểm Model & Trình mô phỏng Ngưỡng (`What-If Threshold Simulator`)**. | Data Scientist, Risk Policy Manager |
| **Tab 3: Fraud Typologies & Patterns (`SUC-24`)** | • **Biểu đồ Cơ cấu Kịch bản Gian lận (`Fraud Typology Breakdown`)** & **Lý do Báo động giả (`FP Reasons`)**.<br/>• **Biểu đồ Rủi ro theo 24 Khung giờ (`Hourly Fraud Rate & Volume Chart`)**.<br/>• **Biểu đồ Phân khúc Số tiền (`Amount Bracket Risk Profile`)** & **Top Chủ thể Rủi ro cao + Blacklist Summary**. | Fraud Analyst, Risk Manager |
| **Tab 4: Compliance & Report Center (`SUC-25`)** | • **Trình Khởi tạo Hồ sơ SAR (`SAR Dossier Builder`):** Chọn Case `RESOLVED_FRAUD` $\rightarrow$ Xem trước biên bản SAR 5 phần chuẩn hóa.<br/>• **Trình Xuất Báo cáo Tổng hợp Dự án (`Executive Audit Report`)**.<br/>• **Thanh Công cụ Xuất bản:** *Print / Save PDF*, *Export Markdown (`.md`)*, *Export JSON/CSV/HTML*. | Fraud Analyst, Compliance Officer |
