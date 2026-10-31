<!-- [26-10-29] Approved update of Detection - Inference System Use Case Specification (SUC-15, SUC-16, SUC-19) -->
# Đặc tả use case hệ thống phân hệ Detection — Inference

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Stage: 3. Design
Updated: 29/10/2026 `[26-10-29]`

# 0. Tài liệu liên quan

- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)
- `docs/features/project_management/design.md` (Thiết kế Kiến trúc Quản lý Dự án & Ràng buộc Schema `BR-PM-04`, `BR-PM-05`, `BR-PM-06`)
- `docs/features/detection/user-flow-and-ui-design.md` (Thiết kế User Flow & UI/UX: Module Detection)

# 1. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng suy luận và phát hiện gian lận theo mẻ (**Hybrid Batch Detection & Inference**) trong phân hệ **Detection** của hệ thống USFDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-19** | **View detection jobs** | Fraud Analyst, Data Scientist | Xem danh mục các tác vụ phát hiện gian lận (`DetectionJob`) trong dự án, các chỉ số tổng hợp (tổng giao dịch quét, số lượng cảnh báo, phân bổ `REJECT`/`REVIEW`/`ALLOW`), lọc theo trạng thái và điều hướng tới kết quả chi tiết. | High |
| **SUC-15** | **Start detection job** | Data Scientist, Fraud Analyst | Khởi chạy tác vụ chấm điểm mẻ trên tập giao dịch cần rà soát (từ `DatasetArtifact` ở giai đoạn `RAW` hoặc tải tệp trực tiếp `input_file_path`) bằng cách kết hợp đồng thời điểm xác suất từ `ModelVersion` (`APPROVED` hoặc chế độ `Rule-Only`) và tập luật nghiệp vụ `ACTIVE` (`JsonLogic`). | High |
| **SUC-16** | **View detection result** | Fraud Analyst, Data Scientist | Xem bảng thống kê tổng quan, biểu đồ phân phối điểm rủi ro, thống kê luật kích hoạt, danh sách giao dịch chi tiết kèm ngăn kéo bằng chứng (`Detection Evidence Drawer`), xuất tệp kết quả (`.csv`/`.parquet`) và chuyển tiếp các giao dịch đáng ngờ sang phân hệ **Investigation** để tạo hồ sơ điều tra (`InvestigationCase`). | High |

---

# 2. Chi tiết đặc tả Use Case

## SUC-19: View detection jobs (Xem danh sách tác vụ phát hiện gian lận)

### Thông tin chung

- **Mã Use Case:** SUC-19
- **Tên Use Case:** View detection jobs (Xem danh sách tác vụ phát hiện gian lận)
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Data Scientist
- **Tác nhân phụ (Secondary Actor):** `InferenceService`, `IDetectionJobRepository`
- **Mô tả:** Cho phép Fraud Analyst và Data Scientist theo dõi toàn bộ danh sách các tác vụ phát hiện gian lận theo mẻ (`DetectionJob`) trong phạm vi dự án đang làm việc, bao gồm thông tin cấu hình động cơ (`ModelVersion` + số lượng `Rule` `ACTIVE`), nguồn dữ liệu đầu vào (`RAW` Artifact hoặc tệp tải lên), trạng thái thực thi (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`), số lượng giao dịch đã quét, tỷ lệ nghi vấn (`fraud_rate`), thời gian xử lý và điều hướng nhanh sang trang phân tích kết quả (`SUC-16`).
- **Tiền điều kiện:** Người dùng đã chọn một Dự án (`Active Project`) trên hệ thống.
- **Hậu điều kiện:** Danh sách các `DetectionJob` cùng các thẻ thống kê KPI của dự án được hiển thị chính xác.
- **Sự kiện kích hoạt (Trigger):** Người dùng điều hướng tới mục **Detection** (`/detection`) trên thanh điều hướng bên trái.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng (`Fraud Analyst` hoặc `Data Scientist`) truy cập màn hình **Detection Jobs Hub** (`/detection`).
2. Hệ thống gọi `GET /api/v1/detection/jobs?project_id={project_id}` để lấy danh sách các tác vụ phát hiện thuộc dự án sắp xếp theo thời gian tạo mới nhất.
3. Hệ thống tổng hợp và hiển thị khu vực **KPI Summary Cards**:
	- Tổng số tác vụ phát hiện trong dự án (`Total Detection Jobs`) và số tác vụ hoàn tất (`Completed`).
	- Tổng số giao dịch đã rà soát (`Total Transactions Scanned`).
	- Tổng số giao dịch bị gắn cờ nghi vấn (`Flagged Transactions`: `REJECT` + `REVIEW`) kèm tỷ lệ phần trăm trung bình.
	- Tổng số hồ sơ điều tra đã chuyển sang phân hệ Investigation (`Cases Dispatched`).
4. Hệ thống hiển thị thanh công cụ tìm kiếm theo tên tác vụ, bộ lọc trạng thái (`ALL`, `COMPLETED`, `RUNNING`, `FAILED`), và bảng danh sách **Detection Jobs** gồm các cột:
	- Tên tác vụ (`job_name`) và mã định danh (`job_id`).
	- Nguồn dữ liệu đầu vào (`target_artifact_id` ở trạng thái `RAW` hoặc đường dẫn tệp trực tiếp `input_path`).
	- Cấu hình động cơ phát hiện (`Engine Snapshot`: tên mô hình + `semver` + ngưỡng `score_threshold`, hoặc nhãn `Rule-Only`, kèm số lượng quy tắc `ACTIVE` tham gia).
	- Trạng thái thực thi (`status`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`).
	- Tổng số bản ghi (`total_records`), số lượng giao dịch nghi vấn (`fraud_records` / `fraud_rate`) và phân bổ nhanh (`REJECT` / `REVIEW` / `ALLOW`).
	- Thời gian thực thi (`execution_time_seconds`), thời điểm tạo (`created_at`), và cột thao tác (**View Results**).
5. Khi người dùng nhấn vào một dòng tác vụ hoặc nút **View Results**, hệ thống điều hướng tới màn hình `/detection/jobs/{job_id}` (`SUC-16`).

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-06 (Cross-Project Isolation):** Danh sách tác vụ phát hiện được cô lập chặt chẽ theo `project_id` đang làm việc.

---

## SUC-15: Start detection job (Khởi chạy tác vụ phát hiện gian lận theo mẻ)

### Thông tin chung

- **Mã Use Case:** SUC-15
- **Tên Use Case:** Start detection job (Khởi chạy tác vụ phát hiện gian lận theo mẻ)
- **Tác nhân chính (Primary Actor):** Data Scientist, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** `InferenceService`, `BatchInferenceExecutor`, `RuleExecutor`, `ProjectSchemaValidator`, `IFileStorage`
- **Mô tả:** Cho phép Data Scientist hoặc Fraud Analyst khởi chạy một tác vụ rà soát và chấm điểm gian lận hàng loạt (Hybrid Batch Detection Job) trên tập giao dịch cần kiểm tra. Hệ thống hỗ trợ **2 tùy chọn nguồn dữ liệu đầu vào**:
	1. Chọn một `DatasetArtifact` có sẵn trong dự án ở giai đoạn **`RAW`** (`target_artifact_id`).
	2. Cung cấp đường dẫn tệp dữ liệu trực tiếp (`input_file_path` — `.csv`, `.parquet`, `.pq`, `.json`) để tải lên và rà soát trực tiếp.
	Tác vụ kết hợp đồng thời điểm xác suất từ phiên bản mô hình AI đã kích hoạt (`ModelVersion` có `status = 'APPROVED'`, hoặc chế độ **Rule-Only**) và phán quyết từ toàn bộ các quy tắc nghiệp vụ đang hoạt động (`Rule` có `status = 'ACTIVE'`) trong dự án.
- **Tiền điều kiện:**
	1. Người dùng đang làm việc trong một Dự án (`Active Project`) có trạng thái `ACTIVE`.
	2. Dự án đã có ít nhất một động cơ phát hiện khả dụng: ít nhất một `ModelVersion` ở trạng thái `APPROVED` (khi chạy chế độ Hybrid / Model) hoặc ít nhất một `Rule` ở trạng thái `ACTIVE` (khi chạy chế độ Rule-Only).
- **Hậu điều kiện:**
	- *Thành công:* Bản ghi `detection_jobs` chuyển sang trạng thái `COMPLETED`; tệp kết quả `predictions.parquet` được lưu trữ trên `IFileStorage` chứa đầy đủ các cột gốc/ánh xạ cùng `model_score`, `triggered_rules`, `triggered_rule_details`, `rule_action`, `final_action` (`REJECT`, `REVIEW`, `ALLOW`), và `is_flagged`; các chỉ số thống kê tổng hợp (`summary_metrics`) được lưu vào bản ghi `DetectionJob`.
	- *Thất bại:* Bản ghi `detection_jobs` được đánh dấu `FAILED` kèm thông báo lỗi chi tiết (`error_message`).
- **Sự kiện kích hoạt (Trigger):** Người dùng nhấn nút **“+ New Detection Job”** tại màn hình Detection Jobs Hub (`/detection`).

### Luồng sự kiện chính (Basic Flow)

1. Người dùng (`Data Scientist` hoặc `Fraud Analyst`) mở màn hình **New Detection Job Wizard** (`/detection/new`).
2. Hệ thống hiển thị biểu mẫu cấu hình tác vụ phát hiện gồm 3 bước:
	- **Bước 1 — Chọn Nguồn Dữ liệu Đầu vào (`Input Data Source`):** Người dùng chọn 1 trong 2 phương thức:
		- *Phương thức 1 (`Existing RAW Dataset Artifact`):* Chọn یک `DatasetArtifact` thuộc dự án hiện tại có `pipeline_stage = 'RAW'` (`target_artifact_id`).
		- *Phương thức 2 (`Direct File Upload / File Path`):* Chọn tệp dữ liệu trực tiếp từ máy trạm hoặc nhập đường dẫn tệp (`input_file_path` định dạng `.csv`, `.parquet`, `.pq`, `.json`).
	- **Bước 2 — Cấu hình Động cơ Phát hiện Kết hợp (`Hybrid Detection Engine`):**
		- *Động cơ Mô hình AI (`model_version_id`):* Chọn một phiên bản mô hình đang ở trạng thái `APPROVED` của dự án (hiển thị tên mô hình, `semver`, `decision_threshold` khuyến nghị), hoặc chọn chế độ **Rule-Only (Không sử dụng mô hình AI)**.
		- *Động cơ Tập luật (`use_rules`):* Mặc định nạp toàn bộ các quy tắc có trạng thái `ACTIVE` của dự án (sử dụng phiên bản `current_version` chứa biểu thức `JsonLogic` và hành động `ALLOW`, `REVIEW`, `REJECT`). Người dùng có thể bật/tắt việc kết hợp tập luật nếu đã chọn mô hình AI.
	- **Bước 3 — Thiết lập Ngưỡng & Khởi chạy (`Decision Policy & Launch`):**
		- Thiết lập **Ngưỡng phân loại rủi ro mô hình (`score_threshold`):** Mặc định lấy theo `decision_threshold` của `ModelVersion` đã chọn (ví dụ `0.50` hoặc `0.80`), cho phép tùy chỉnh trong khoảng `(0.0, 1.0)`.
		- Nhập **Tên tác vụ (`job_name`)**.
3. Người dùng nhấn nút **Start Detection Job**.
4. Hệ thống gọi `POST /api/v1/detection/jobs`, kiểm tra hợp lệ nguồn dữ liệu đầu vào:
	- Nếu truyền `target_artifact_id`: kiểm tra artifact tồn tại, thuộc dự án hiện tại (`BR-PM-06`), và bắt buộc có `pipeline_stage == 'RAW'`.
	- Nếu truyền `input_file_path`: kiểm tra tệp tồn tại, đúng định dạng hỗ trợ, đọc dữ liệu và kiểm tra tính tương thích lược đồ với `project.raw_schema` (`ProjectSchemaValidator.validate_dataframe(..., allow_missing_target=True)`), sau đó lưu bản sao tệp đầu vào của tác vụ lên `IFileStorage`.
5. Hệ thống khởi tạo bản ghi `DetectionJob` ở trạng thái `RUNNING` và điều phối `BatchInferenceExecutor` thực thi qua các bước:
	- **Bước 5.1 — Truy vết Pipeline Lineage & Chuẩn bị đặc trưng (khi dùng AI Model):**
		- Từ `ModelVersion` đã chọn (`run_id` $\rightarrow$ `RunDataset` $\rightarrow$ `DatasetArtifact`), hệ thống tự động truy vết ngược chuỗi phả hệ dữ liệu (`PRE_PROCESSED` $\rightarrow$ `FEATURE_ENGINEERED` $\rightarrow$ `MAPPED` $\rightarrow$ `RAW`) để thu thập:
			- `column_mapping` từ artifact `MAPPED`.
			- Bộ trích xuất đặc trưng `fitted_feature_engineers.joblib` từ artifact `FEATURE_ENGINEERED`.
			- Bộ chuẩn hóa đặc trưng `preprocessor.joblib` / `fitted_pipeline.joblib` và trọng số mô hình (`model.joblib` hoặc `model_bundle.zip`).
		- Áp dụng `column_mapping` và `fitted_feature_engineers.joblib` lên dữ liệu đầu vào `RAW` để sinh các đặc trưng làm giàu (`enriched_features`).
	- **Bước 5.2 — Suy luận Mô hình AI (`Model Inference`):**
		- Nếu có chọn `ModelVersion`, hệ thống chạy dự đoán hàng loạt để sinh xác suất gian lận `model_score` ($0.0 \rightarrow 1.0$) cho từng giao dịch. (Nếu chạy chế độ *Rule-Only*, `model_score = 0.0`).
	- **Bước 5.3 — Thực thi Rule Engine (`RuleExecutor` / `JsonLogicEvaluator`):**
		- Với mỗi giao dịch, hệ thống đóng gói ngữ cảnh dữ liệu (gồm các trường `raw`, `mapped`, `enriched` và `model_score`), duyệt qua toàn bộ các quy tắc `ACTIVE` của dự án:
			- Ghi nhận danh sách mã quy tắc khớp điều kiện vào `triggered_rules` kèm chi tiết mệnh đề thỏa mãn (`matched_clauses` trong `triggered_rule_details`).
	- **Bước 5.4 — Tổng hợp phán quyết cuối cùng (`Conflict Resolver & Decision Aggregator` — `BR-DT-07`):**
		- Nếu có bất kỳ quy tắc `ACTIVE` nào vi phạm có hành động `REJECT` $\rightarrow$ phán quyết cuối cùng `final_action = 'REJECT'`.
		- Ngược lại, nếu có quy tắc `ACTIVE` vi phạm có hành động `REVIEW` **HOẶC** điểm mô hình `model_score >= score_threshold` (khi có sử dụng mô hình AI) $\rightarrow$ phán quyết cuối cùng `final_action = 'REVIEW'`.
		- Ngược lại $\rightarrow$ phán quyết cuối cùng `final_action = 'ALLOW'`.
		- Các giao dịch có `final_action` thuộc `('REJECT', 'REVIEW')` được đánh dấu là giao dịch nghi vấn (`is_flagged = True`).
6. Hệ thống lưu bảng kết quả chấm điểm ra tệp `predictions.parquet` trên `IFileStorage`, tính toán bộ chỉ số tổng hợp `summary_metrics` (số lượng `REJECT`, `REVIEW`, `ALLOW`, tổng giá trị giao dịch nghi vấn `amount_at_risk`, thống kê số lần kích hoạt từng `rule_code`, và phân phối điểm rủi ro), đồng thời cập nhật trạng thái `DetectionJob` thành `COMPLETED`.
7. Hệ thống thông báo tác vụ hoàn tất và điều hướng người dùng tới màn hình xem kết quả `/detection/jobs/{job_id}` (`SUC-16`).

### Luồng ngoại lệ (Exception Flows)

- **4a. Artifact đầu vào không ở giai đoạn `RAW` (`400 Bad Request`):**
	- Nếu người dùng truyền `target_artifact_id` nhưng `DatasetArtifact` đó có `pipeline_stage != 'RAW'`, hệ thống từ chối khởi chạy và trả về thông báo lỗi yêu cầu chọn artifact ở giai đoạn `RAW`.
- **4b. Bất tương thích lược đồ dữ liệu đầu vào (`Schema Mismatch` — `400 Bad Request` / `FAILED`):**
	- Nếu tệp dữ liệu đầu vào (`input_file_path` hoặc `RAW` artifact) thiếu các cột bắt buộc trong `project.raw_schema` hoặc thiếu các cột đặc trưng mà `ModelVersion` yêu cầu khi suy luận (trừ cột nhãn `label`/`is_fraud` không bắt buộc khi inference), hệ thống dừng tác vụ và thông báo rõ danh sách các cột bị thiếu.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-07 (Decision Hierarchy):** Thứ tự ưu tiên giải quyết xung đột phán quyết giữa Rule Engine và AI Model bắt buộc tuân theo: `REJECT` (từ Rule `REJECT`) > `REVIEW` (từ Rule `REVIEW` hoặc `model_score >= score_threshold`) > `ALLOW`.
- **BR-DT-11 (RAW Input Standardization):** Dữ liệu đầu vào của tác vụ phát hiện (`target_artifact_id` hoặc `input_file_path`) luôn ở định dạng lược đồ `RAW`; quá trình ánh xạ (`MAPPED`), làm giàu đặc trưng (`FEATURE_ENGINEERED`) và chuẩn hóa (`PRE_PROCESSED`) được thực hiện tự động và nhất quán thông qua các bộ biến đổi đã khớp (`fitted artifacts`) của mô hình.

---

## SUC-16: View detection result (Xem kết quả phát hiện gian lận và chuyển tiếp điều tra)

### Thông tin chung

- **Mã Use Case:** SUC-16
- **Tên Use Case:** View detection result (Xem kết quả phát hiện gian lận và chuyển tiếp điều tra)
- **Tác nhân chính (Primary Actor):** Fraud Analyst, Data Scientist
- **Tác nhân phụ (Secondary Actor):** `InferenceService`, `IInvestigationRepository`, `IFileStorage`
- **Mô tả:** Cho phép Fraud Analyst và Data Scientist xem bảng tổng hợp và danh sách chi tiết kết quả phân loại gian lận của một tác vụ phát hiện (`DetectionJob`), tra cứu lý do gắn cờ (điểm xác suất mô hình AI, các quy tắc `ACTIVE` bị vi phạm cùng biểu thức điều kiện thỏa mãn và giá trị đặc trưng thực tế), xuất tệp báo cáo (`.csv`/`.parquet`) và chuyển tiếp các giao dịch đáng ngờ sang phân hệ **Investigation** để khởi tạo hồ sơ điều tra (`InvestigationCase`).
- **Tiền điều kiện:** Tác vụ phát hiện (`DetectionJob`) đã tồn tại trong dự án.
- **Hậu điều kiện:** Kết quả phân loại và bằng chứng rủi ro hiển thị đầy đủ; các giao dịch nghi vấn được chọn khi nhấn **Send to Investigation** được lưu vào bảng `investigation_cases` kèm đầy đủ ngữ cảnh phát hiện.
- **Sự kiện kích hoạt (Trigger):** Người dùng chọn một tác vụ trong danh sách **Detection Jobs Hub** (`SUC-19`) hoặc được điều hướng tự động ngay sau khi hoàn tất `SUC-15`.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng (`Fraud Analyst` hoặc `Data Scientist`) truy cập màn hình **Detection Result Explorer** (`/detection/jobs/{job_id}`).
2. Hệ thống gọi `GET /api/v1/detection/jobs/{job_id}` và `GET /api/v1/detection/jobs/{job_id}/results` để tải thông tin tổng hợp cùng danh sách kết quả đánh giá từng giao dịch từ `predictions.parquet`.
3. Hệ thống hiển thị trang **Detection Result Overview** gồm:
	- **Thống kê tổng quan (Summary KPI Cards):**
		- Tổng số giao dịch đã quét (`total_records`) và thời gian thực thi.
		- Số lượng và tỷ lệ giao dịch theo từng mức phán quyết: `REJECT` (Từ chối), `REVIEW` (Cần rà soát), `ALLOW` (Chấp thuận).
		- Tổng số giao dịch nghi vấn (`Flagged Count` = `REJECT` + `REVIEW`, kèm `fraud_rate`).
		- Tổng giá trị giao dịch có rủi ro (`Amount at Risk` — tổng `amount` của các giao dịch `REJECT` và `REVIEW`).
	- **Biểu đồ phân phối & Thống kê tập luật (Analytics Panels):**
		- *Risk Score Distribution:* Biểu đồ phân bố điểm xác suất `model_score` trên toàn bộ lô dữ liệu kèm vạch ngưỡng `score_threshold`.
		- *Rule Trigger Breakdown:* Bảng thống kê số lượt kích hoạt (`hit_count`, `hit_rate`) và hành động (`REJECT` / `REVIEW` / `ALLOW`) của từng `rule_code` trong đợt chạy.
	- **Bảng danh sách giao dịch chi tiết (Transaction Detection Table):**
		- Định danh giao dịch (`event_id`), định danh khách hàng/thẻ (`user_id`), thời gian (`timestamp`), số tiền (`amount`).
		- Điểm xác suất từ mô hình AI (`model_score` từ `0.0` đến `1.0`).
		- Danh sách các mã quy tắc bị vi phạm (`triggered_rules`).
		- Hành động phán quyết cuối cùng (`final_action`: `REJECT`, `REVIEW`, `ALLOW`).
		- Trạng thái hồ sơ điều tra (`case_id` nếu giao dịch đã được gửi sang Investigation).
4. Người dùng có thể lọc và tìm kiếm danh sách giao dịch theo:
	- Mức phán quyết (`ALL`, `FLAGGED` [`REJECT` + `REVIEW`], `REJECT`, `REVIEW`, `ALLOW`).
	- Mã quy tắc vi phạm (`rule_code`).
	- Từ khóa tìm kiếm (`event_id` hoặc `user_id`) và khoảng điểm `min_score` / `max_score`.
5. Người dùng nhấp vào một dòng giao dịch bất kỳ để mở ngăn kéo **Detection Evidence Drawer (Chi tiết bằng chứng nghi vấn)**:
	- Hiển thị tóm tắt phán quyết cuối cùng (`final_action`), điểm xác suất AI (`model_score` so với `score_threshold`) và mức độ rủi ro.
	- Hiển thị danh sách chi tiết các quy tắc đã kích hoạt (`rule_code`, `rule_name`, `action`, và các mệnh đề điều kiện cụ thể đã khớp `matched_clauses`).
	- Hiển thị bảng chụp nhanh toàn bộ giá trị đặc trưng (`condition_snapshot` / `features`) của giao dịch tại thời điểm chấm điểm.
6. Để chuyển tiếp điều tra, người dùng tích chọn một hoặc nhiều giao dịch đáng ngờ trên bảng (hoặc nhấn nút ngay trong ngăn kéo Evidence Drawer) và nhấn **Send to Investigation (Create Cases)**.
7. Hệ thống gọi `POST /api/v1/detection/jobs/{job_id}/send-to-investigation`, khởi tạo các bản ghi `InvestigationCase` trong cơ sở dữ liệu (lưu `project_id`, `event_id`, `status = 'PENDING'`, `risk_level`, `fraud_probability`, và `metadata` chứa `job_id`, `user_id`, `amount`, `timestamp`, `final_action`, `triggered_rules`, `features`), hiển thị thông báo xác nhận và cho phép điều hướng trực tiếp sang phân hệ **Investigation** (`/investigation`).

### Luồng rẽ nhánh (Alternative Flows)

- **6a. Xuất kết quả phát hiện ra tệp (`GET /api/v1/detection/jobs/{job_id}/export`):**
	- Người dùng nhấn nút **Export CSV** hoặc **Export Parquet** trên thanh công cụ để tải toàn bộ bảng kết quả chấm điểm (kèm `model_score`, `triggered_rules`, `final_action`) về máy phục vụ báo cáo hoặc phân tích ngoại tuyến.
- **2a. Tác vụ phát hiện bị thất bại (`status = 'FAILED'`):**
	- Nếu `DetectionJob` có trạng thái `FAILED`, hệ thống hiển thị khung thông báo lỗi chi tiết (`error_message`) và nút khởi tạo lại tác vụ.
