# Đặc tả use case hệ thống phân hệ Investigation

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7?pvs=21)
Stage: 3. Design
Status: Not started
Task ID: TASK-94

# 0. Tài liệu liên quan

- [Tìm hiểu quy trình nghiệp vụ FDS](https://app.notion.com/p/T-m-hi-u-quy-tr-nh-nghi-p-v-FDS-3e5b99c6a95080568644ec2069d8d6d4?pvs=21)
- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)
- [Đặc tả use case hệ thống phân hệ Detection](https://app.notion.com/p/c-t-use-case-h-th-ng-ph-n-h-Detection-3f9b99c6a95080e8a8f8e8f4f21c2728?pvs=21)
- [Thiết kế và cài đặt rule engine](https://app.notion.com/p/Thi-t-k-v-c-i-t-rule-engine-3d5b99c6a95080ac90cecd4e8cca834c?pvs=21)
- [Nghiên cứu tích hợp AI Agent vào FDS](https://app.notion.com/p/Nghi-n-c-u-t-ch-h-p-AI-Agent-v-o-FDS-3b4b99c6a95080cd82d3f8d03101e218?pvs=21)

# 1. Tổng quan nghiệp vụ Điều tra (Investigation)

Phân hệ **Investigation** hiện thực hóa nghiệp vụ **BUC-02 (Điều tra giao dịch)**, **BUC-06 (Liên hệ xác minh)** và **BUC-07 (Tạm dừng / khóa thẻ khẩn cấp)**, đồng thời đóng vai trò khép kín vòng lặp phản hồi dữ liệu (Feedback Loop) cho **BUC-04 (Cập nhật, tối ưu chính sách rủi ro)**.

Sau khi phân hệ **Detection** thực thi chấm điểm hàng loạt (`SUC-15`) và xuất danh sách kết quả nghi vấn (`SUC-16`), các giao dịch bị gắn cờ (`REJECT`, `REVIEW`, `ALERT`) được chuyển sang phân hệ **Investigation** để gom thành các **Hồ sơ điều tra (Cases)**. Tại đây, chuyên viên phân tích gian lận (`Fraud Analyst`) sử dụng không gian điều tra trực quan để trả lời 4 câu hỏi cốt lõi:

1. **Tại sao giao dịch/chủ thể này bị hệ thống bắt? (Trigger Evidence):** Xem điểm rủi ro từ mô hình AI (`model_score`), độ đóng góp của từng đặc trưng (SHAP / Top Feature Contributions), danh sách mã quy tắc bị vi phạm (`triggered_rules`) và giá trị dữ liệu thực tế tại thời điểm vi phạm (`condition_snapshot`).
2. **Hành vi giao dịch này có thực sự lệch khỏi thói quen lịch sử của chủ thẻ không? (Behavioral & Temporal Profile):** Đối chiếu giao dịch nghi vấn với hồ sơ cơ sở (Baseline 30–90 ngày) của chính `user_id` đó theo 5 chiều: vận tốc giao dịch/thử thẻ nhỏ (*Velocity / Card Testing*), tỷ lệ số tiền so với mức trung bình (`ratio_to_avg_amount`), khung giờ giao dịch, thiết bị/IP và mã ngành điểm bán (`merchant_category`).
3. **Đây là vụ việc đơn lẻ hay nằm trong đường dây có tổ chức? (Network / Link Analysis):** Khám phá đồ thị liên kết thực thể (`user_id` — `device_id` — `ip_address` — `merchant_id` — `card_id`) nhằm vạch trần các cụm dùng chung thiết bị (*Device-sharing Fraud*) hoặc điểm bán hàng thông đồng (*Merchant Ring Fraud*).
4. **Phán quyết cuối cùng và hành động ngăn chặn là gì? (Resolution & Feedback Loop):** Xác nhận hồ sơ là gian lận thật (`CONFIRMED_FRAUD`) hay cảnh báo giả (`FALSE_POSITIVE` / `LEGITIMATE`), thực hiện khóa thẻ/tài khoản hoặc đưa thực thể vào danh sách chặn (`Watchlist / Blacklist`), đồng thời cập nhật nhãn xác thực (`verified_label`) và tinh chỉnh lại tập luật.

# 2. Tóm tắt danh mục Use Case hệ thống

Dưới đây là danh mục Use Case hệ thống (SUC) cho phân hệ **Investigation** trong FDS (tiếp nối mã số từ `SUC-16` của phân hệ Detection).

| **Mã SUC** | **Tên Use Case** | **Primary Actor** | **Mô tả tóm tắt** |
| --- | --- | --- | --- |
| **SUC-17** | **Manage cases** | Fraud Analyst | Quản lý hàng đợi hồ sơ điều tra (Case Queue), lọc/sắp xếp theo mức độ ưu tiên, phân công xử lý, gộp hồ sơ cùng chủ thể hoặc xử lý hàng loạt. |
| **SUC-18** | **Review case manually** | Fraud Analyst | Điều tra chi tiết hồ sơ trên giao diện Workbench 3 cột (xem bằng chứng AI/Rule, đối chiếu chuỗi thời gian & hành vi lịch sử), gắn nhãn phán quyết (`Fraud` / `Legitimate`) và thực hiện hành động khóa tài khoản/thẻ. |
| **SUC-19** | **Investigate network** | Fraud Analyst | Khám phá đồ thị mạng lưới liên kết đa thực thể (User, Card, Device, IP, Merchant) theo các bậc liên kết (1-hop, 2-hop) để phát hiện và xử lý các đường dây gian lận có tổ chức (Fraud Rings). |
| **SUC-20** | **Manage rules & watchlists from investigation** | Fraud Analyst, Data Scientist | Trích xuất nhanh quy tắc phát hiện mới từ mẫu gian lận vừa điều tra, báo cáo quy tắc gây báo động giả (Noisy Rule) để tinh chỉnh ngưỡng, và quản lý danh sách chặn/miễn trừ thực thể (`Blacklist` / `Whitelist`). |
| **SUC-21** | **Run AI Case Copilot** *(Mở rộng)* | Fraud Analyst | Sử dụng AI Agent tự động tổng hợp ngữ cảnh đa nguồn của Case, giải thích lý do gắn cờ bằng ngôn ngữ tự nhiên và sinh bản nháp nhận định điều tra phục vụ báo cáo SAR. |

# 3. Chi tiết đặc tả Use Case

Phần này đặc tả chi tiết các Use Case thuộc phân hệ **Investigation** (`SUC-17` đến `SUC-21`).

## SUC-17: Manage cases (Quản lý danh sách hồ sơ điều tra / Case Queue)

### Thông tin chung

- **Mã Use Case:** SUC-17
- **Tên Use Case:** Manage cases (Quản lý danh sách hồ sơ điều tra / Case Queue)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Hệ thống cơ sở dữ liệu (`ICaseRepository`)
- **Mô tả:** Cho phép Fraud Analyst theo dõi toàn bộ danh sách các hồ sơ nghi vấn gian lận (`Cases`) được sinh ra từ các tác vụ phát hiện (`SUC-16`), tìm kiếm, lọc và sắp xếp theo độ ưu tiên rủi ro, nhận xử lý hồ sơ (`Assign`), gộp các hồ sơ có cùng chủ thể (`Merge Cases`) hoặc đóng hàng loạt các hồ sơ có mẫu rõ ràng.
- **Tiền điều kiện:**
    1. Người dùng đã đăng nhập hệ thống với vai trò `Fraud Analyst` và chọn một Dự án (Project) cụ thể.
    2. Đã có các giao dịch nghi vấn được chuyển tiếp từ `SUC-16 (View detection result)` sang phân hệ Investigation để khởi tạo bản ghi trong bảng `fraud_cases`.
- **Hậu điều kiện:**
    - *Thành công:* Danh sách hồ sơ điều tra hiển thị đầy đủ kèm các chỉ số rủi ro tổng hợp; trạng thái phân công (`assigned_to`) hoặc trạng thái hồ sơ (`status`) được cập nhật chính xác và ghi vết vào `case_audit_logs`.
    - *Thất bại:* Giữ nguyên trạng thái hồ sơ hiện tại.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst truy cập vào mục **Investigation -> Case Queue** trên thanh điều hướng chính hoặc chuyển hướng trực tiếp sau khi nhấn “Send to Investigation” tại `SUC-16`.

### Luồng sự kiện chính (Basic Flow)

1. Fraud Analyst mở màn hình **Case Management Queue** trong phân hệ **Investigation**.
2. Hệ thống truy vấn bảng `fraud_cases` và `case_transactions` thuộc dự án hiện tại, tính toán các thẻ thống kê nhanh (KPI Summary Cards) và hiển thị trên đầu trang:
    - **Open Cases:** Tổng số hồ sơ đang chờ điều tra (`status = 'OPEN'`).
    - **Critical Priority Cases:** Số hồ sơ có mức độ ưu tiên khẩn cấp (`priority = 'CRITICAL'`).
    - **In Progress:** Số hồ sơ đang được chuyên viên thụ lý (`status = 'IN_PROGRESS'`).
    - **Confirmed Fraud / False Positive Ratio:** Tỷ lệ xác nhận gian lận thực tế trên tổng số hồ sơ đã đóng.
3. Hệ thống hiển thị **Bảng Hàng đợi Hồ sơ (Case Queue Table)**, mặc định sắp xếp theo điểm ưu tiên (`priority_score`) giảm dần:
    - Mã hồ sơ (`case_code`, ví dụ: `CASE-2026-00142`).
    - Định danh chủ thể chính (`subject_user_id` / `card_id`) và trạng thái chủ thể hiện tại (`ACTIVE`, `BLOCKED`, `WATCHLISTED`).
    - Số lượng giao dịch nghi vấn gom trong hồ sơ (`flagged_tx_count`) và Tổng giá trị tiền rủi ro (`total_flagged_amount`).
    - Điểm xác suất AI cao nhất (`max_model_score` từ `0.00` đến `1.00`) và Điểm tập luật cao nhất (`max_rule_score` từ `0.0` đến `100.0`).
    - Danh sách các mã quy tắc vi phạm nổi bật (`triggered_rule_codes`).
    - Mức độ ưu tiên (`priority`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) và Trạng thái hồ sơ (`OPEN`, `IN_PROGRESS`, `RESOLVED_FRAUD`, `RESOLVED_LEGITIMATE`).
    - Chuyên viên phụ trách (`assigned_to`) và Thời gian khởi tạo (`created_at`).
4. Fraud Analyst sử dụng bộ lọc đa chiều (Filter Bar) để thu hẹp phạm vi xử lý:
    - Lọc theo trạng thái (`Status`), mức độ ưu tiên (`Priority`), chuyên viên phụ trách (`Assigned to me` / `Unassigned`).
    - Lọc theo mã quy tắc bị kích hoạt (`rule_code`), khoảng điểm `max_model_score` hoặc khoảng tiền giao dịch.
    - Tìm kiếm trực tiếp theo `case_code`, `user_id`, `event_id` (mã giao dịch), `device_id`, hoặc `ip_address`.
5. Fraud Analyst chọn một hồ sơ trong hàng đợi và nhấn **Claim / Assign to Me** để nhận trách nhiệm điều tra; hệ thống cập nhật `status = 'IN_PROGRESS'`, `assigned_to = current_user` và ghi nhận vào `case_audit_logs`.
6. Fraud Analyst nhấp vào hồ sơ để mở không gian điều tra chi tiết (**Case Investigation Workbench** — chuyển sang `SUC-18`).

### Luồng rẽ nhánh (Alternative Flows)

- **5a. Gộp nhiều hồ sơ của cùng một chủ thể hoặc cùng đường dây (Merge Cases):**
    - Nếu trong hàng đợi xuất hiện nhiều hồ sơ `OPEN` rời rạc của cùng một `subject_user_id` (hoặc từ các đợt chạy `Detection Job` khác nhau), Fraud Analyst tích chọn các hồ sơ đó và nhấn **Merge Cases**.
    - Hệ thống chuyển toàn bộ liên kết giao dịch trong `case_transactions` về hồ sơ gốc có độ ưu tiên cao nhất, tính lại `total_flagged_amount`, `max_model_score`, và đánh dấu các hồ sơ phụ thành `MERGED`.
- **5b. Phán quyết nhanh hàng loạt (Bulk Resolution):**
    - Đối với các hồ sơ có cùng một mẫu vi phạm rõ ràng (ví dụ: cùng bị bắt bởi một quy tắc mới phát hiện là lỗi cấu hình gây báo động giả), Fraud Analyst tích chọn các hồ sơ, nhấn **Bulk Resolve**, chọn phán quyết (`RESOLVED_LEGITIMATE` hoặc `RESOLVED_FRAUD`) và nhập lý do chung để đóng hàng loạt.

### Luồng ngoại lệ (Exception Flows)

- **5c. Xung đột nhận hồ sơ (Concurrent Claim Conflict):**
    - Tại bước 5, nếu hai Fraud Analyst cùng nhấn “Claim” một hồ sơ tại cùng một thời điểm, hệ thống áp dụng cơ chế khóa lạc quan (Optimistic Locking) ưu tiên yêu cầu đến trước và hiển thị thông báo cho người thứ hai: *“Hồ sơ này vừa được chuyên viên [Tên] nhận xử lý. Vui lòng làm mới danh sách.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-01 (Xếp hạng độ ưu tiên tự động - Case Priority Scoring):** Khi khởi tạo hồ sơ, hệ thống tự động tính điểm ưu tiên `priority_score` dựa trên tổ hợp có trọng số giữa xác suất mô hình (`max_model_score`), điểm rủi ro tập luật (`max_rule_score`), hành động nghiêm trọng nhất (`REJECT` > `REVIEW` > `ALERT`) và quy mô số tiền (`total_flagged_amount`) để phân loại vào 4 mức: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- **BR-IV-02:** Một hồ sơ ở trạng thái đã đóng (`RESOLVED_FRAUD` hoặc `RESOLVED_LEGITIMATE`) không thể bị xóa khỏi hệ thống; mọi thao tác mở lại (`Reopen Case`) bắt buộc phải nhập lý do giải trình vào `case_audit_logs`.

---

## SUC-18: Review case manually (Điều tra chi tiết hồ sơ & Ra phán quyết)

### Thông tin chung

- **Mã Use Case:** SUC-18
- **Tên Use Case:** Review case manually (Điều tra chi tiết hồ sơ & Ra phán quyết)
- **Tác nhân chính (Primary Actor):** Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Hệ thống lưu trữ dữ liệu (`DatasetArtifact` / `ICaseRepository`), Dịch vụ quản lý danh sách chặn (`IWatchlistService`)
- **Mô tả:** Cung cấp không gian làm việc trực quan 3 cột (Investigation Workbench) giúp Fraud Analyst mổ xẻ bằng chứng từ động cơ AI và Rule Engine, đối chiếu giao dịch nghi vấn với chuỗi thời gian và hồ sơ hành vi lịch sử (Baseline) của chính chủ thẻ, ghi nhận kết quả xác minh, đưa ra phán quyết cuối cùng (`Mark as Fraud` / `Mark as Legitimate`), kích hoạt khóa tài khoản/thẻ khẩn cấp (`Block Account/Card`) và đóng vòng lặp phản hồi nhãn dữ liệu (`Ground Truth Feedback Loop`).
- **Tiền điều kiện:** Hồ sơ điều tra (`fraud_cases`) đã tồn tại trong hệ thống; người dùng có quyền `case: review`.
- **Hậu điều kiện:**
    - *Thành công:* Hồ sơ được cập nhật trạng thái phán quyết (`RESOLVED_FRAUD` hoặc `RESOLVED_LEGITIMATE`) kèm mã lý do (`resolution_reason`) và ghi chú điều tra (`resolution_notes`); nhãn thực tế (`verified_label = 1` hoặc `0`) được cập nhật cho các giao dịch thuộc hồ sơ; nếu chọn hành động ngăn chặn, định danh tài khoản/thẻ/thiết bị được đưa vào danh sách khóa (`BLOCKED` trong bảng `entity_watchlists`); toàn bộ thao tác được lưu vết bất biến vào `case_audit_logs`.
    - *Thất bại:* Hồ sơ giữ nguyên trạng thái `OPEN` hoặc `IN_PROGRESS`.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst chọn một hồ sơ từ màn hình `SUC-17 (Manage cases)` để bắt đầu điều tra.

### Luồng sự kiện chính (Basic Flow)

1. Fraud Analyst mở một hồ sơ điều tra từ hàng đợi; hệ thống tải dữ liệu chi tiết và hiển thị giao diện **Case Investigation Workbench (Bố cục 3 cột phối hợp)**:
    - **Cột Trái — Hồ sơ Chủ thể & Chuẩn hành vi cơ sở (Subject Profile & Historical Baseline):**
        - Thông tin định danh chủ thể (`subject_user_id`), trạng thái hiện tại (`ACTIVE` / `BLOCKED`) và danh sách các giao dịch bị gắn cờ nằm trong Case.
        - **Chỉ số Baseline lịch sử của khách hàng (30–90 ngày trước):** Số tiền giao dịch trung bình (`avg_amount_30d`), số tiền lớn nhất từng chi tiêu (`max_amount_30d`), tần suất giao dịch trung bình/ngày, khung giờ hoạt động phổ biến nhất, danh mục ngành hàng (`merchant_category`) và thiết bị/IP quen thuộc.
    - **Cột Giữa — Bằng chứng Phát hiện & Phân tích Hành vi Trực quan (Evidence & Behavioral Visual Analytics):**
        - **Khối 1 — Bằng chứng Kích hoạt (Why Flagged / Trigger Evidence):**
            - Hiển thị điểm **AI Model Fraud Score** kèm biểu đồ thanh ngang **Top-K Feature Contributions (SHAP / Local Explainability)** chỉ rõ các đặc trưng đẩy điểm rủi ro của giao dịch này lên cao nhất (ví dụ: `feature.velocity_1h = 8` đóng góp `+0.34`, `feature.ratio_to_avg_amount_30d = 9.2` đóng góp `+0.29`).
            - Hiển thị danh sách **Triggered Rules** trích xuất từ `rule_execution_logs`: nêu rõ mã quy tắc (`rule_code`), mức hành động (`REJECT`/`REVIEW`), trọng số (`risk_weight`), và **Snapshot giá trị thực tế (`condition_snapshot`)** tại thời điểm vi phạm (ví dụ: `mapped.amount = 25,000,000 > 10,000,000 AND feature.velocity_1h = 8 > 5`).
        - **Khối 2 — Đối chiếu Chuỗi thời gian & Độ lệch Hành vi (Behavioral Timeline & Deviation View):**
            - **Biểu đồ Trục thời gian Giao dịch (Interactive Transaction Timeline):** Biểu diễn toàn bộ chuỗi giao dịch gần đây của `user_id` theo thời gian (trục hoành: `timestamp`, trục tung: `amount`, màu sắc: giao dịch bình thường màu xám, giao dịch nghi vấn trong Case màu đỏ/cam). Giúp điều tra viên phát hiện trực quan mẫu hình *thử thẻ bằng nhiều giao dịch nhỏ liên tiếp trước khi rút khoản tiền lớn (Card Testing / Micro-fraud -> Cash-out)* hoặc *tấn công tốc độ cao (Velocity Attack)*.
            - **Bảng Đối chiếu Độ lệch (Current vs. Baseline Comparison Table):** Đặt song song giá trị của giao dịch nghi vấn bên cạnh giá trị Baseline lịch sử của chủ thẻ và tô đỏ các thuộc tính vượt ngưỡng bất thường (ví dụ: lệch múi giờ/khung giờ 02:30 sáng, đổi `device_id` mới lần đầu xuất hiện, khoảng cách địa lý dịch chuyển bất khả thi).
    - **Cột Phải — Bảng Phán quyết, Hành động Ngăn chặn & Nhật ký (Resolution & Mitigation Panel):**
        - Khung nhập **Ghi chú điều tra & Xác minh (`Investigation Notes`)**, nút phán quyết và các tùy chọn ngăn chặn.
2. Fraud Analyst kiểm tra bằng chứng ở Cột Giữa và đối chiếu với thói quen lịch sử của chủ thẻ ở Cột Trái. (Nếu nghi ngờ có liên kết đồng phạm với tài khoản khác, chuyên viên có thể chuyển sang tab **Network Graph** — kích hoạt `SUC-19`).
3. (Tùy chọn theo nghiệp vụ `BUC-06`) Nếu cần xác minh trực tiếp với chủ thẻ, Fraud Analyst liên hệ với khách hàng và ghi nhận kết quả phản hồi (khách xác nhận có thực hiện hay không, thẻ vật lý còn giữ không) vào ô **Investigation Notes**, đồng thời chuyển trạng thái tạm thời sang `PENDING_CUSTOMER` nếu đang chờ khách trả lời.
4. Sau khi có đủ căn cứ, Fraud Analyst đưa ra **Phán quyết điều tra (Case Resolution)** tại Cột Phải:
    - **Trường hợp A — Xác nhận là Gian lận (`Mark as Fraud / Confirmed Fraud`):**
        - Chọn nút **Confirm Fraud**.
        - Chọn **Mã phân loại kịch bản gian lận (`fraud_typology_code`)**: *Card Testing / Micro-fraud*, *Velocity Attack*, *Account Takeover (ATO)*, *Device-sharing Fraud Ring*, *Collusive Merchant*, hoặc *Other*.
        - Chọn **Hành động ngăn chặn khẩn cấp (`Mitigation Actions` - hiện thực hóa `BUC-07`)**:
            - `[x]` **Khóa / Đóng băng tài khoản hoặc thẻ (`Block User / Card`)**: Đưa `subject_user_id` / `card_id` vào trạng thái `BLOCKED` để tự động từ chối mọi giao dịch phát sinh tiếp theo.
            - `[ ]` **Chặn thiết bị / địa chỉ IP liên đới (`Blacklist Device ID / IP Address`)**.
    - **Trường hợp B — Xác nhận là Giao dịch Hợp lệ / Báo động giả (`Mark as Legitimate / False Positive`):**
        - Chọn nút **Mark as Legitimate (False Positive)**.
        - Chọn **Mã lý do báo động giả (`false_positive_reason`)**: *Unusual Legitimate Travel / Holiday Spending*, *Customer Confirmed via Call/OTP*, *Overly Strict Rule Threshold*, *Model False Alarm*.
        - (Tùy chọn) Tích chọn **Đưa chủ thể vào danh sách miễn trừ tạm thời (`Temporary Whitelist`)** hoặc **Đánh dấu quy tắc gây nhiễu (`Flag Noisy Rule` — liên kết `SUC-20`)**.
5. Fraud Analyst nhập tóm tắt kết luận cuối cùng (`resolution_summary`) và nhấn **Submit Decision**.
6. Hệ thống thực thi giao dịch cơ sở dữ liệu (Database Transaction):
    - Cập nhật bảng `fraud_cases`: `status = 'RESOLVED_FRAUD'` (hoặc `'RESOLVED_LEGITIMATE'`), `resolved_by = current_user`, `resolved_at = NOW()`, `resolution_reason`, `resolution_summary`.
    - Cập nhật nhãn xác thực thực tế (`verified_label = 1` nếu Fraud, `verified_label = 0` nếu Legitimate) cho các bản ghi giao dịch trong `case_transactions` để phục vụ trích xuất tập dữ liệu huấn luyện lại (`Retraining Ground Truth`).
    - Nếu có tích chọn hành động khóa (`Block Account/Card` hoặc `Blacklist Device/IP`), hệ thống thêm bản ghi tương ứng vào bảng `entity_watchlists` với `list_type = 'BLACKLIST'` và `status = 'ACTIVE'`.
    - Ghi bản ghi kiểm toán chi tiết vào `case_audit_logs`.
7. Hệ thống thông báo hoàn tất xử lý hồ sơ và tự động chuyển sang hồ sơ ưu tiên tiếp theo trong hàng đợi (nếu bật chế độ *Auto-advance Queue*).

### Luồng rẽ nhánh (Alternative Flows)

- **4a. Tách giao dịch hợp lệ ra khỏi hồ sơ đa giao dịch (Partial Case Resolution):**
    - Khi một Case gom nhiều giao dịch của cùng một `user_id` (ví dụ 5 giao dịch), nếu Fraud Analyst phát hiện chỉ có 3 giao dịch cuối là gian lận còn 2 giao dịch đầu là hợp lệ của chính chủ thẻ, chuyên viên có thể gắn nhãn riêng từng giao dịch (`verified_label = 0` hoặc `1`) trước khi chốt trạng thái tổng thể của Case là `RESOLVED_FRAUD`.
- **4b. Chuyển cấp điều tra chuyên sâu (Escalate Case to Senior Analyst):**
    - Nếu hồ sơ có dấu hiệu phức tạp hoặc giá trị quá lớn vượt thẩm quyền, Fraud Analyst chọn **Escalate Case**, nâng `priority = 'CRITICAL'`, đính kèm ghi chú phân tích ban đầu và gán cho Senior Analyst / Risk Manager.

### Luồng ngoại lệ (Exception Flows)

- **1a. Chủ thể mới chưa có lịch sử giao dịch (Cold-start User):**
    - Tại bước 1, nếu `subject_user_id` là khách hàng mới phát sinh giao dịch lần đầu tiên (không có dữ liệu lịch sử 30 ngày trong `DatasetArtifact`), hệ thống hiển thị nhãn cảnh báo **`New / Cold-Start Account`** tại Cột Trái và tự động chuyển bảng đối chiếu sang so sánh với **Mức trung bình của toàn bộ tập khách hàng cùng phân khúc / cùng nhóm ngành hàng (`Population / Peer Group Baseline`)**.
- **5a. Chưa nhập lý do phán quyết bắt buộc:**
    - Tại bước 5, nếu Fraud Analyst nhấn “Submit Decision” nhưng chưa chọn `resolution_reason` hoặc để trống `resolution_summary`, hệ thống chặn lưu và hiển thị thông báo: *“Vui lòng chọn mã lý do kết luận và nhập tóm tắt bằng chứng điều tra để đảm bảo tuân thủ kiểm toán.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-03 (Bắt buộc giải trình phán quyết - Mandatory Audit Justification):** Mọi phán quyết đóng hồ sơ (`RESOLVED_FRAUD` hoặc `RESOLVED_LEGITIMATE`) cũng như mọi lệnh khóa tài khoản/thẻ (`Block Account/Card`) bắt buộc phải đi kèm `resolution_reason` và `resolution_summary` tối thiểu 10 ký tự để phục vụ kiểm toán nội bộ và trích xuất báo cáo SAR (`BUC-05`).
- **BR-IV-04 (Vòng lặp phản hồi nhãn chuẩn - Ground Truth Feedback Integrity):** Nhãn do chuyên viên xác nhận thủ công (`verified_label`) có độ ưu tiên cao nhất (Ground Truth) và được lưu tách biệt với nhãn dự đoán ban đầu của mô hình (`predicted_label`), dùng làm nguồn nhãn chuẩn khi xuất dữ liệu huấn luyện lại mô hình (`SUC-08`) hoặc đánh giá độ chính xác thực tế của tập luật (`SUC-12`).

---

## SUC-19: Investigate network (Điều tra đồ thị mạng lưới liên kết)

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

## SUC-20: Manage rules & watchlists from investigation (Tinh chỉnh quy tắc & Danh sách chặn từ kết quả điều tra)

### Thông tin chung

- **Mã Use Case:** SUC-20
- **Tên Use Case:** Manage rules & watchlists from investigation (Tinh chỉnh quy tắc & Danh sách chặn từ kết quả điều tra)
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Data Scientist
- **Tác nhân phụ (Secondary Actor):** Rule Engine Service (`IRuleRepository`), Watchlist Service (`IWatchlistRepository`)
- **Mô tả:** Cho phép Fraud Analyst chuyển hóa trực tiếp các phát hiện từ quá trình điều tra thực tế thành chính sách phòng vệ (`BUC-04`): (1) trích xuất nhanh mẫu hành vi của một Case gian lận mới thành quy tắc phát hiện nháp (`DRAFT` / `SHADOW`), (2) gắn cờ phản hồi các quy tắc đang gây tỷ lệ báo động giả cao (`Noisy Rules`) để điều chỉnh ngưỡng hoặc hạ trọng số, và (3) quản lý danh sách chặn/miễn trừ thực thể (`Blacklist` / `Whitelist`).
- **Tiền điều kiện:** Người dùng đã đăng nhập với vai trò `Fraud Analyst` hoặc `Data Scientist`.
- **Hậu điều kiện:**
    - *Thành công:* Quy tắc mới được tạo từ Case và lưu vào bảng `rules` ở trạng thái `DRAFT` hoặc `SHADOW`; hoặc thông số quy tắc hiện hành / danh sách `entity_watchlists` được cập nhật và ghi vết vào lịch sử kiểm toán.
    - *Thất bại:* Không thay đổi cấu hình tập luật hoặc danh sách chặn hiện tại.
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst nhấn nút **“Create Rule from Case”** / **“Flag Noisy Rule”** trong màn hình điều tra (`SUC-18`), hoặc truy cập vào tab **Investigation -> Policy & Watchlists**.

### Luồng sự kiện chính (Basic Flow)

1. **Kịch bản 1 — Trích xuất quy tắc mới từ mẫu gian lận vừa điều tra (Create Quick Rule from Case):**
    - Sau khi xác nhận một hồ sơ là `CONFIRMED_FRAUD` (đặc biệt là các ca do mô hình AI bắt được nhưng chưa có quy tắc nào trong Rule Engine bao phủ), Fraud Analyst nhấn nút **Create Rule from Case**.
    - Hệ thống mở hộp thoại **Quick Rule Builder**, tự động trích xuất các thuộc tính bất thường nhất từ `condition_snapshot` của giao dịch trong Case để dựng sẵn cây điều kiện gợi ý (`CompositeCondition` `AND`), ví dụ:
        - `mapped.merchant_category == 'CRYPTO_EXCHANGE'`
        - `AND feature.velocity_1h >= 4`
        - `AND mapped.amount >= 5000000`
    - Fraud Analyst xem xét, chỉnh sửa lại giá trị ngưỡng (`threshold`), đặt `rule_code`, `name`, chọn `action` (`REVIEW` hoặc `REJECT`) và `risk_weight`.
    - Fraud Analyst có thể nhấn **Quick Dry-run** (liên kết `SUC-12`) để xem ngay quy tắc này sẽ bắt trúng bao nhiêu giao dịch trên tập dữ liệu hiện tại, sau đó nhấn **Save as Shadow / Draft Rule** để lưu vào bảng `rules`.
2. **Kịch bản 2 — Đánh giá và tinh chỉnh quy tắc gây báo động giả (Tune Noisy Rules from Investigation Feedback):**
    - Fraud Analyst hoặc Data Scientist mở bảng **Rule Investigation Feedback Table**, nơi hệ thống thống kê hiệu quả thực tế của từng `rule_code` dựa trên kết quả phán quyết từ `SUC-18`:
        - Tổng số Case mà quy tắc đó đã kích hoạt (`Cases Triggered`).
        - Số Case được xác nhận là gian lận thật (`Confirmed Fraud Count - TP`).
        - Số Case bị kết luận là báo động giả (`False Positive Count - FP`) và **Tỷ lệ Báo động giả thực tế (`Verified FPR %`)**.
    - Đối với các quy tắc có `Verified FPR %` vượt ngưỡng cho phép (ví dụ `> 80%`), người dùng có thể nhấn **Adjust Threshold / Weight** để nới ngưỡng `threshold`, giảm `risk_weight`, hoặc hạ trạng thái quy tắc từ `ACTIVE` xuống `SHADOW` / `INACTIVE`.
3. **Kịch bản 3 — Quản lý Danh sách Chặn & Miễn trừ Thực thể (Manage Entity Watchlists - Blacklist / Whitelist):**
    - Fraud Analyst mở tab **Entity Watchlists** để xem, tìm kiếm, thêm mới hoặc gỡ bỏ các thực thể (`user_id`, `card_id`, `device_id`, `ip_address`, `merchant_id`) trong hai danh sách:
        - **`BLACKLIST` (Danh sách chặn):** Các thực thể đã xác nhận gian lận hoặc bị khóa khẩn cấp (`BUC-07`) — tự động kích hoạt hành động `REJECT` ở các đợt kiểm tra tiếp theo.
        - **`WHITELIST` (Danh sách miễn trừ):** Các tài khoản/đối tác uy tín đã được xác minh — giảm thiểu cảnh báo lặp lại không cần thiết (có thời hạn hiệu lực `expires_at`).

### Luồng ngoại lệ (Exception Flows)

- **1a. Người dùng không có quyền triển khai trực tiếp (`ACTIVE`) quy tắc:**
    - Nếu `Fraud Analyst` chỉ có quyền đề xuất quy tắc (`rule: propose`) mà không có quyền triển khai trực tiếp lên `ACTIVE` (`rule: deploy` thuộc về `Data Scientist` / `Risk Manager`), hệ thống tự động lưu quy tắc mới ở trạng thái `DRAFT` hoặc `SHADOW` và gửi thông báo phê duyệt sang phân hệ Detection.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-IV-06:** Mọi quy tắc được tạo mới hoặc chỉnh sửa ngưỡng từ phân hệ Investigation bắt buộc phải tuân thủ cấu trúc cây điều kiện `Boolean AST` (`CompositeCondition` / `SingleCondition`) và kiểm tra tính duy nhất của `rule_code` theo `BR-DT-05` của phân hệ Detection.
- **BR-IV-07:** Một định danh thực thể (`entity_type`, `entity_value`) trong cùng một Project không được phép vừa nằm trong `BLACKLIST` vừa nằm trong `WHITELIST` ở trạng thái `ACTIVE` tại cùng một thời điểm.

---

## SUC-21: Run AI Case Copilot (Trợ lý AI tự động tổng hợp & tóm tắt điều tra) *(Chức năng nâng cao)*

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

## 4.1. Đề xuất Lược đồ Cơ sở Dữ liệu (PostgreSQL Schema)

Để hỗ trợ đầy đủ 5 Use Case trên và kết nối liền mạch với bảng `projects`, `rules`, `rule_execution_logs` hiện có, phân hệ Investigation bổ sung 4 bảng cốt lõi sau:

```sql
-- 1. Bảng Hồ sơ điều tra gian lận (Fraud Cases)
CREATE TABLE fraud_cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    case_code TEXT NOT NULL,                          -- Mã hiển thị: 'CASE-2026-0001'
    detection_job_id UUID,                            -- Liên kết đợt chạy SUC-15 đã sinh ra Case
    subject_user_id TEXT NOT NULL,                    -- Định danh chủ thể/khách hàng/thẻ chính
    
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'IN_PROGRESS', 'PENDING_CUSTOMER', 'RESOLVED_FRAUD', 'RESOLVED_LEGITIMATE', 'MERGED')),
    priority TEXT NOT NULL DEFAULT 'MEDIUM'
        CHECK (priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    priority_score NUMERIC(5, 2) DEFAULT 0.0,
    
    flagged_tx_count INTEGER NOT NULL DEFAULT 1,
    total_flagged_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.0,
    max_model_score NUMERIC(5, 4),                    -- Điểm xác suất AI cao nhất trong Case (0.0 -> 1.0)
    max_rule_score NUMERIC(5, 2),                     -- Điểm rủi ro Rule cao nhất trong Case (0.0 -> 100.0)
    triggered_rule_codes JSONB DEFAULT '[]'::jsonb,   -- Danh sách mã rule vi phạm nổi bật
    
    assigned_to TEXT,                                 -- Username chuyên viên đang thụ lý
    resolution_verdict TEXT
        CHECK (resolution_verdict IN ('CONFIRMED_FRAUD', 'FALSE_POSITIVE')),
    resolution_reason TEXT,                           -- Mã lý do (VD: 'CARD_TESTING', 'ATO', 'NOISY_RULE')
    resolution_summary TEXT,                          -- Ghi chú kết luận cuối cùng phục vụ kiểm toán & SAR
    ai_investigation_brief JSONB,                     -- Bản nháp phân tích từ AI Copilot (SUC-21)
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    
    CONSTRAINT uq_project_case_code UNIQUE (project_id, case_code)
);

CREATE INDEX idx_cases_project_queue ON fraud_cases(project_id, status, priority_score DESC);
CREATE INDEX idx_cases_subject_user ON fraud_cases(project_id, subject_user_id);

-- 2. Bảng Liên kết Giao dịch trong Hồ sơ & Nhãn Xác thực (Case Transactions & Ground Truth Labels)
CREATE TABLE case_transactions (
    case_id UUID NOT NULL REFERENCES fraud_cases(case_id) ON DELETE CASCADE,
    transaction_id TEXT NOT NULL,                     -- Khớp với event_id trong DatasetArtifact
    model_score NUMERIC(5, 4),
    total_risk_score NUMERIC(5, 2),
    highest_severity_action TEXT,
    transaction_snapshot JSONB NOT NULL,              -- Snapshot mapped.*, feature.*, shap_top_features
    verified_label INTEGER CHECK (verified_label IN (0, 1)), -- Nhãn chuẩn sau điều tra (1: Fraud, 0: Legit)
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    PRIMARY KEY (case_id, transaction_id)
);

-- 3. Bảng Danh sách Chặn / Miễn trừ Thực thể (Entity Watchlists: Blacklist & Whitelist)
CREATE TABLE entity_watchlists (
    watchlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('USER_ID', 'CARD_ID', 'DEVICE_ID', 'IP_ADDRESS', 'MERCHANT_ID')),
    entity_value TEXT NOT NULL,
    list_type TEXT NOT NULL CHECK (list_type IN ('BLACKLIST', 'WHITELIST')),
    reason TEXT NOT NULL,
    source_case_id UUID REFERENCES fraud_cases(case_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'REMOVED')),
    created_by TEXT DEFAULT CURRENT_USER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_active_entity_watchlist
    ON entity_watchlists(project_id, entity_type, entity_value)
    WHERE status = 'ACTIVE';

-- 4. Bảng Nhật ký Kiểm toán & Ghi chú Điều tra (Case Audit Logs & Notes)
CREATE TABLE case_audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES fraud_cases(case_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,                        -- 'CREATED', 'ASSIGNED', 'NOTE_ADDED', 'RESOLVED', 'ENTITY_BLOCKED', 'REOPENED'
    actor TEXT NOT NULL DEFAULT CURRENT_USER,
    note_or_detail TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 4.2. Đặc tả Bố cục Giao diện (UI/UX Layout)

Để chuyên viên phân tích không phải chuyển đổi rời rạc giữa nhiều màn hình, giao diện phân hệ **Investigation** được thiết kế gồm **3 chế độ hiển thị chính**:

| **Màn hình / Khu vực** | **Thành phần Giao diện (UI Components)** | **Mục đích trải nghiệm (UX Rationale)** |
| --- | --- | --- |
| **1. Hàng đợi Hồ sơ (Case Queue View — `SUC-17`)** |   • **4 Thẻ KPI trên cùng:** *Open Cases*, *Critical Cases*, *In Progress*, *Precision / False Positive Rate*.
  • **Thanh Lọc & Tìm kiếm:** Lọc theo `Priority`, `Status`, `Rule Code`, `Assigned Analyst`, khoảng điểm `Model Score`.
  • **Bảng Danh sách Case:** Hiển thị thanh nhiệt độ rủi ro (`Model Score` & `Rule Score`), nhãn quy tắc vi phạm, tổng tiền rủi ro và nút `Investigate`. | Giúp điều tra viên tập trung xử lý các ca có rủi ro tài chính và xác suất gian lận cao nhất trước (`Triage & Prioritization`), tránh quá tải khi số lượng cảnh báo lớn. |
| **2. Không gian Điều tra 3 Cột (Case Workbench — `SUC-18` & `SUC-21`)** |   • **Cột Trái (25% — Subject & Baseline):** Thông tin `user_id`, trạng thái thẻ, các chỉ số Baseline 30 ngày (số tiền TB, tần suất TB, giờ hoạt động quen thuộc) và danh sách các giao dịch trong Case.
  • **Cột Giữa (50% — Evidence & Visual Analytics):**
  1. *Trigger Evidence:* Điểm AI + Biểu đồ thanh ngang Top SHAP Features + Danh sách Rule vi phạm kèm `condition_snapshot`.
  2. *Behavioral Timeline:* Biểu đồ Scatter/Bar chuỗi giao dịch theo thời gian và bảng so sánh *Giao dịch hiện tại vs. Baseline* (tô đỏ các trường lệch chuẩn).
  3. *Tab Network Graph:* Chuyển nhanh sang đồ thị liên kết (`SUC-19`).
  • **Cột Phải (25% — Decision & Mitigation):** Tóm tắt từ `AI Case Copilot`, nút **Confirm Fraud** / **Mark as Legitimate**, chọn mã lý do, checkbox **Block Account/Card**, nút **Create Quick Rule**, và khung ghi chú/lịch sử kiểm toán. | Hội tụ toàn bộ bằng chứng (*Tại sao bị bắt?*  • *Có lệch thói quen lịch sử không?*  • *Ra quyết định*) trên một màn hình duy nhất theo đúng mô hình *Multiple Coordinated Views (EVA)* và *Ravelin Workbench*. |
| **3. Khung Đồ thị Mạng lưới (Network Graph View — `SUC-19`)** |   • **Interactive Force-Directed Canvas:** Các nút phân biệt bằng icon (`User`, `Card`, `Device`, `IP`, `Merchant`) và màu sắc mức độ rủi ro (Đỏ / Cam / Xám).
  • **Thanh công cụ Đồ thị:** Chọn độ sâu (`1-hop`, `2-hop`), lọc loại thực thể, thanh trượt thời gian, và nút hành động hàng loạt (**Add Ring to Case**, **Block Selected Entities**). | Giúp phát hiện trực quan các cụm dùng chung thiết bị/IP (*Device-sharing Ring*) hoặc điểm bán hàng giả mạo (*Merchant Ring*) mà bảng dữ liệu phẳng không thể nhìn thấy. |