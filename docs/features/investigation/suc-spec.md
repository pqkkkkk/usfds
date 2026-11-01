# Đặc tả use case hệ thống phân hệ Investigation

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7?pvs=21)
Stage: 3. Design
Status: In progress
Task ID: TASK-94

<!-- [26-10-31] Quyết định cuối: một transaction = một Case; blacklist-only; audit dùng chung; không bulk resolve, network, Copilot hoặc client actor. -->

# 0. Tài liệu liên quan

- [Tìm hiểu quy trình nghiệp vụ FDS](https://app.notion.com/p/T-m-hi-u-quy-tr-nh-nghi-p-v-FDS-3e5b99c6a95080568644ec2069d8d6d4?pvs=21)
- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)
- [Đặc tả use case hệ thống phân hệ Detection](https://app.notion.com/p/c-t-use-case-h-th-ng-ph-n-h-Detection-3f9b99c6a95080e8a8f8e8f4f21c2728?pvs=21)
- [Thiết kế và cài đặt rule engine](https://app.notion.com/p/Thi-t-k-v-c-i-t-rule-engine-3d5b99c6a95080ac90cecd4e8cca834c?pvs=21)
- [Nghiên cứu tích hợp AI Agent vào FDS](https://app.notion.com/p/Nghi-n-c-u-t-ch-h-p-AI-Agent-v-o-FDS-3b4b99c6a95080cd82d3f8d03101e218?pvs=21)

# 1. Tổng quan nghiệp vụ Điều tra (Investigation)

Phân hệ **Investigation** hiện thực hóa nghiệp vụ **BUC-02 (Điều tra giao dịch)**, **BUC-06 (Liên hệ xác minh)** và **BUC-07 (Tạm dừng / khóa thẻ khẩn cấp)**, đồng thời đóng vai trò khép kín vòng lặp phản hồi dữ liệu (Feedback Loop) cho **BUC-04 (Cập nhật, tối ưu chính sách rủi ro)**.

Sau khi Detection xuất kết quả nghi vấn, mỗi giao dịch được chọn gửi qua **Case Intake Contract** (mục 3.0) tạo đúng một **Case**. Các Case cùng `user_id` vẫn có phán quyết độc lập; lịch sử giao dịch và các Case liên quan được truy vấn làm ngữ cảnh điều tra, không gom thành hồ sơ cấp cao hơn. Detection triển khai ở workstream riêng và phải tuân thủ contract REST này.

<!-- [26-10-31] Đồng bộ thuật ngữ với Rule Engine đã cài đặt (JsonLogic, RuleAction = ALLOW | REVIEW | REJECT, RuleStatus = DRAFT | ACTIVE | INACTIVE). Không có risk_weight / ALERT / SHADOW / condition_snapshot. -->

1. **Tại sao giao dịch/chủ thể này bị hệ thống bắt? (Trigger Evidence):** Xem điểm rủi ro từ mô hình AI (`model_score`), độ đóng góp của từng đặc trưng (SHAP / Top Feature Contributions), danh sách quy tắc bị vi phạm (`triggered_rules`) kèm lý do kích hoạt (`trigger_reason`) và các mệnh đề khớp (`matched_clauses`).
2. **Hành vi giao dịch này có thực sự lệch khỏi thói quen lịch sử của chủ thẻ không? (Behavioral & Temporal Profile):** Đối chiếu giao dịch nghi vấn với hồ sơ cơ sở (Baseline 30–90 ngày) của chính `user_id` đó theo 5 chiều: vận tốc giao dịch/thử thẻ nhỏ (*Velocity / Card Testing*), tỷ lệ số tiền so với mức trung bình (`ratio_to_avg_amount`), khung giờ giao dịch, thiết bị/IP và mã ngành điểm bán (`merchant_category`).
3. *(Deferred — workstream riêng [26-10-31])* **Đây là vụ việc đơn lẻ hay nằm trong đường dây có tổ chức? (Network / Link Analysis):** Khám phá đồ thị liên kết thực thể (`user_id` — `device_id` — `ip_address` — `merchant_id` — `card_id`) nhằm vạch trần các cụm dùng chung thiết bị (*Device-sharing Fraud*) hoặc điểm bán hàng thông đồng (*Merchant Ring Fraud*).
4. **Phán quyết và phản hồi:** Đóng riêng Case ở trạng thái `RESOLVED_FRAUD` hoặc `RESOLVED_LEGITIMATE`, tùy chọn blacklist thực thể thuộc giao dịch. `verified_label` suy ra từ trạng thái, không lưu cột nhãn riêng.

# 2. Tóm tắt danh mục Use Case hệ thống

Dưới đây là danh mục Use Case hệ thống (SUC) cho phân hệ **Investigation** trong FDS (tiếp nối mã số từ `SUC-16` của phân hệ Detection).

| **Mã SUC** | **Tên Use Case** | **Primary Actor** | **Mô tả tóm tắt** |
| --- | --- | --- | --- |
| **SUC-17** | **Manage cases** | Fraud Analyst | Hàng đợi từng giao dịch: tìm kiếm, lọc, sắp xếp, phân trang và nhận xử lý từng Case. Không merge/split hoặc đóng hàng loạt. |
| **SUC-18** | **Review case manually** | Fraud Analyst | Điều tra chi tiết hồ sơ trên giao diện Workbench 3 cột (xem bằng chứng AI/Rule, đối chiếu chuỗi thời gian & hành vi lịch sử), gắn nhãn phán quyết (`Fraud` / `Legitimate`) và thực hiện hành động khóa tài khoản/thẻ. |
| **SUC-19** | **Investigate network** *(Deferred — workstream riêng [26-10-31])* | Fraud Analyst | Khám phá đồ thị mạng lưới liên kết đa thực thể (User, Card, Device, IP, Merchant) theo các bậc liên kết (1-hop, 2-hop) để phát hiện và xử lý các đường dây gian lận có tổ chức (Fraud Rings). |
| **SUC-20** | **Manage rules & blacklist from investigation** | Fraud Analyst, Data Scientist | Rule nháp JsonLogic, phản hồi theo rule version và quản lý blacklist. Whitelist ngoài scope. |
| **SUC-21** | **Run AI Case Copilot** *(Deferred — workstream riêng [26-10-31])* | Fraud Analyst | Sử dụng AI Agent tự động tổng hợp ngữ cảnh đa nguồn của Case, giải thích lý do gắn cờ bằng ngôn ngữ tự nhiên và sinh bản nháp nhận định điều tra phục vụ báo cáo SAR. |

# 3. Chi tiết đặc tả Use Case

Phần này đặc tả chi tiết các Use Case thuộc phân hệ **Investigation** (`SUC-17` đến `SUC-21`).

> **[26-10-31] Phạm vi hiện tại:** `SUC-17`, `SUC-18`, `SUC-20` và Case Intake Contract. `SUC-19`, `SUC-21` được thiết kế/cài đặt ở workstream khác. Chưa áp dụng xác thực/phân quyền: backend cung cấp `actor = local-analyst` cho phân công, phán quyết và audit; API không nhận header `X-Actor`. Giá trị này không đại diện cho danh tính đã xác thực.

## 3.0. Send-to-Investigation Contract [26-11-01]

Client gửi đúng một request. Backend truy vấn DetectionJob và output đã lưu theo project, tạo snapshot chính xác và ghi Case/ghi chú/audit qua CaseService trong cùng transaction. Không endpoint prepare hoặc intake công khai; không nhận đường dẫn file hay snapshot từ client.

**Endpoint duy nhất:** `POST /api/v1/detection/jobs/{job_id}/send-to-investigation`

```json
{
    "event_ids": ["TX-000123"],
    "analyst_notes": "Optional initial triage note"
}
```

Production input/output nằm trong Detection storage, không cần đăng ký dataset_artifacts. Case mới lưu detection_job_id để workbench truy output của đúng job; dataset_artifact_id nullable, giữ lại cho Case nghiên cứu có sẵn. Job phải COMPLETED và mọi event được chọn phải có duy nhất một bản ghi REVIEW/REJECT.

**Payload nội bộ** (không phải body của API công khai):

```json
{
  "project_id": "uuid",
    "dataset_artifact_id": null,
    "detection_job_id": "uuid",
  "model_version_id": "uuid | null",
  "transactions": [
    {
      "event_id": "TX-000123",
      "user_id": "U-889",
      "timestamp": "2026-10-01T02:30:00Z",
      "amount": 25000000,
      "model_score": 0.94,
      "final_action": "REJECT",
      "triggered_rules": [
        {
          "rule_id": "uuid",
          "rule_version_id": "uuid",
          "version_number": 2,
          "rule_code": "R_HIGH_AMOUNT_NIGHT",
          "rule_name": "High amount at night",
          "action": "REJECT",
          "trigger_reason": "amount > 10000000 AND hour >= 0",
          "matched_clauses": ["amount > 10000000"]
        }
      ],
      "feature_contributions": [
        { "feature_name": "amount", "feature_value": 25000000, "contribution": 0.29 }
      ],
      "attributes": { "<raw_schema_column>": "value" }
    }
  ]
}
```

| Trường | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `detection_job_id` | Có cho production | Nguồn output của job, kiểm tra cùng project và COMPLETED. Backend đọc toàn bộ dữ liệu có sẵn trong job để dựng baseline/timeline; không suy diễn lịch sử ngoài dữ liệu đó. |
| `dataset_artifact_id` | Không cho production | Giữ nguồn cho Case nghiên cứu đã có; workbench kiểm tra artifact cùng project. Không ép production thành dataset nghiên cứu. |
| `event_id`, `user_id`, `timestamp`, `amount` | Có | Định danh & giá trị chuẩn của giao dịch. |
| `model_score` | Không | Xác suất gian lận `0.0 → 1.0`; `null` nếu đợt quét không dùng mô hình. |
| `final_action` | Có | Chỉ nhận `REJECT` hoặc `REVIEW`. Giao dịch `ALLOW` không được gửi. Nếu không có rule nào kích hoạt nhưng `model_score ≥ decision_threshold`, Detection gửi `REVIEW`. |
| `triggered_rules` | Không | Chỉ các rule `ACTIVE` có `is_triggered = true`; cấu trúc trùng `RuleExecutionResult` + `matched_clauses`. |
| `feature_contributions` | Không | Top-K đóng góp đặc trưng (SHAP) đã tính sẵn ở Detection; Investigation không tự tính lại. |
| `attributes` | Không | Snapshot giá trị các cột RAW (tên cột theo `project.raw_schema`) của giao dịch — dùng để hiển thị & dựng rule nháp (`SUC-20`). |

**Response `201`:** `ApiResponse` với `data = { "created_case_ids": [...], "accepted_count": n, "skipped_event_ids": [...] }`. Retry toàn bộ giao dịch đã có vẫn trả `201`, `accepted_count = 0`.

**Quy tắc hợp đồng:**
- **BR-IV-C1 (Idempotent):** Unique `(project_id, event_id)`, kể cả Case đã đóng. Gửi lại bỏ qua, không thay snapshot/phán quyết/nguồn gốc.
- **BR-IV-C2 (Một giao dịch = một Case):** Mỗi event mới tạo một Case `OPEN`, dù user đã có Case khác. Không append giao dịch vào Case.
- **BR-IV-C3 (Validation):** Body gửi 1–5000 event IDs và note optional. Job không tồn tại → 404; chưa COMPLETED/thiếu output/ID không tồn tại hoặc trùng trong output/event ALLOW/thiếu context hợp lệ → lỗi, không ghi một phần. Snapshot nội bộ giữ ID chuỗi, timestamp UTC, amount hữu hạn không âm và score nullable/hữu hạn [0,1]. Không dùng giá trị đã làm tròn để hiển thị. Retry cùng event không đổi phán quyết hoặc tạo thêm notes/audit.
- `triggered_rules` chỉ chứa rule REVIEW/REJECT đã kích hoạt, không trùng `rule_version_id`; `is_triggered` nếu gửi phải là true. `execution_time_ms` optional, hữu hạn không âm. Rule ID/version là snapshot lịch sử, không đánh giá lại phiên bản hiện tại.

## SUC-17: Manage cases (Quản lý danh sách hồ sơ điều tra / Case Queue)

### Thông tin chung

- **Mã Use Case:** SUC-17
- **Tên Use Case:** Manage cases (Quản lý danh sách hồ sơ điều tra / Case Queue)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Hệ thống cơ sở dữ liệu (`ICaseRepository`)
- **Mô tả:** Theo dõi, tìm kiếm, lọc/sắp xếp/phân trang và nhận xử lý từng Case giao dịch.
- **Tiền điều kiện:**
    1. Người dùng đã chọn một Dự án (Project) cụ thể. *(Chưa áp dụng đăng nhập/vai trò — [26-10-31])*
    2. Đã có các giao dịch nghi vấn được chuyển tiếp từ `SUC-16 (View detection result)` qua Case Intake Contract (mục 3.0) để khởi tạo bản ghi trong bảng `fraud_cases`.
- **Hậu điều kiện:**
    - *Thành công:* Hiển thị giao dịch và bằng chứng của từng Case; claim cập nhật status/assigned_to/version và ghi `audit_logs` cùng DB transaction.
    - *Thất bại:* Giữ nguyên trạng thái hồ sơ hiện tại.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst truy cập vào mục **Investigation -> Case Queue** trên thanh điều hướng chính hoặc chuyển hướng trực tiếp sau khi nhấn “Send to Investigation” tại `SUC-16`.

### Luồng sự kiện chính (Basic Flow)

1. Fraud Analyst mở màn hình **Case Management Queue** trong phân hệ **Investigation**.
2. Hệ thống truy vấn `fraud_cases` thuộc dự án hiện tại và hiển thị KPI:
    - **Open Cases:** Tổng số hồ sơ đang chờ điều tra (`status = 'OPEN'`).
    - **Critical Priority Cases:** Số Case chưa đóng có `priority = CRITICAL`.
    - **In Progress:** Số hồ sơ đang được chuyên viên thụ lý (`status = 'IN_PROGRESS'`).
    - **Confirmed Fraud / False Positive Ratio:** Tỷ lệ xác nhận gian lận thực tế trên tổng số hồ sơ đã đóng.
3. Hệ thống hiển thị **Bảng Hàng đợi Hồ sơ (Case Queue Table)**, mặc định sắp xếp theo điểm ưu tiên (`priority_score`) giảm dần:
    - Mã hồ sơ (`case_code`, ví dụ: `CASE-2026-00142`).
    - `event_id`, `user_id`, `tx_timestamp`, `amount` của một giao dịch.
    - `model_score` nullable và `final_action` REVIEW/REJECT; không có chỉ số tổng hợp nhóm.
    - Danh sách các mã quy tắc vi phạm (`triggered_rule_codes`).
    - Priority CRITICAL/HIGH/MEDIUM/LOW và status OPEN/IN_PROGRESS/PENDING_CUSTOMER/RESOLVED_FRAUD/RESOLVED_LEGITIMATE.
    - Chuyên viên phụ trách (`assigned_to`) và Thời gian khởi tạo (`created_at`).
4. Fraud Analyst sử dụng bộ lọc đa chiều (Filter Bar) để thu hẹp phạm vi xử lý:
    - Lọc theo trạng thái (`Status`), mức độ ưu tiên (`Priority`), chuyên viên phụ trách (`Assigned to me` / `Unassigned`).
    - Lọc theo rule_code, khoảng model_score hoặc amount; sắp xếp priority_score/amount/created_at giảm dần, phân trang có thứ tự tie-break ổn định.
    - Tìm kiếm trực tiếp theo `case_code`, `user_id`, hoặc `event_id` (mã giao dịch).
5. Claim một Case chưa đóng với expected_version: `status = IN_PROGRESS`, `assigned_to = local-analyst`, version tăng một và ghi audit. Actor do backend cung cấp, không lấy từ client.
6. Fraud Analyst nhấp vào hồ sơ để mở không gian điều tra chi tiết (**Case Investigation Workbench** — chuyển sang `SUC-18`).

### Luồng rẽ nhánh (Alternative Flows)

Không có merge/split hoặc bulk resolve trong scope đã duyệt. Xem Case liên quan không làm thay đổi Case đó.

### Luồng ngoại lệ (Exception Flows)

- **5c. Xung đột nhận hồ sơ (Concurrent Claim Conflict):**
    - Request với expected_version cũ trả `409`, client tải lại Case, không ghi thay đổi/audit. Quy tắc vẫn cần trong single-user vì nhiều tab có thể cùng sửa Case. Cảnh báo nhiều analyst hoãn đến khi có danh tính người dùng.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-01 [26-10-31]:** Priority tính một lần từ giao dịch: `45·(model_score hoặc 0) + 35·action_factor + 10·min(rule_count,3)/3 + 10·min(log10(1+amount)/7,1)`, làm tròn hai chữ số; action_factor = 1 cho REJECT, 0.6 cho REVIEW; rule_count là số mã rule phân biệt. Mức ≥75 CRITICAL, ≥55 HIGH, ≥35 MEDIUM, còn lại LOW. Heuristic này giả định dataset cùng đơn vị tiền, không phải xác suất hay điểm Rule Engine. Escalate nâng priority CRITICAL, không sửa snapshot.
- **BR-IV-02:** Không có API xóa Case. Reopen bắt buộc lý do tối thiểu 10 ký tự, lưu phán quyết cũ trong `audit_logs`.

---

## SUC-18: Review case manually (Điều tra chi tiết hồ sơ & Ra phán quyết)

### Thông tin chung

- **Mã Use Case:** SUC-18
- **Tên Use Case:** Review case manually (Điều tra chi tiết hồ sơ & Ra phán quyết)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ:** DatasetArtifact, ICaseRepository, IBlacklistRepository, IAuditRepository.
- **Mô tả:** Cung cấp không gian làm việc trực quan 3 cột (Investigation Workbench) giúp Fraud Analyst mổ xẻ bằng chứng từ động cơ AI và Rule Engine, đối chiếu giao dịch nghi vấn với chuỗi thời gian và hồ sơ hành vi lịch sử (Baseline) của chính chủ thẻ, ghi nhận kết quả xác minh, đưa ra phán quyết cuối cùng (`Mark as Fraud` / `Mark as Legitimate`), kích hoạt khóa tài khoản/thẻ khẩn cấp (`Block Account/Card`) và đóng vòng lặp phản hồi nhãn dữ liệu (`Ground Truth Feedback Loop`).
- **Tiền điều kiện:** Hồ sơ điều tra (`fraud_cases`) đã tồn tại trong hệ thống. *(Chưa áp dụng phân quyền — [26-10-31])*
- **Hậu điều kiện:**
    - *Thành công:* Riêng Case đang mở được cập nhật phán quyết/reason/summary; nhãn suy ra từ status. Mitigation ghi entity_blacklist và audit cùng DB transaction. Các Case khác của user giữ nguyên.
    - *Thất bại:* Hồ sơ giữ nguyên trạng thái `OPEN` hoặc `IN_PROGRESS`.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst chọn một hồ sơ từ màn hình `SUC-17 (Manage cases)` để bắt đầu điều tra.

### Luồng sự kiện chính (Basic Flow)

1. Fraud Analyst mở một hồ sơ điều tra từ hàng đợi; hệ thống tải dữ liệu chi tiết và hiển thị giao diện **Case Investigation Workbench (Bố cục 3 cột phối hợp)**:
    - **Cột Trái — Hồ sơ Chủ thể & Chuẩn hành vi cơ sở (Subject Profile & Historical Baseline):**
        - `user_id`, trạng thái ACTIVE/BLOCKED suy ra từ blacklist USER_ID, thông tin giao dịch của Case và các Case khác cùng user (status/assignee/link). Danh sách liên quan là query, không phải nhóm có phán quyết chung.
        - **Chỉ số Baseline lịch sử của khách hàng (30–90 ngày trước):** Số tiền giao dịch trung bình (`avg_amount_30d`), số tiền lớn nhất từng chi tiêu (`max_amount_30d`), tần suất giao dịch trung bình/ngày, khung giờ hoạt động phổ biến nhất, danh mục ngành hàng (`merchant_category`) và thiết bị/IP quen thuộc.
    - **Cột Giữa — Bằng chứng Phát hiện & Phân tích Hành vi Trực quan (Evidence & Behavioral Visual Analytics):**
        - **Khối 1 — Bằng chứng Kích hoạt (Why Flagged / Trigger Evidence):**
            - Hiển thị điểm **AI Model Fraud Score** kèm biểu đồ thanh ngang **Top-K Feature Contributions (SHAP / Local Explainability)** lấy từ `feature_contributions` do Detection gửi sang (ví dụ: `velocity_1h = 8` đóng góp `+0.34`). Nếu Detection không gửi, hiển thị trạng thái *“Không có dữ liệu giải thích mô hình”*.
            - Hiển thị danh sách **Triggered Rules** lấy từ `triggered_rules` trong snapshot giao dịch: mã quy tắc (`rule_code`), phiên bản (`version_number`), hành động (`REJECT`/`REVIEW`), lý do kích hoạt (`trigger_reason`) và các mệnh đề khớp (`matched_clauses`, ví dụ: `amount > 10000000`). *[26-10-31]*
        - **Khối 2 — Đối chiếu Chuỗi thời gian & Độ lệch Hành vi (Behavioral Timeline & Deviation View):**
            - **Biểu đồ Trục thời gian Giao dịch (Interactive Transaction Timeline):** Biểu diễn toàn bộ chuỗi giao dịch gần đây của `user_id` theo thời gian (trục hoành: `timestamp`, trục tung: `amount`, màu sắc: giao dịch bình thường màu xám, giao dịch nghi vấn trong Case màu đỏ/cam). Giúp điều tra viên phát hiện trực quan mẫu hình *thử thẻ bằng nhiều giao dịch nhỏ liên tiếp trước khi rút khoản tiền lớn (Card Testing / Micro-fraud -> Cash-out)* hoặc *tấn công tốc độ cao (Velocity Attack)*.
            - **Bảng Đối chiếu Độ lệch (Current vs. Baseline Comparison Table):** Đặt song song giá trị của giao dịch nghi vấn bên cạnh giá trị Baseline lịch sử của chủ thẻ và tô đỏ các thuộc tính vượt ngưỡng bất thường. Quy tắc bất thường [26-10-31]: `amount ≥ 3 × avg_amount`; giờ giao dịch không thuộc top-3 khung giờ quen thuộc; giá trị `device_id` / `ip_address` / `merchant_id` / `merchant_category` (nếu artifact có cột) chưa từng xuất hiện trong lịch sử.
    - **Cột Phải — Bảng Phán quyết, Hành động Ngăn chặn & Nhật ký (Resolution & Mitigation Panel):**
        - Khung nhập **Ghi chú điều tra & Xác minh (`Investigation Notes`)**, nút phán quyết và các tùy chọn ngăn chặn.
2. Fraud Analyst kiểm tra bằng chứng ở Cột Giữa và đối chiếu với thói quen lịch sử của chủ thẻ ở Cột Trái. *(Tab **Network Graph** — `SUC-19` — deferred [26-10-31])*
3. (Tùy chọn theo nghiệp vụ `BUC-06`) Nếu cần xác minh trực tiếp với chủ thẻ, Fraud Analyst liên hệ với khách hàng và ghi nhận kết quả phản hồi (khách xác nhận có thực hiện hay không, thẻ vật lý còn giữ không) vào ô **Investigation Notes**, đồng thời chuyển trạng thái tạm thời sang `PENDING_CUSTOMER` nếu đang chờ khách trả lời.
4. Sau khi có đủ căn cứ, Fraud Analyst đưa ra **Phán quyết điều tra (Case Resolution)** tại Cột Phải:
    - **Trường hợp A — Xác nhận là Gian lận (`Mark as Fraud / Confirmed Fraud`):**
        - Chọn nút **Confirm Fraud**.
        - Chọn **Mã phân loại kịch bản gian lận (`resolution_reason`)**: `CARD_TESTING`, `VELOCITY_ATTACK`, `ACCOUNT_TAKEOVER`, `DEVICE_SHARING_RING`, `COLLUSIVE_MERCHANT`, hoặc `OTHER_FRAUD`.
        - Chọn **Hành động ngăn chặn khẩn cấp (`Mitigation Actions` - hiện thực hóa `BUC-07`)**:
            - **Block User / Card:** Analyst chủ động chọn entity thuộc giao dịch để thêm entity_blacklist (user lấy từ user_id, card từ snapshot). Không tự chọn checkbox. Việc Detection từ chối giao dịch tiếp theo thuộc workstream riêng.
            - `[ ]` **Chặn thiết bị / địa chỉ IP liên đới (`Blacklist Device ID / IP Address`)**.
    - **Trường hợp B — Xác nhận là Giao dịch Hợp lệ / Báo động giả (`Mark as Legitimate / False Positive`):**
        - Chọn nút **Mark as Legitimate (False Positive)**.
        - Chọn **Mã lý do báo động giả (`resolution_reason`)**: `LEGITIMATE_UNUSUAL_SPENDING`, `CUSTOMER_CONFIRMED`, `OVERLY_STRICT_RULE`, `MODEL_FALSE_ALARM`, hoặc `OTHER_LEGITIMATE`.
        - Không whitelist hoặc blacklist khi kết luận legitimate. Phản hồi noisy rule được thống kê từ phán quyết, không cần flag thủ công.
5. Fraud Analyst nhập tóm tắt kết luận cuối cùng (`resolution_summary`) và nhấn **Submit Decision**.
6. Hệ thống thực thi giao dịch cơ sở dữ liệu (Database Transaction):
    - Cập nhật bảng `fraud_cases`: `status = 'RESOLVED_FRAUD'` (hoặc `'RESOLVED_LEGITIMATE'`), `resolved_by = actor`, `resolved_at = NOW()`, `resolution_reason`, `resolution_summary`.
    - verified_label không có cột lưu: RESOLVED_FRAUD = 1, RESOLVED_LEGITIMATE = 0, các trạng thái chưa đóng = null.
    - Nếu fraud và chọn mitigation, ghi entity_blacklist ACTIVE; bỏ qua entry đã ACTIVE cùng type/value. Entity phải thuộc transaction snapshot hoặc user_id. Validation thất bại hủy toàn bộ request.
    - Tăng version và append audit_logs gồm phán quyết trước/sau, note và mitigation. Không sửa/xóa log qua API.
7. Hệ thống thông báo hoàn tất xử lý hồ sơ và tự động chuyển sang hồ sơ ưu tiên tiếp theo trong hàng đợi (nếu bật chế độ *Auto-advance Queue*).

### Luồng rẽ nhánh (Alternative Flows)

- Không có partial resolution vì mỗi Case chỉ chứa một giao dịch.
- **4b. Chuyển cấp điều tra chuyên sâu (Escalate Case to Senior Analyst):**
    - Nếu hồ sơ có dấu hiệu phức tạp hoặc giá trị quá lớn vượt thẩm quyền, Fraud Analyst chọn **Escalate Case**, nâng `priority = 'CRITICAL'`, đính kèm ghi chú phân tích ban đầu (bắt buộc) và gán `assigned_to` cho Senior Analyst / Risk Manager. Không phát sinh trạng thái mới; ghi audit `ESCALATED`.
- **4c. Reopen:** RESOLVED_* → IN_PROGRESS, expected_version và lý do ≥10 ký tự; xóa resolution fields hiện tại, verified_label trở về null. Phán quyết cũ giữ trong audit. Không tự gỡ blacklist.

### Luồng ngoại lệ (Exception Flows)

- **1a. Chủ thể mới chưa có lịch sử giao dịch (Cold-start User):**
    - Baseline 30/90 ngày chỉ dùng timestamp trước giao dịch hiện tại. Không có lịch sử user → population baseline từ các giao dịch quá khứ trong cùng cửa sổ, không mặc định là cùng phân khúc. Nếu population cũng rỗng hoặc artifact unavailable, hiển thị thiếu dữ liệu; không dùng số liệu tương lai/giả. Timeline tối đa 500 giao dịch, Case liên quan hiển thị tối đa 200 và có tổng số.
- **5a. Chưa nhập lý do phán quyết bắt buộc:**
    - Tại bước 5, nếu Fraud Analyst nhấn “Submit Decision” nhưng chưa chọn `resolution_reason` hoặc để trống `resolution_summary`, hệ thống chặn lưu và hiển thị thông báo: *“Vui lòng chọn mã lý do kết luận và nhập tóm tắt bằng chứng điều tra để đảm bảo tuân thủ kiểm toán.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-03 (Bắt buộc giải trình phán quyết - Mandatory Audit Justification):** Mọi phán quyết đóng hồ sơ (`RESOLVED_FRAUD` hoặc `RESOLVED_LEGITIMATE`) cũng như mọi lệnh khóa tài khoản/thẻ (`Block Account/Card`) bắt buộc phải đi kèm `resolution_reason` và `resolution_summary` tối thiểu 10 ký tự để phục vụ kiểm toán nội bộ và trích xuất báo cáo SAR (`BUC-05`).
- **BR-IV-04:** Ground truth suy ra từ Case.status, độc lập với model_score/final_action. Case đang mở/reopen không được coi là nhãn 0. Xuất nhãn cho retraining ở workstream khác phải dùng quy tắc này.

---

## SUC-19: Investigate network (Điều tra đồ thị mạng lưới liên kết)

> **[26-10-31] Deferred:** Thiết kế & cài đặt ở workstream riêng. Nội dung dưới đây giữ nguyên để tham khảo, không thuộc phạm vi hiện tại.

### Thông tin chung

- **Mã Use Case:** SUC-19
- **Tên Use Case:** Investigate network (Điều tra đồ thị mạng lưới liên kết)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Graph Query / Link Analysis Service (`INetworkGraphService`)
- **Mô tả:** Cung cấp công cụ trực quan hóa và khám phá đồ thị liên kết đa thực thể (Entity Link Graph) xoay quanh chủ thể hoặc giao dịch đang điều tra, giúp Fraud Analyst phát hiện các đường dây gian lận có tổ chức như chia sẻ thiết bị/IP (*Device-sharing Fraud*) hoặc điểm chấp nhận thanh toán thông đồng (*Merchant Ring / Clustered Terminal Exploitation*).
- **Tiền điều kiện:**
    1. Người dùng đang mở một hồ sơ điều tra (`SUC-18`) hoặc truy cập trực tiếp công cụ **Network Explorer** trong phân hệ Investigation.
    2. Tập dữ liệu dự án có ánh xạ các trường định danh thực thể liên kết (như `user_id`, `device_id`, `ip_address`, `merchant_id`, `card_id` hoặc `recipient_id`).
- **Hậu điều kiện:**
    - *Thành công:* Đồ thị mạng lưới liên kết được hiển thị trực quan kèm các chỉ số trung tâm/cụm rủi ro; chuyên viên có thể gom các tài khoản đồng phạm vào Case hiện tại, tạo Case đường dây mới (`Fraud Ring Case`) hoặc khóa hàng loạt thực thể trong cụm gian lận.
    - *Thất bại:* Không làm thay đổi dữ liệu hồ sơ hiện tại.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst nhấn tab **Investigate Network (Link Analysis)** bên trong màn hình chi tiết Case (`SUC-18`) hoặc chọn mục **Network Investigation** trên thanh điều hướng.

### Luồng sự kiện chính (Basic Flow)

1. Fraud Analyst mở công cụ **Investigate Network** từ một hồ sơ đang điều tra (hoặc nhập một định danh hạt giống `seed_entity_id` như `user_id`, `device_id`, `ip_address`, `merchant_id`).
2. Hệ thống truy vấn dữ liệu giao dịch và xây dựng đồ thị con (Subgraph) xung quanh nút hạt giống với độ sâu mặc định **1-hop** hoặc **2-hop**:
    - **Các loại Nút thực thể (Entity Nodes):**
        - `User / Account Node` (`user_id`)
        - `Device Node` (`device_id`)
        - `IP Address Node` (`ip_address`)
        - `Merchant Node` (`merchant_id`)
        - `(Tùy chọn) Card / Recipient Node`
    - **Các Cạnh liên kết (Relationship Edges):** Thể hiện các giao dịch hoặc sự kiện dùng chung thực thể, kèm trọng số cạnh là **Số lượng giao dịch (`tx_count`)** và **Tổng số tiền (`total_amount`)**.
3. Hệ thống hiển thị **Khung Đồ thị Tương tác (Interactive Graph Canvas)** cùng bảng thống kê cụm (Cluster Inspector):
    - **Mã màu trạng thái Nút:**
        - *Màu Đỏ:* Thực thể đã bị xác nhận gian lận (`CONFIRMED_FRAUD` / `BLOCKED`).
        - *Màu Cam:* Thực thể đang có Case nghi vấn chờ xử lý (`OPEN` / `HIGH RISK`).
        - *Màu Xanh/Xám:* Thực thể bình thường chưa có cảnh báo.
    - **Cảnh báo Mẫu hình Đồ thị Tự động (Graph Pattern Highlights):** Hệ thống tự động tô sáng các cấu trúc bất thường:
        - *Star / Hub Pattern trên Device hoặc IP:* Một `device_id` hoặc `ip_address` kết nối tới nhiều `user_id` khác nhau trong cửa sổ thời gian ngắn (dấu hiệu *Device-sharing Fraud Ring*).
        - *Dense Fan-in trên Merchant:* Hàng loạt thẻ/tài khoản bị cảnh báo cùng quẹt tiền dồn dập vào một `merchant_id` trong thời gian ngắn (dấu hiệu *Merchant Ring Fraud*).
4. Fraud Analyst tương tác trên đồ thị để mở rộng điều tra:
    - Nhấp đúp vào một nút trung gian (ví dụ: một `device_id` khả nghi) để **Mở rộng nhánh liên kết (Expand Neighbors +1 hop)** và xem tất cả các `user_id` khác từng dùng thiết bị đó.
    - Sử dụng thanh bộ lọc đồ thị (Graph Filter Bar): lọc theo loại nút thực thể, lọc theo khung thời gian phát sinh liên kết (Time Window Slider), hoặc ẩn các nút điểm bán hàng lớn phổ biến (Super-nodes) để tránh nhiễu.
    - Nhấp vào một nút hoặc một cạnh bất kỳ để xem danh sách các giao dịch chi tiết tạo nên liên kết đó ở ngăn **Edge Transaction Inspector** bên phải.
5. Khi phát hiện một cụm tài khoản/thiết bị đồng phạm (Fraud Ring), Fraud Analyst quét chọn (Multi-select / Lasso select) các nút trong cụm và chọn một trong các hành động:
    - **Add Linked Transactions to Current Case:** Gom toàn bộ giao dịch nghi vấn của các tài khoản liên đới vào hồ sơ đang điều tra để xử lý chung một lần.
    - **Block / Blacklist Selected Entities:** Đưa toàn bộ `device_id`, `ip_address` và các `user_id` đồng phạm vào danh sách khóa (`entity_watchlists`) và đánh dấu `RESOLVED_FRAUD`.

### Luồng rẽ nhánh (Alternative Flows)

- **3a. Xem điểm bất thường đồ thị từ mô hình GNN (GNN Node/Subgraph Risk Overlay):**
    - Nếu đợt phát hiện (`SUC-15`) sử dụng mô hình họ đồ thị (`GNN`), hệ thống hiển thị thêm kích thước nút tỷ lệ thuận với `gnn_risk_prob` và làm nổi bật các cạnh có trọng số chú ý cao (Graph Attention / Edge Importance).

### Luồng ngoại lệ (Exception Flows)

- **2a. Tập dữ liệu chỉ có trường cơ bản, thiếu trường thực thể phụ trợ:**
    - Nếu `DatasetArtifact` chỉ ánh xạ 5 trường bắt buộc (`event_id`, `timestamp`, `amount`, `user_id`, `label`) mà không có các trường tùy chọn (`device_id`, `ip_address`, `merchant_id`), hệ thống hiển thị thông báo hướng dẫn: *“Tập dữ liệu hiện tại chỉ chứa định danh chủ thể đơn lẻ (user_id), chưa có các trường thực thể liên kết (như device_id, ip_address, merchant_id) để dựng đồ thị đa thực thể.”*
- **4a. Quá tải số lượng nút khi mở rộng nút bậc cao (Super-node Explosion):**
    - Tại bước 4, nếu người dùng nhấn mở rộng một nút `merchant_id` cực lớn (ví dụ siêu thị có hơn 10.000 khách hàng giao dịch), hệ thống tự động giới hạn hiển thị **Top 50 nút có điểm rủi ro cao nhất** và hiển thị thông báo: *“Thực thể này có N liên kết. Hệ thống đang hiển thị 50 liên kết có điểm rủi ro cao nhất để đảm bảo hiệu năng trực quan.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-05:** Mỗi lần mở rộng đồ thị (`Expand Node`) trên giao diện được giới hạn tối đa `200` nút hiển thị đồng thời trên Canvas nhằm đảm bảo tốc độ tương tác mượt mà và tránh hiện tượng rối đồ thị (*Hairball Graph*).

---

## SUC-20: Manage rules & blacklist from investigation [26-10-31]

### Thông tin chung

- **Mã Use Case:** SUC-20
- **Tên Use Case:** Manage rules & blacklist from investigation.
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Data Scientist
- **Tác nhân phụ:** RuleManager, IBlacklistRepository, IAuditRepository.
- **Mô tả:** Tạo rule nháp từ một Case fraud, thống kê phản hồi theo rule version, và quản lý blacklist. Không whitelist.
- **Tiền điều kiện:** Người dùng đã chọn một Dự án. *(Chưa áp dụng phân quyền — [26-10-31])*
- **Hậu điều kiện:**
    - *Thành công:* Rule DRAFT được lưu qua RuleManager hiện có; điều chỉnh rule tại Rule Studio; thêm/gỡ entity_blacklist được audit cùng transaction.
    - *Thất bại:* Không thay đổi cấu hình tập luật hoặc danh sách chặn hiện tại.
- **Sự kiện kích hoạt:** Create Rule from Case hoặc Investigation -> Policies (Blacklist / Rule Feedback).

### Luồng sự kiện chính (Basic Flow)

1. **Kịch bản 1 — Trích xuất quy tắc mới từ mẫu gian lận vừa điều tra (Create Quick Rule from Case):**
    - Case phải ở RESOLVED_FRAUD. Chuyên viên nhấn Create Rule from Case.
    - Hệ thống dựng điều kiện JsonLogic gợi ý (`{"and": [...]}`) từ chính giao dịch của Case:
        - Chọn tối đa 3 đặc trưng có `contribution > 0` lớn nhất trong `feature_contributions` mà tên cột tồn tại trong `attributes` và `project.raw_schema`.
        - Cột `NUMERIC` → `{">=": [{"var": col}, value]}`; cột khác → `{"==": [{"var": col}, value]}`.
        - Không có đặc trưng phù hợp → trả điều kiện rỗng kèm thông báo để chuyên viên tự xây dựng.
    - Hệ thống mở **Rule Studio** (`SUC-11`) với điều kiện gợi ý điền sẵn; Fraud Analyst chỉnh ngưỡng, đặt `rule_code`, `name`, chọn `action` (`REVIEW` hoặc `REJECT`).
    - Nếu Case có dataset_artifact_id thì preselect artifact đó khi Dry-run. Case production không có artifact nghiên cứu: chuyên viên chọn tập kiểm thử được quản lý trong Rule Studio; không tự đăng ký file production hoặc dùng nhầm artifact huấn luyện. Rule lưu DRAFT, giữ source_case_id/detection_job_id làm provenance.
2. **Kịch bản 2 — Đánh giá và tinh chỉnh quy tắc gây báo động giả (Tune Noisy Rules from Investigation Feedback):**
    - Thống kê theo `(rule_id, rule_version_id)` từ snapshot từng Case: cases_triggered, TP (status fraud), FP (status legitimate), pending (chưa đóng hoặc reopen).
    - `verified_false_positive_ratio = FP / (TP + FP)`, null nếu chưa có phán quyết. Đây là tỷ lệ báo động giả trong cảnh báo đã xác minh, không phải FPR chuẩn `FP/(FP+TN)` vì không có tập TN.
    - Tỷ lệ >80% hiển thị cảnh báo; Tune in Rule Studio mở đúng rule. Snapshot version cũ không thay đổi khi chỉnh rule hiện tại.
3. **Quản lý Blacklist:** Tìm kiếm/lọc/thêm/gỡ USER_ID, CARD_ID, DEVICE_ID, IP_ADDRESS, MERCHANT_ID. Reason bắt buộc tối thiểu 10 ký tự. Gỡ chuyển REMOVED và lưu removed_at/by; không xóa vật lý. Detection sử dụng blacklist ở workstream riêng.

### Luồng ngoại lệ (Exception Flows)

- **3a. Trùng blacklist ACTIVE:** Trả 409, không tạo entry/audit trùng.
- ~~**1a. Người dùng không có quyền triển khai trực tiếp (`ACTIVE`) quy tắc**~~ — *Bỏ [26-10-31]: chưa áp dụng phân quyền; rule tạo từ Investigation luôn ở `DRAFT`.*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-06 [26-10-31]:** Mọi quy tắc được tạo mới hoặc chỉnh sửa từ phân hệ Investigation đi qua Rule Engine hiện có (`RuleManager`): điều kiện JsonLogic, kiểm tra cột theo `project.raw_schema` (`BR-PM-04`, `BR-PM-05`) và tính duy nhất của `rule_code` trong project.
- **BR-IV-07 [26-10-31]:** Partial unique `(project_id, entity_type, entity_value) WHERE status = ACTIVE`. Quy tắc blacklist/whitelist đối lập trước đây không còn áp dụng.

---

## SUC-21: Run AI Case Copilot (Trợ lý AI tự động tổng hợp & tóm tắt điều tra) *(Chức năng nâng cao)*

> **[26-10-31] Deferred:** Thiết kế & cài đặt ở workstream riêng (`usfds-agent` hiện tại chỉ là POC, không tái sử dụng). Nội dung dưới đây giữ nguyên để tham khảo.

### Thông tin chung

- **Mã Use Case:** SUC-21
- **Tên Use Case:** Run AI Case Copilot (Trợ lý AI tự động tổng hợp & tóm tắt điều tra)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Investigation AI Agent (`CaseInvestigationAgent` / LLM Service)
- **Mô tả:** Hiện thực hóa use case AI Agent ưu tiên số 1 trong tài liệu [Nghiên cứu tích hợp AI Agent vào FDS](https://app.notion.com/p/Nghi-n-c-u-t-ch-h-p-AI-Agent-v-o-FDS-3b4b99c6a95080cd82d3f8d03101e218?pvs=21): cho phép Fraud Analyst kích hoạt AI Agent tự động thu thập toàn bộ ngữ cảnh của hồ sơ (dữ liệu giao dịch, điểm mô hình, đặc trưng SHAP, các quy tắc vi phạm, độ lệch so với Baseline lịch sử và các liên kết đồ thị bậc 1), từ đó diễn giải nguyên nhân cảnh báo bằng ngôn ngữ tự nhiên, đề xuất bước điều tra tiếp theo và soạn sẵn bản nháp tóm tắt điều tra (phục vụ báo cáo SAR).
- **Tiền điều kiện:** Hồ sơ điều tra đang được mở trong `SUC-18`; dịch vụ LLM / AI Agent đã được cấu hình kết nối.
- **Hậu điều kiện:** Bản phân tích tổng hợp và nháp kết luận điều tra (`ai_investigation_brief`) được sinh ra và hiển thị trong khung Copilot của hồ sơ; mọi kết luận cuối cùng vẫn bắt buộc do con người (`Fraud Analyst`) xác nhận.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst nhấn nút **“Generate AI Case Summary”** trong màn hình chi tiết Case (`SUC-18`).

### Luồng sự kiện chính (Basic Flow)

1. Tại màn hình chi tiết hồ sơ (`SUC-18`), Fraud Analyst nhấn nút **Generate AI Case Summary (AI Copilot)**.
2. Hệ thống đóng gói ngữ cảnh có cấu trúc của hồ sơ (`CaseInvestigationContext`) gồm:
    - Thông tin giao dịch nghi vấn (`mapped_data`, `enriched_features`).
    - Kết quả từ Detection (`model_score`, Top SHAP features, `triggered_rules` kèm `condition_snapshot`).
    - Thống kê Baseline 30 ngày của `subject_user_id` và tóm tắt số lượng thực thể liên kết bậc 1 (số tài khoản dùng chung `device_id` / `ip_address`).
3. `CaseInvestigationAgent` phân tích ngữ cảnh và trả về bản tóm tắt có cấu trúc gồm 3 phần:
    - **Tóm tắt lý do cảnh báo (Why Flagged Narrative):** Diễn giải ngắn gọn bằng ngôn ngữ tự nhiên vì sao giao dịch bị bắt (kết hợp cả lý do từ mô hình AI và quy tắc vi phạm).
    - **Phân tích các điểm bất thường chính (Key Behavioral Anomalies):** Liệt kê các điểm lệch rõ nhất so với thói quen của chủ thẻ và các dấu hiệu liên kết mạng lưới (nếu có).
    - **Đề xuất hành động & Nháp biên bản điều tra (Recommended Next Steps & Draft Narrative):** Gợi ý các câu hỏi cần xác minh với khách hàng, đề xuất hướng xử lý và soạn sẵn đoạn văn bản tóm tắt chuẩn hóa để Fraud Analyst có thể sao chép/chỉnh sửa đưa vào `resolution_summary` hoặc báo cáo SAR (`BUC-05`).
4. Fraud Analyst xem xét bản phân tích của AI, nhấn **Copy to Resolution Notes** (nếu đồng ý), chỉnh sửa lại theo nhận định chuyên môn và thực hiện phán quyết chính thức tại `SUC-18`.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-08 (Human-in-the-loop Governance):** AI Case Copilot chỉ đóng vai trò hỗ trợ tổng hợp thông tin và soạn bản nháp (`Advisory Only`), tuyệt đối không được tự động đóng hồ sơ (`RESOLVED_*`) hay tự động khóa tài khoản của khách hàng khi chưa có thao tác xác nhận của `Fraud Analyst`.

---

# 4. Thiết kế Cơ sở Dữ liệu & Giao diện (UI/UX) phân hệ Investigation

## 4.1. Schema đã chốt [26-10-31]

SQLite qua SQLAlchemy; domain entity dataclass thuần. UUID lưu String(36), datetime UTC, JSON snapshots. Không có bảng CaseTransaction.

### Case -> fraud_cases
| Field | DB type | Null | Ràng buộc |
| --- | --- | --- | --- |
| case_id | String(36) | Không | PK, UUID do ứng dụng sinh |
| project_id | String(36) | Không | Project scope kiểm tra tại API, như quy ước hiện có |
| case_code | String(64) | Không | Unique với project_id; CASE-year-UUIDhex để không cần counter |
| event_id, user_id | String(255) | Không | Unique project_id/event_id |
| tx_timestamp | DateTime UTC | Không | Timestamp giao dịch, khác thời gian tạo Case |
| amount | Float | Không | Hữu hạn, >=0; đơn vị tiền của artifact |
| model_score | Float | Có | Hữu hạn, [0,1] |
| final_action | String(20) | Không | REVIEW/REJECT, snapshot Detection |
| triggered_rules, triggered_rule_codes | JSON | Không | Snapshot lịch sử; codes là projection để query |
| feature_contributions, attributes | JSON | Không | []/{} khi không có dữ liệu |
| dataset_artifact_id | String(36) | Có | Nguồn nghiên cứu có sẵn, validate cùng project |
| detection_job_id, model_version_id | String(36) | Có | Job là nguồn production; API kiểm tra project/status/output, không nhận đường dẫn client |
| status | String(30) | Không | Năm trạng thái nêu tại SUC-17 |
| priority, priority_score | String(20), Float | Không | BR-IV-01; escalation không đổi model score |
| assigned_to | String(100) | Có | Claim = local-analyst |
| resolution_reason, resolution_summary | String(50), Text | Có | Bắt buộc khi đóng; reason phù hợp verdict |
| resolved_at, resolved_by | DateTime UTC, String(100) | Có | Thông tin phán quyết hiện tại |
| version | Integer | Không | Bắt đầu 1, CAS update tăng 1 |
| created_at, updated_at | DateTime UTC | Không | Lifecycle |

Index queue `(project_id,status,priority_score)`, user `(project_id,user_id)`. verified_label chỉ có trong response/projection, không có cột riêng. Không max_model_score, tổng tiền nhóm, merged_into_case_id hoặc MERGED.

<!-- [26-11-01] Migration giữ Case/blacklist/audit và đổi dataset_artifact_id thành nullable; bỏ ORM/repository bảng investigation_cases, drop khi rỗng và dừng upgrade nếu bảng legacy còn dữ liệu để tránh mất dữ liệu. -->

### EntityBlacklist -> entity_blacklist
| Field | DB type | Null | Ràng buộc |
| --- | --- | --- | --- |
| blacklist_id | String(36) | Không | PK |
| project_id | String(36) | Không | Index |
| entity_type, entity_value | String(30), String(255) | Không | USER_ID/CARD_ID/DEVICE_ID/IP_ADDRESS/MERCHANT_ID |
| status | String(20) | Không | ACTIVE/REMOVED |
| reason | Text | Không | >=10 ký tự sau trim |
| source_case_id | String(36) | Có | FK fraud_cases, có thể null khi thêm tay |
| created_by, created_at | String(100), DateTime UTC | Không | Actor backend |
| removed_by, removed_at | String(100), DateTime UTC | Có | Không xóa vật lý |

Partial unique `(project_id,entity_type,entity_value) WHERE status='ACTIVE'`. Không list_type/expires_at hoặc whitelist.

### AuditLog -> audit_logs (dùng chung)
| Field | DB type | Null | Ràng buộc |
| --- | --- | --- | --- |
| log_id | String(36) | Không | PK |
| project_id | String(36) | Có | Hỗ trợ hoạt động cấp hệ thống trong tương lai |
| entity_type, entity_id | String(40), String(255) | Không | CASE hoặc BLACKLIST_ENTRY trong scope này |
| action | String(40) | Không | CREATED/CLAIM/RESOLVE_FRAUD/RESOLVE_LEGITIMATE/REOPEN/PENDING_CUSTOMER/ESCALATE/NOTE_ADDED/REMOVED |
| actor | String(100) | Không | local-analyst hiện tại, không phải danh tính xác thực |
| note, details | Text, JSON | Có/Không | Lý do/ghi chú và before/after/mitigation |
| created_at | DateTime UTC | Không | Append-only qua repository/API |

Index `(project_id,entity_type,entity_id,created_at)` và `(project_id,created_at)`. Không FK case_id vì audit dùng chung nhiều loại entity. Ghi cùng transaction với thao tác chính; scope này không mở rộng audit các module khác. Interface chỉ append/list, không tuyên bố chống sửa DB trực tiếp.

## 4.2. Đặc tả Bố cục Giao diện (UI/UX Layout)

Để chuyên viên phân tích không phải chuyển đổi rời rạc giữa nhiều màn hình, giao diện phân hệ **Investigation** được thiết kế gồm **3 chế độ hiển thị chính**:

> **[26-10-31] Phạm vi hiện tại:** Case Queue, Case Workbench, Policies (Blacklist / Rule Feedback). Không Network/Copilot/whitelist hoặc bulk controls.

| **Màn hình / Khu vực** | **Thành phần Giao diện (UI Components)** | **Mục đích trải nghiệm (UX Rationale)** |
| --- | --- | --- |
| **Case Queue** | KPI open/critical/in-progress/confirmed fraud ratio; filters/sort/pagination; mỗi dòng là một event với amount, model_score, final_action, rule codes, status và claim. | Ưu tiên từng giao dịch, không có nhóm phán quyết chung. |
| **Case Workbench** | Desktop ba cột Subject & Baseline / Evidence & Timeline / Decision & Audit; mobile xếp tuần tự. Baseline 30/90 ngày, chart contributions, related Case links, notes/reason/summary/mitigation và reopen. | Đủ ngữ cảnh nhưng phán quyết độc lập. |
| **Policies** | Blacklist tìm/lọc/thêm/gỡ; Rule Feedback theo version với TP/FP/pending và tỷ lệ FP đã xác minh; mở Rule Studio hiện có. | Khép kín feedback, không thêm rule engine mới. |