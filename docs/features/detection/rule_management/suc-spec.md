# Đặc tả use case hệ thống phân hệ Detection
# 0. Tài liệu liên quan

[Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21) 

# 1. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng rule management cho phân hệ Detection trong FDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-11** | **Create rule** | Data Scientist | Soạn thảo các điều kiện logic phát hiện gian lận (kết hợp các đặc trưng và ngưỡng giá trị). | High |
| **SUC-12** | **Test rule** | Data Scientist | Chạy thử nghiệm (dry-run/backtest) tập luật trên tập dữ liệu lịch sử để đánh giá độ chính xác và tỷ lệ báo động giả. | High |
| **SUC-13** | **Get recommended rules** | Data Scientist | Nhận các quy tắc được hệ thống/AI gợi ý tự động dựa trên cây quyết định hoặc mẫu bất thường mới. | Low |
| **SUC-14** | **Activate rule** | Data Scientist | Đưa rule vào trạng thái hoạt động (Active) để có thể sử dụng nó cho SUC-15 | High |
| **SUC-18** | **View rules** | Data Scientist | Xem danh sách các rule cùng các thong tin liên quan | High |

# 2. Chi tiết

## SUC-11: Create rule (Tạo quy tắc phát hiện gian lận)

### Thông tin chung

- **Mã Use Case:** SUC-11
- **Tên Use Case:** Create rule (Tạo quy tắc phát hiện gian lận)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist soạn thảo các quy tắc phát hiện gian lận dựa trên cấu trúc cây điều kiện logic phân cấp (Boolean AST), kết hợp linh hoạt giữa dữ liệu giao dịch gốc (`mapped.*`), đặc trưng làm giàu (`feature.*`) và điểm số rủi ro từ mô hình AI (`model.*`).
- **Tiền điều kiện:** Người dùng đã đăng nhập với vai trò `Data Scientist` (quyền `rule: create`) và đang làm việc trong một Dự án (Project) cụ thể.
- **Hậu điều kiện:**
    - *Thành công:* Quy tắc mới được lưu vào bảng `rules` với cấu trúc `condition_tree` định dạng `JSONB`, trạng thái ban đầu là `DRAFT` và `version = 1`.
    - *Thất bại:* Quy tắc không được lưu vào cơ sở dữ liệu.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Create Rule” trong mục Rule Engine của phân hệ Detection.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist truy cập vào trình quản lý **Rule Engine** và nhấn nút **Create Rule**.
2. Hệ thống hiển thị giao diện trình dựng quy tắc trực quan (Visual Rule Tree Builder) kèm danh mục các trường dữ liệu theo 3 không gian tên (Context Namespaces):
    - `mapped.<field>`: Các trường giao dịch chuẩn hóa từ `SUC-02` (`mapped.amount`, `mapped.user_id`, `mapped.timestamp`, `mapped.merchant_category`, `mapped.ip_address`,…).
    - `feature.<field>`: Các đặc trưng nâng cao từ `SUC-05` (`feature.velocity_1h`, `feature.tx_frequency_24h`, `feature.ratio_to_avg_amount_30d`,…).
    - `model.<field>`: Điểm rủi ro đầu ra của mô hình học máy (`model.fraud_score`, `model.score`).
3. Data Scientist nhập thông tin chung của quy tắc:
    - Mã quy tắc duy nhất (`rule_code`, ví dụ: `R_HIGH_VELOCITY_NIGHT`).
    - Tên quy tắc (`name`) và Mô tả ý nghĩa nghiệp vụ (`description`).
    - Độ ưu tiên thực thi (`priority`, mặc định `100` — giá trị càng nhỏ độ ưu tiên càng cao).
    - Hành động đề xuất khi quy tắc thỏa mãn (`action` thuộc `RuleAction`: `REJECT`, `REVIEW`, `ALERT`, `SCORE_BOOST`, `PASS`).
    - Trọng số rủi ro cộng thêm (`risk_weight`, giá trị từ `0.0` đến `100.0`).
4. Data Scientist thiết lập cây điều kiện logic (`condition_tree` theo mô hình Composite Pattern):
    - Thêm các nhóm điều kiện (`CompositeCondition`) kết nối bằng toán tử logic `AND`, `OR`, `NOT` (hỗ trợ lồng ghép nhiều cấp).
    - Thêm các mệnh đề so sánh đơn nguyên tử (`SingleCondition`) gồm: Trường dữ liệu (`field`), Toán tử so sánh (`ComparisonOperator`: `==`, `!=`, `>`, `>=`, `<`, `<=`, `IN`, `NOT_IN`, `CONTAINS`, `REGEX`, `EXISTS`) và Giá trị ngưỡng (`threshold`).
5. Data Scientist nhấn nút **Save as Draft**.
6. Hệ thống kiểm tra tính hợp lệ của quy tắc:
    - Kiểm tra tính duy nhất của `rule_code` trong phạm vi `project_id`.
    - Xác thực cấu trúc cây điều kiện AST thông qua Pydantic schema (không có nút rỗng, kiểu dữ liệu của `threshold` tương thích với `operator`, biểu thức `REGEX` hợp lệ).
7. Hệ thống lưu quy tắc vào bảng `rules` với trạng thái `status = 'DRAFT'`, `version = 1` và thông báo tạo quy tắc thành công.

### Luồng rẽ nhánh (Alternative Flows)

- **2a. Tạo quy tắc từ mẫu có sẵn (Rule Template) hoặc nhân bản quy tắc cũ: (***review: chức năng advanced, sẽ cài đặt sau)*
    - Tại bước 2, Data Scientist có thể chọn một mẫu quy tắc chuẩn (ví dụ: *High Amount International Night Transaction*) để hệ thống dựng sẵn cây điều kiện, sau đó chỉ cần điều chỉnh lại ngưỡng `threshold`.

### Luồng ngoại lệ (Exception Flows)

- **6a. Trùng mã quy tắc (`rule_code`):**
    - Tại bước 6, nếu `rule_code` đã tồn tại trong dự án hiện tại (vi phạm ràng buộc `uq_project_rule_code`), hệ thống hiển thị thông báo lỗi: *“Mã quy tắc (rule_code) đã tồn tại trong dự án này. Vui lòng nhập mã định danh khác.”*
- **6b. Cây điều kiện rỗng hoặc biểu thức không hợp lệ:**
    - Tại bước 6, nếu cây điều kiện chưa có mệnh đề `SingleCondition` nào hoặc giá trị ngưỡng không hợp lệ với toán tử (ví dụ dùng toán tử `>` cho chuỗi văn bản không phải số), hệ thống đánh dấu vị trí nút lỗi trên giao diện và yêu cầu chỉnh sửa.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-05:** Mã quy tắc (`rule_code`) phải là duy nhất trong phạm vi một Dự án (`UNIQUE (project_id, rule_code)`).
- **BR-DT-06:** Trọng số rủi ro (`risk_weight`) của mỗi quy tắc phải là số không âm ($\ge 0.0$), và tổng điểm rủi ro cộng dồn từ các quy tắc cho một giao dịch được giới hạn tối đa ở mức `100.0`.

## SUC-12: Test rule (Kiểm thử quy tắc / Dry-run & Backtest)

### Thông tin chung

- **Mã Use Case:** SUC-12
- **Tên Use Case:** Test rule (Kiểm thử quy tắc / Dry-run & Backtest)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist chạy thử nghiệm (`dry-run` / `backtest`) một quy tắc hoặc một bộ quy tắc trên tập dữ liệu giao dịch lịch sử nhằm đánh giá tỷ lệ kích hoạt (Trigger Rate), độ chính xác (Precision) và tỷ lệ cảnh báo giả (False Positive Rate) trước khi triển khai chính thức.
- **Tiền điều kiện:**
    1. Quy tắc cần kiểm thử đã được định nghĩa hợp lệ (ở trạng thái `DRAFT`, `SHADOW` hoặc `ACTIVE`).
    2. Trong dự án đã có ít nhất một `DatasetArtifact` ở trạng thái `MAPPED` hoặc `FEATURE_ENGINEERED`.
- **Hậu điều kiện:** Hệ thống hiển thị báo cáo kết quả mô phỏng kiểm thử (số lượng giao dịch vi phạm, tỷ lệ báo động giả, thời gian thực thi trung bình) mà không làm thay đổi trạng thái dữ liệu vận hành.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Test Rule / Dry-run” trên màn hình soạn thảo hoặc chi tiết quy tắc.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn một quy tắc (hoặc một bộ quy tắc `rule_sets`) và nhấn nút **Test Rule (Dry-run)**.
2. Hệ thống hiển thị hộp thoại cấu hình kiểm thử:
    - Chọn `DatasetArtifact` lịch sử dùng để chạy backtest (ưu tiên tập `FEATURE_ENGINEERED` có sẵn các đặc trưng làm giàu và nhãn thực tế `label`).
    - (Tùy chọn) Chọn một `ModelVersion` nếu trong điều kiện của quy tắc có tham chiếu tới không gian tên `model.fraud_score`.
3. Data Scientist nhấn nút **Run Backtest**.
4. Hệ thống nạp dữ liệu từ `DatasetArtifact` và khởi tạo `RuleExecutionContext` cho từng giao dịch.
5. Bộ đánh giá đệ quy `RuleConditionEvaluator` duyệt cây điều kiện `condition_tree` trên toàn bộ tập dữ liệu kiểm thử và đo lường thời gian thực thi (`execution_time_ms`).
6. Hệ thống đối chiếu danh sách các giao dịch kích hoạt quy tắc với cột nhãn thực tế (`label` = 0 hoặc 1) và tổng hợp báo cáo đánh giá:
    - **Tổng số giao dịch kiểm thử** và **Số lượng giao dịch khớp điều kiện (`Triggered Count` / `Hit Rate %`)**.
    - **Hiệu quả phát hiện (khi tập dữ liệu có nhãn `label`):**
        - Số giao dịch gian lận bắt đúng (`True Positives - TP`).
        - Số giao dịch hợp lệ bị bắt nhầm (`False Positives - FP`) và **Tỷ lệ báo động giả (`False Positive Rate - FPR`)**.
        - Độ xác chuẩn của quy tắc (`Rule Precision = TP / (TP + FP)`).
    - **Hiệu năng thực thi:** Thời gian đánh giá trung bình trên mỗi giao dịch (`ms/tx`) và tổng thời gian chạy.
    - **Bảng dữ liệu mẫu (Sample Triggered Transactions):** Hiển thị 20 giao dịch đầu tiên bị quy tắc bắt trúng kèm giá trị thực tế của các trường trong `condition_snapshot`.
7. Data Scientist xem xét kết quả; nếu tỷ lệ báo động giả quá cao, người dùng có thể tinh chỉnh lại ngưỡng `threshold` của quy tắc và chạy kiểm thử lại.

### Luồng ngoại lệ (Exception Flows)

- **4a. Thiếu trường dữ liệu trong ngữ cảnh kiểm thử:**
    - Nếu quy tắc tham chiếu đến một đặc trưng `feature.<x>` hoặc `model.fraud_score` nhưng tập dữ liệu được chọn chưa có trường đó (và người dùng không chọn mô hình đi kèm), hệ thống hiển thị cảnh báo: *“Tập dữ liệu kiểm thử thiếu trường dữ liệu mà quy tắc yêu cầu. Các mệnh đề thiếu dữ liệu sẽ mặc định trả về False (trừ toán tử != và NOT_IN).”*

## SUC-13: Get recommended rules (Nhận đề xuất quy tắc tự động) *(review: chức năng advanced, sẽ bổ sung sau)*

### Thông tin chung

- **Mã Use Case:** SUC-13
- **Tên Use Case:** Get recommended rules (Nhận đề xuất quy tắc tự động)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist sử dụng công cụ học máy giải thích được (White-box Decision Tree / Rule Extraction) để tự động phân tích các mẫu gian lận trong dữ liệu lịch sử hoặc kết quả điều tra mới, từ đó trích xuất và đề xuất các quy tắc phát hiện gian lận tiềm năng dưới dạng cây điều kiện chuẩn của Rule Engine.
- **Tiền điều kiện:** Trong dự án đã có `DatasetArtifact` ở trạng thái `FEATURE_ENGINEERED` có nhãn `label` (hoặc tập dữ liệu đã được cập nhật nhãn xác nhận từ phân hệ Investigation).
- **Hậu điều kiện:**
    - *Thành công:* Danh sách các quy tắc gợi ý được sinh ra kèm các chỉ số ước lượng (`Precision`, `Recall`, `Support`); các quy tắc được Data Scientist chấp nhận sẽ được lưu vào bảng `rules` ở trạng thái `DRAFT` hoặc `SHADOW`.
    - *Thất bại:* Không có quy tắc nào được lưu thêm vào hệ thống.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Get Recommended Rules” tại màn hình quản lý Rule Engine.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist nhấn nút **Get Recommended Rules** trong phân hệ **Detection**.
2. Hệ thống hiển thị bảng cấu hình trích xuất quy tắc tự động:
    - Chọn nguồn dữ liệu phân tích (`DatasetArtifact` ở trạng thái `FEATURE_ENGINEERED`).
    - Thiết lập độ sâu tối đa của cây điều kiện gợi ý (`max_depth`, mặc định từ `2` đến `4` để đảm bảo quy tắc ngắn gọn, dễ giải thích).
    - Thiết lập ngưỡng độ chính xác tối thiểu (`min_precision`, ví dụ `0.70`) và số lượng mẫu gian lận tối thiểu mà quy tắc phải bao phủ (`min_support`).
3. Data Scientist nhấn nút **Generate Recommendations**.
4. Hệ thống huấn luyện mô hình cây quyết định giải thích được (`Surrogate Decision Tree`) trên tập đặc trưng `mapped.*` và `feature.*` để tìm các điểm chia ngưỡng (split thresholds) phân tách tốt nhất giữa nhóm gian lận (`label = 1`) và hợp lệ (`label = 0`).
5. Hệ thống duyệt qua các nhánh lá (leaf paths) đạt ngưỡng `min_precision` và `min_support`, tự động biên dịch từng nhánh thành cấu trúc `CompositeCondition` (`AND` của các `SingleCondition`) và gợi ý `risk_weight` cùng `action` tương ứng.
6. Hệ thống hiển thị danh sách các quy tắc đề xuất, mỗi quy tắc gồm:
    - Biểu thức điều kiện dạng tường minh (ví dụ: `feature.velocity_1h > 5 AND mapped.amount > 10,000,000`).
    - Độ chính xác ước tính (`Precision`), độ phủ trên tổng số ca gian lận (`Recall / Coverage`), và số lượng giao dịch khớp trong tập dữ liệu.
7. Data Scientist xem xét, tích chọn các quy tắc hữu ích, đặt `rule_code`, chỉnh sửa ngưỡng (nếu cần) và nhấn **Import Selected Rules** để lưu vào bảng `rules` (mặc định ở trạng thái `DRAFT` hoặc `SHADOW`).

### Luồng ngoại lệ (Exception Flows)

- **5a. Không tìm thấy quy tắc thỏa mãn ngưỡng cấu hình:**
    - Nếu không có nhánh điều kiện nào đạt mức `min_precision` và `min_support` đã đặt, hệ thống thông báo: *“Không tìm thấy mẫu quy tắc nào đạt ngưỡng độ chính xác yêu cầu trên tập dữ liệu này. Vui lòng giảm ngưỡng min_precision hoặc bổ sung thêm đặc trưng tại bước Feature Engineering.”*

## SUC-14: Activate rule

### Thông tin chung

- **Mã Use Case:** SUC-14
- **Tên Use Case:** Deploy rule (Triển khai quy tắc)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist kích hoạt quy tắc từ trạng thái nháp (`DRAFT`) sang trạng thái hoạt động chính thức (`ACTIVE`), hoặc quản lý kích hoạt theo bộ quy tắc (`rule_sets`) trong động cơ đánh giá gian lận.
- **Tiền điều kiện:** Người dùng có quyền `rule:activate`(vai trò `Data Scientist`); quy tắc đã được tạo hợp lệ trong bảng `rules`.
- **Hậu điều kiện:**
    - *Thành công:* Trạng thái của quy tắc trong bảng `rules` được cập nhật thành `ACTIVE`, phiên bản `version` và thời gian `updated_at` được ghi nhận; quy tắc lập tức có hiệu lực trong các lần chạy `SUC-15` tiếp theo.
    - *Thất bại:* Trạng thái quy tắc giữ nguyên như cũ.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Deploy Rule” (hoặc chuyển trạng thái kích hoạt) tại danh sách Rule Engine hoặc sau khi kiểm thử quy tắc (`SUC-12`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn một hoặc nhiều quy tắc đang ở trạng thái `DRAFT` hoặc `SHADOW` trong danh mục **Rule Engine** và nhấn **Deploy Rule**.
2. Hệ thống hiển thị hộp thoại xác nhận chế độ triển khai:
    - **Chế độ `ACTIVE` (Triển khai chính thức):** Quy tắc trực tiếp tham gia tính tổng điểm rủi ro (`total_risk_score`) và quyết định hành động (`highest_severity_action`).
    - Kiểm tra lại thứ tự ưu tiên (`priority`) và nhóm quy tắc (`rule_sets`) liên kết.
3. Data Scientist chọn chế độ mong muốn và nhấn **Confirm Activate**.
4. Hệ thống kiểm tra tính hợp lệ của cây điều kiện `condition_tree` và cập nhật bản ghi trong bảng `rules` (`status = 'ACTIVE'` cập nhật `updated_at`). Nếu quy tắc được chỉnh sửa nội dung từ một phiên bản đã từng triển khai trước đó, hệ thống tự động tăng số hiệu `version` thêm 1.
5. Hệ thống thông báo triển khai quy tắc thành công.