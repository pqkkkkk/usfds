# Đặc tả use case hệ thống phân hệ Detection
# 0. Tài liệu liên quan

[Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21) 

# 1. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng inference cho phân hệ Detection trong FDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-15** | **Start detection job** | Data Scientist, Fraud Analyst | Khởi chạy tác vụ chấm điểm mẻ trên tập giao dịch cần rà soát bằng cách kết hợp Mô hình AI và Rule Engine. | High |
| **SUC-16** | **View detection result** | Fraud Analyst, Data Scientist | Xem danh sách kết quả phân loại, điểm số rủi ro, và chuyển tiếp các giao dịch đáng ngờ sang module Investigation để tạo Case. | High |
| **SUC-19** | **View detection jobs** | Fraud Analyst | Xem danh sách các detection job cùng các thông tin liên quan | High |

# 2. Chi tiết
## SUC-15: Start detection job (Khởi chạy tác vụ phát hiện gian lận theo mẻ)

### Thông tin chung

- **Mã Use Case:** SUC-15
- **Tên Use Case:** Start detection job (Khởi chạy tác vụ phát hiện gian lận theo mẻ)
- **Tác nhân chính (Primary Actor):** Data Scientist, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Compute Engine / Detection Worker, Hệ thống lưu trữ (`IFileStorage`)
- **Mô tả:** Cho phép Data Scientist hoặc Fraud Analyst khởi chạy một tác vụ rà soát và chấm điểm gian lận hàng loạt (Batch Detection Job) trên tập giao dịch cần kiểm tra bằng cách kết hợp đồng thời điểm xác suất từ Mô hình AI (`Model Inference`) và phán quyết từ Bộ quy tắc nghiệp vụ (`Rule EngineExecutionService`).
- **Tiền điều kiện:**
- **Hậu điều kiện:**
    - *Thành công:* Tác vụ `detection_job` hoàn tất; toàn bộ giao dịch trong tập dữ liệu được gán điểm rủi ro mô hình (`model_score`), điểm rủi ro quy tắc (`total_risk_score`), danh sách quy tắc vi phạm (`triggered_rules`, `shadow_triggered_rules`) và hành động phán quyết cuối cùng; nhật ký thực thi được lưu vào bảng `rule_execution_logs`.
    - *Thất bại:* Tác vụ được đánh dấu `failed` kèm thông báo lỗi chi tiết.
- **Sự kiện kích hoạt (Trigger):** Người dùng nhấn nút “Start Detection Job” tại phân hệ Detection.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng (`Data Scientist` hoặc `Fraud Analyst`) mở màn hình **Detection Jobs** và nhấn nút **Start Detection Job**.
2. Hệ thống hiển thị biểu mẫu cấu hình tác vụ phát hiện:
    - **Tên tác vụ (`job_name`)** và mô tả đợt rà soát.
    - **Chọn tập dữ liệu cần rà soát (`target_artifact_id`):** Chọn `DatasetArtifact` chứa các giao dịch cần chấm điểm hoặc upload dataset mới.
    - **Cấu hình Động cơ AI (`Model Deployment`):** Chọn phiên bản mô hình đang `active` trong bảng `deployments` (hoặc chọn chế độ *Rule-Only* nếu chỉ quét bằng tập luật).
    - **Cấu hình Động cơ Tập luật (`Rule Set`):** Mặc định nạp toàn bộ các quy tắc có trạng thái `ACTIVE` của dự án (sắp xếp theo `priority` tăng dần).
    - **Ngưỡng phân loại rủi ro (`score_threshold`):** Ngưỡng xác suất mô hình (ví dụ `0.80`) để gắn cờ nghi vấn từ phía AI.
3. Người dùng nhấn nút **Run Detection Job**.
4. Hệ thống khởi tạo bản ghi tác vụ phát hiện ở trạng thái `running` và điều phối thực thi qua các bước:
    - **Bước 4.1 — Chuẩn bị đặc trưng (nếu cần):** Nếu tập dữ liệu đầu vào đang ở trạng thái `MAPPED`, hệ thống tự động nạp bộ `fitted_feature_engineers.joblib` để trích xuất các đặc trưng làm giàu (`enriched_features`).
    - **Bước 4.2 — Suy luận Mô hình AI (Model Inference):** Nạp pipeline biến đổi và trọng số của `ModelVersion` đã chọn, thực hiện dự đoán hàng loạt để sinh `model_score` ($0.0 \rightarrow 1.0$) cho từng giao dịch.
    - **Bước 4.3 — Thực thi Rule Engine (`RuleEngineExecutionService`):** Với mỗi giao dịch, hệ thống đóng gói `RuleExecutionContext` (gồm `transaction_id`, `mapped_data`, `enriched_features`, và `model_score`), duyệt qua toàn bộ các quy tắc `ACTIVE` và `SHADOW` theo thứ tự ưu tiên:
        - Các quy tắc `ACTIVE` khớp điều kiện được đưa vào `triggered_rules` và cộng dồn `risk_weight` vào `total_risk_score` (tối đa `100.0`).
        - Các quy tắc `SHADOW` khớp điều kiện được tách riêng vào `shadow_triggered_rules` để phục vụ giám sát.
    - **Bước 4.4 — Tổng hợp phán quyết cuối cùng (`Conflict Resolver & Decision Aggregator`):**
        - Xác định hành động có mức độ nghiêm trọng cao nhất từ các quy tắc `ACTIVE` bị vi phạm theo thứ tự phân cấp `SEVERITY_HIERARCHY`: `REJECT` $\rightarrow$ `REVIEW` $\rightarrow$ `ALERT` $\rightarrow$ `SCORE_BOOST` $\rightarrow$ `PASS`.
        - Nếu không có quy tắc `REJECT`/`REVIEW` nào kích hoạt nhưng `model_score` vượt ngưỡng `score_threshold`, giao dịch vẫn được gắn nhãn nghi vấn (`REVIEW` / `ALERT`) để đưa vào danh sách cảnh báo.
5. Hệ thống lưu kết quả chấm điểm của toàn bộ giao dịch, ghi vết từng quy tắc kích hoạt vào bảng `rule_execution_logs` (kèm `batch_detection_job_id` và `condition_snapshot`), và cập nhật trạng thái tác vụ thành `succeeded`.
6. Hệ thống thông báo tác vụ hoàn tất và điều hướng người dùng tới màn hình xem kết quả (`SUC-16`).

### Luồng ngoại lệ (Exception Flows)

- **4a. Bất tương thích lược đồ dữ liệu (Schema Mismatch):**
    - Tại bước 4, nếu tập dữ liệu đầu vào thiếu các cột đặc trưng bắt buộc mà `ModelVersion` đã chọn yêu cầu khi suy luận, hệ thống dừng tác vụ, cập nhật trạng thái `failed` và thông báo rõ danh sách các cột bị thiếu.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-07:** Thứ tự ưu tiên giải quyết xung đột hành động giữa các quy tắc (`SEVERITY_HIERARCHY`) bắt buộc tuân theo: `REJECT` > `REVIEW` > `ALERT` > `SCORE_BOOST` > `PASS`.
- **BR-DT-08:** Các quy tắc ở trạng thái `SHADOW` khi kích hoạt bắt buộc được lưu vết với cờ `is_shadow = TRUE` trong `rule_execution_logs` nhưng tuyệt đối không được cộng vào `total_risk_score` hay làm thay đổi `highest_severity_action` của giao dịch.

## SUC-16: View detection result (Xem kết quả phát hiện gian lận)

### Thông tin chung

- **Mã Use Case:** SUC-16
- **Tên Use Case:** View detection result (Xem kết quả phát hiện gian lận)
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Data Scientist
- **Mô tả:** Cho phép Fraud Analyst và Data Scientist xem bảng tổng hợp và danh sách chi tiết kết quả phân loại gian lận của một tác vụ phát hiện (`Detection Job`), tra cứu lý do gắn cờ (mã quy tắc vi phạm, bằng chứng dữ liệu, điểm số AI) và chuyển tiếp các giao dịch đáng ngờ sang phân hệ **Investigation** để tạo hồ sơ điều tra (Case).
- **Tiền điều kiện:** Đã có ít nhất một tác vụ phát hiện (`SUC-15`) hoàn tất ở trạng thái `succeeded`; người dùng có quyền `detection_job: view`.
- **Hậu điều kiện:** Kết quả phân loại và bằng chứng rủi ro hiển thị đầy đủ; các giao dịch nghi vấn được chọn sẽ được khởi tạo thành các hồ sơ điều tra (Cases) bên phân hệ Investigation (`BUC-02`).
- **Sự kiện kích hoạt (Trigger):** Fraud Analyst hoặc Data Scientist nhấn vào một tác vụ đã hoàn tất trong danh sách Detection Jobs hoặc chuyển sang từ cuối luồng `SUC-15`.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng (`Fraud Analyst` hoặc `Data Scientist`) chọn một `Detection Job` để xem kết quả.
2. Hệ thống tải dữ liệu tổng hợp của đợt rà soát cùng danh sách kết quả đánh giá từng giao dịch và nhật ký `rule_execution_logs`.
3. Hệ thống hiển thị trang **Detection Result Overview** gồm:
    - **Thống kê tổng quan (Summary Cards):** Tổng số giao dịch đã quét, tổng số giao dịch bị cảnh báo nghi vấn, tỷ lệ phân bổ theo từng hành động (`REJECT`, `REVIEW`, `ALERT`, `PASS`), và biểu đồ phân phối điểm rủi ro (`Model Fraud Score` & `Rule Risk Score`).
    - **Thống kê hiệu quả tập luật (Rule Trigger Breakdown):** Bảng thống kê số lần kích hoạt của từng `rule_code` (tách biệt rõ nhóm `ACTIVE` và nhóm `SHADOW`).
    - **Bảng danh sách giao dịch chi tiết (Transaction Detection Table):**
        - Định danh giao dịch (`event_id`), định danh khách hàng/thẻ (`user_id`), thời gian (`timestamp`), số tiền (`amount`).
        - Điểm xác suất từ mô hình AI (`model_score` từ `0.0` đến `1.0`).
        - Tổng điểm rủi ro từ tập luật (`total_risk_score` từ `0.0` đến `100.0`).
        - Danh sách các mã quy tắc bị vi phạm (`triggered_rules`).
        - Hành động phán quyết cuối cùng (`highest_severity_action`).
4. Người dùng có thể lọc danh sách giao dịch theo mức hành động (ví dụ: chỉ lọc `REJECT` và `REVIEW`), lọc theo mã quy tắc vi phạm (`rule_code`), theo khoảng điểm `model_score`, hoặc sắp xếp theo số tiền giao dịch giảm dần.
5. Người dùng nhấp vào một giao dịch bất kỳ để mở ngăn **Detection Evidence Drawer (Chi tiết bằng chứng nghi vấn)**:
    - Hiển thị danh sách đầy đủ các quy tắc đã kích hoạt kèm `trigger_reason` và `condition_snapshot` (giá trị thực tế của các trường `mapped.*`, `feature.*`, `model.*` tại thời điểm giao dịch).
    - Hiển thị các đặc trưng đóng góp lớn nhất vào điểm số rủi ro của mô hình AI cho giao dịch đó.
6. Để chuyển tiếp điều tra, `Fraud Analyst` tích chọn các giao dịch đáng ngờ (hoặc chọn **Select All Flagged Transactions**) và nhấn nút **Send to Investigation (Create Cases)**.
7. Hệ thống gom nhóm các giao dịch đáng ngờ (theo từng giao dịch hoặc gom theo cùng `user_id`) để khởi tạo các hồ sơ điều tra (`Cases`) sang phân hệ **Investigation** và hiển thị thông báo xác nhận.

### Luồng rẽ nhánh (Alternative Flows)

- **6a. Xuất kết quả phát hiện ra tệp (Export Detection Results):**
    - Người dùng có thể nhấn nút **Export Results** để tải danh sách kết quả chấm điểm và các lý do vi phạm dưới định dạng `.csv` hoặc `.parquet` phục vụ báo cáo hoặc phân tích ngoại tuyến.
- **6b. Tinh chỉnh ngưỡng hoặc đề xuất luật từ kết quả rà soát:**
    - Dựa trên thống kê các quy tắc `SHADOW` trong đợt chạy, `Data Scientist` có thể điều hướng nhanh sang `SUC-14` để nâng cấp một quy tắc `SHADOW` có hiệu quả tốt lên `ACTIVE`.