<!-- [26-10-24] Approved update of Detection - Training System Use Case Specification (SUC-08, SUC-09, SUC-10, SUC-17, SUC-27) -->
# Đặc tả use case hệ thống phân hệ Detection - Training

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Stage: 3. Design
Updated: 24/10/2026 `[26-10-24]`

# 0. Tài liệu liên quan

- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)
- `docs/features/detection/training/model_plugin/design.md` (Thiết kế Kiến trúc Plugin Mô hình Học máy)
- `docs/features/detection/user-flow-and-ui-design.md` (Thiết kế User Flow & UI/UX: Module Detection)

# 1. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng quản lý và huấn luyện mô hình học máy trong phân hệ **Detection — Training** của hệ thống USFDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-27** | **View models & training runs** | Data Scientist | Xem danh mục mô hình đã đăng ký (`BUILTIN` & `SCRIPT`), các phiên bản mô hình (`ModelVersion`) và lịch sử các lần chạy huấn luyện (`TrainingRun`) trong dự án. | High |
| **SUC-08** | **Start model training** | Data Scientist | Chọn tập dữ liệu đầu vào (`FEATURE_ENGINEERED` / `PRE_PROCESSED`), chọn mô hình mục tiêu, cấu hình siêu tham số (`hyperparameters`) và khởi chạy huấn luyện. | High |
| **SUC-09** | **View model training result** | Data Scientist | Xem các chỉ số đánh giá (`ROC-AUC`, `PR-AUC`, `F1`, `F2`, `Precision`, `Recall`, `Confusion Matrix`), đồ thị đường cong và mô phỏng điều chỉnh ngưỡng quyết định (`Threshold Simulator`). | High |
| **SUC-10** | **Activate model** | Data Scientist | Kiểm tra tính toàn vẹn artifact, thiết lập ngưỡng quyết định (`decision_threshold`) và đưa phiên bản mô hình (`ModelVersion`) vào trạng thái hoạt động (`APPROVED`) để sẵn sàng phục vụ phát hiện gian lận (`SUC-15`). | High |
| **SUC-17** | **Import custom model** | Data Scientist | Tải lên gói mã nguồn `.zip` hoặc trỏ đường dẫn thư mục/tệp mô hình tùy chỉnh, kiểm tra an toàn 2 giai đoạn (Static AST + Dynamic Dry-Run) và đăng ký vào Model Registry. | High |

---

# 2. Chi tiết đặc tả Use Case

## SUC-27: View models & training runs (Xem danh mục mô hình và lịch sử huấn luyện)

### Thông tin chung

- **Mã Use Case:** SUC-27
- **Tên Use Case:** View models & training runs (Xem danh mục mô hình và lịch sử huấn luyện)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `TrainingOrchestrationService`, `IModelRepository`, `IModelVersionRepository`, `ITrainingRunRepository`
- **Mô tả:** Cho phép Data Scientist theo dõi tổng quan toàn bộ các lần chạy huấn luyện (`TrainingRun`), danh mục các thuật toán đã đăng ký trong Model Registry (bao gồm mô hình dựng sẵn `BUILTIN` và mô hình tùy chỉnh `SCRIPT`), cùng danh sách các phiên bản mô hình (`ModelVersion`) và trạng thái kích hoạt của chúng trong phạm vi dự án đang làm việc.
- **Tiền điều kiện:** Người dùng đã chọn một Dự án (`Active Project`) trên hệ thống.
- **Hậu điều kiện:**
	- Hiển thị đầy đủ thẻ thống kê KPI, bảng lịch sử `Training Runs` và danh mục `Model Registry` kèm các phiên bản `ModelVersion`.
- **Sự kiện kích hoạt (Trigger):** Data Scientist điều hướng tới mục **Models** (`/models`) trên thanh điều hướng bên trái.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist truy cập màn hình **Model Hub** (`/models`).
2. Hệ thống gọi `GET /api/v1/training/models?project_id={project_id}` và `GET /api/v1/training/runs?project_id={project_id}`.
3. Hệ thống tổng hợp và hiển thị khu vực **KPI Summary Cards**:
	- Tổng số lần chạy huấn luyện (`Total Runs`) và số lần hoàn tất (`Completed`).
	- Số lượng thuật toán trong Registry (`Registered Models`: `BUILTIN` + `SCRIPT`).
	- Số lượng phiên bản mô hình đang hoạt động (`Active / Approved Versions`).
	- Chỉ số `Best PR-AUC` cao nhất đạt được trong dự án kèm tên lần chạy tương ứng.
4. Tại tab **Training Runs**:
	- Hệ thống hiển thị bảng danh sách các lần chạy huấn luyện sắp xếp theo thời gian mới nhất, gồm: Tên lần chạy (`run_name`), Thuật toán (`model_name`), Tập dữ liệu (`dataset_artifact_id`), Trạng thái (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`), các chỉ số chính (`PR-AUC`, `ROC-AUC`, `F1-Score`), Thời lượng (`duration_seconds`), và cột Hành động (`View Result`, `Activate`).
	- Data Scientist có thể tìm kiếm theo tên lần chạy hoặc lọc theo trạng thái (`status`) và mô hình (`model_id`).
5. Tại tab **Model Registry**:
	- Hệ thống hiển thị danh sách các mô hình (`Model`) gồm: Tên hiển thị (`display_name`), Mã định danh (`model_name`), Loại thực thi (`BUILTIN` hoặc `SCRIPT`), Mô tả, và cấu hình siêu tham số mặc định (`default_hyperparameters`).
	- Khi Data Scientist mở rộng một dòng mô hình, hệ thống gọi `GET /api/v1/training/models/{model_id}/versions` và hiển thị bảng các phiên bản (`ModelVersion`) của mô hình đó: Số hiệu `semver`, Trạng thái (`CANDIDATE`, `APPROVED`, `DEPRECATED`, `ARCHIVED`), Ngưỡng quyết định (`decision_threshold`), Mã kiểm tra `checksum_sha256` (rút gọn), cùng nút **View Run** và **Activate**.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-06 (Cross-Project Isolation):** Danh sách mô hình tùy chỉnh (`SCRIPT`) và lịch sử `TrainingRun` được lọc theo `project_id` đang chọn, trong khi các mô hình hệ thống dựng sẵn (`BUILTIN` có `project_id = None`) luôn khả dụng cho mọi dự án.

---

## SUC-08: Start model training (Khởi chạy huấn luyện mô hình)

### Thông tin chung

- **Mã Use Case:** SUC-08
- **Tên Use Case:** Start model training (Khởi chạy huấn luyện mô hình)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** Compute Engine / Training Worker (`TrainingRunExecutor`), Hệ thống lưu trữ (`IFileStorage` / Object Storage)
- **Mô tả:** Cho phép Data Scientist lựa chọn tập dữ liệu đã làm giàu đặc trưng (`FEATURE_ENGINEERED` hoặc `PRE_PROCESSED`), chọn thuật toán học máy trong Model Registry (`Random Forest`, `XGBoost`, hoặc Custom Plugin `SCRIPT`), cấu hình bộ siêu tham số (`hyperparameters`) và khởi chạy tiến trình huấn luyện. Các bước chuẩn hóa dữ liệu đặc thù theo mô hình (Model-Owned Normalization) được đóng gói tự động bên trong mô hình (`preprocessor.joblib`).
- **Tiền điều kiện:**
	1. Người dùng đang làm việc trong một Dự án (`Active Project`).
	2. Trong dự án đã có ít nhất một `DatasetArtifact` đạt trạng thái `FEATURE_ENGINEERED` (từ `SUC-05`) hoặc `PRE_PROCESSED` và có `validation_status != 'FAILED'`.
- **Hậu điều kiện:**
	- *Thành công:* Bản ghi `training_runs` được cập nhật trạng thái `COMPLETED` kèm bộ chỉ số đánh giá (`accuracy`, `precision_score`, `recall_score`, `f1_score`, `loss`, `custom_metrics`) và `recommended_threshold`; liên kết dữ liệu huấn luyện được ghi nhận vào bảng `run_datasets`; tệp trọng số mô hình và `preprocessor.joblib` (hoặc `model_bundle.zip`) được lưu trữ bất biến trên `IFileStorage` kèm mã băm `checksum_sha256`; một phiên bản mô hình mới (`model_versions`) được tự động cấp phát số hiệu `semver` và đăng ký vào Model Registry ở trạng thái `CANDIDATE`.
	- *Thất bại:* Bản ghi `training_runs` chuyển sang trạng thái `FAILED` kèm thông tin lỗi (`error_message`); không sinh bản ghi `model_versions` mới.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút **“+ New Training Run”** tại màn hình Model Hub (`/models`) hoặc điều hướng từ bước hoàn tất làm giàu dữ liệu (`SUC-05`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist mở giao diện **Training Wizard** (`/models/train`).
2. Hệ thống tải danh sách các mô hình (`GET /api/v1/training/models`) và danh sách các Dataset cùng các `DatasetArtifact` hợp lệ ở trạng thái `FEATURE_ENGINEERED` hoặc `PRE_PROCESSED` thuộc dự án hiện tại.
3. Data Scientist thực hiện cấu hình qua 3 bước:
	- **Bước 1 — Chọn Tập dữ liệu đầu vào (`dataset_artifact_id`):** Chọn Dataset và phiên bản `DatasetArtifact` chứa cặp tệp `train_enriched.parquet` và `test_enriched.parquet`. Hệ thống hiển thị thông tin tóm tắt của Artifact (số dòng, số cột, trạng thái kiểm định `validation_status`).
	- **Bước 2 — Chọn Mô hình & Cấu hình Siêu tham số (`model_id`, `hyperparameters`):**
		- Chọn mô hình mục tiêu từ danh mục (`BUILTIN` hoặc `SCRIPT`).
		- Hệ thống tự động sinh biểu mẫu cấu hình siêu tham số dựa trên `hyperparameter_schema` và điền sẵn giá trị từ `default_hyperparameters` (hỗ trợ chỉnh sửa từng trường hoặc chỉnh sửa trực tiếp JSON và nút **Reset to Defaults**).
	- **Bước 3 — Kiểm tra & Khởi chạy (`Review & Launch`):**
		- Nhập hoặc giữ tên lần chạy tự động (`run_name`), kiểm tra bảng tổng hợp cấu hình.
4. Data Scientist nhấn nút **Start Training**.
5. Hệ thống gọi `POST /api/v1/training/runs`, khởi tạo `TrainingRun`, thực thi huấn luyện (tự động khớp `preprocessor.joblib` đối với mô hình `BUILTIN` hoặc chạy qua `_usfds_runner.py` đối với mô hình `SCRIPT`), tính toán đầy đủ bộ chỉ số qua `MetricEvaluator` và đăng ký `ModelVersion` mới.
6. Hệ thống thông báo hoàn tất huấn luyện và điều hướng người dùng sang trang xem kết quả chi tiết `/models/runs/{run_id}` (`SUC-09`).

### Luồng ngoại lệ (Exception Flows)

- **5a. Tập dữ liệu thiếu cột nhãn mục tiêu (`target_column`):**
	- Nếu `DatasetArtifact` không chứa cột nhãn mục tiêu (`label`, `is_fraud`, `target`,...), hệ thống bắt ngoại lệ, cập nhật `training_runs.status = 'FAILED'` kèm `error_message` chi tiết.
- **5b. Lỗi quá tải bộ nhớ hoặc ngoại lệ trong quá trình huấn luyện (Runtime Error):**
	- Nếu quá trình huấn luyện gặp lỗi runtime hoặc script plugin trả về mã thoát khác `0`, `TrainingRunExecutor` bắt ngoại lệ, dọn dẹp thư mục tạm, cập nhật `training_runs.status = 'FAILED'` kèm `error_message` và hiển thị nhật ký lỗi tại `SUC-09`.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-03:** Mỗi phiên bản mô hình (`model_versions`) sau khi tạo là bất biến (immutable), bắt buộc gắn với mã kiểm tra toàn vẹn `checksum_sha256` (64 ký tự) và tự động tăng số hiệu `semver` (`1.0.0` $\rightarrow$ `1.0.1`) trong cùng một `model_id`.

---

## SUC-09: View model training result (Xem kết quả huấn luyện mô hình)

### Thông tin chung

- **Mã Use Case:** SUC-09
- **Tên Use Case:** View model training result (Xem kết quả huấn luyện mô hình)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `TrainingOrchestrationService`, `MetricEvaluator`
- **Mô tả:** Cho phép Data Scientist xem báo cáo đánh giá hiệu năng chi tiết của mô hình sau khi huấn luyện (`ROC-AUC`, `PR-AUC`, `Precision`, `Recall`, `F1-Score`, `F2-Score`, `Confusion Matrix`), quan sát đồ thị `ROC Curve`, `Precision-Recall Curve`, `Score Distribution` và mô phỏng điều chỉnh ngưỡng cắt điểm rủi ro (`Decision Threshold Simulator`) để chọn ngưỡng vận hành tối ưu trước khi kích hoạt mô hình (`SUC-10`).
- **Tiền điều kiện:** Bản ghi `TrainingRun` đã tồn tại trong hệ thống (ở trạng thái `COMPLETED` hoặc `FAILED`).
- **Hậu điều kiện:** Báo cáo hiệu năng, biểu đồ đánh giá và trình mô phỏng ngưỡng được hiển thị trực quan; người dùng có thể chuyển tiếp ngưỡng quyết định đã chọn sang hộp thoại kích hoạt mô hình (`SUC-10`).
- **Sự kiện kích hoạt (Trigger):** Data Scientist chọn một lần chạy từ danh sách `Training Runs` (`SUC-27`) hoặc được điều hướng tự động ngay sau khi `SUC-08` hoàn tất.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist truy cập trang chi tiết kết quả huấn luyện `/models/runs/{run_id}`.
2. Hệ thống gọi `GET /api/v1/training/runs/{run_id}` (và `GET /api/v1/training/versions/{version_id}` nếu có `version_id`).
3. Hệ thống hiển thị bảng điều khiển kết quả huấn luyện gồm 4 khu vực chính:
	- **Thông tin định danh & Truy vết (Lineage Metadata):** Tên lần chạy (`run_name`), tên mô hình, số hiệu phiên bản (`semver`), trạng thái phiên bản (`CANDIDATE` / `APPROVED`), thời gian thực thi (`duration_seconds`), mã kiểm tra `checksum_sha256`, và liên kết tới `dataset_artifact_id`.
	- **Bộ chỉ số hiệu năng cốt lõi (Core Performance KPIs):**
		- Các chỉ số chuyên biệt cho dữ liệu gian lận mất cân bằng: `PR-AUC` (Average Precision), `ROC-AUC`, `F1-Score`, `F2-Score` (ưu tiên Recall gấp 2 lần Precision).
		- Các chỉ số chuẩn: `Precision`, `Recall`, `Accuracy`, `Loss`.
	- **Mô phỏng ngưỡng quyết định & Ma trận nhầm lẫn (Interactive Threshold Simulator & Confusion Matrix):**
		- Thanh trượt **Decision Threshold Slider** (từ `0.01` đến `0.99`, tra cứu tức thời trên lưới 100 điểm `threshold_tuning_grid` của `MetricEvaluator`) cùng các nút chọn nhanh ngưỡng khuyến nghị (`recommended_thresholds`: `Best F1`, `Best F2`, `Youden's J`, `Target Recall ≥ 90%`, `Target Recall ≥ 95%`).
		- Khi Data Scientist kéo thanh trượt hoặc chọn một preset, hệ thống cập nhật tức thời:
			- Ma trận nhầm lẫn 2x2 (`Confusion Matrix`: `TP` - bắt đúng gian lận, `FP` - báo động giả, `TN` - hợp lệ đúng, `FN` - bỏ sót gian lận) hỗ trợ chuyển đổi hiển thị giữa số lượng tuyệt đối và tỷ lệ phần trăm.
			- Bộ chỉ số tại ngưỡng đang chọn: `Precision`, `Recall`, `F1-Score`, `F2-Score`, và `False Positive Rate (FPR)`.
	- **Đồ thị đường cong & Phân phối điểm rủi ro (Evaluation Charts & Configuration):**
		- Biểu đồ đường cong `ROC Curve` (`FPR` vs `TPR`) và `Precision-Recall Curve` (`Recall` vs `Precision`).
		- Biểu đồ `Score Distribution Histogram`: Phân bố xác suất dự đoán giữa nhóm giao dịch Hợp lệ (`Legit`) và Gian lận (`Fraud`) kèm vạch đánh dấu ngưỡng quyết định hiện tại.
		- Khung thông tin `Hyperparameters` và đường dẫn lưu trữ `artifact_uri`.
4. Data Scientist nhấn nút **Activate Model Version** để mở hộp thoại `SUC-10` kèm ngưỡng `decision_threshold` đang chọn trên thanh trượt.

### Luồng ngoại lệ (Exception Flows)

- **2a. Lần chạy huấn luyện bị thất bại (`status = 'FAILED'`):**
	- Nếu `TrainingRun` có trạng thái `FAILED`, hệ thống ẩn các biểu đồ metric và hiển thị khung **Execution Error Log** chứa chi tiết nguyên nhân lỗi (`error_message`), cấu hình `hyperparameters` đã dùng và nút **Retry in Training Wizard** để cấu hình lại.

---

## SUC-10: Activate model (Kích hoạt phiên bản mô hình)

### Thông tin chung

- **Mã Use Case:** SUC-10
- **Tên Use Case:** Activate model (Kích hoạt phiên bản mô hình)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `TrainingOrchestrationService`, `IModelVersionRepository`, `IFileStorage`
- **Mô tả:** Cho phép Data Scientist đưa một phiên bản mô hình (`ModelVersion`) đã huấn luyện vào trạng thái hoạt động (`APPROVED`) kèm ngưỡng quyết định (`decision_threshold`) đã tinh chỉnh, để phiên bản đó sẵn sàng được lựa chọn trong các tác vụ phát hiện gian lận (`SUC-15`). Các phiên bản mô hình được kích hoạt độc lập (một dự án có thể có nhiều `ModelVersion` ở trạng thái `APPROVED` để người vận hành linh hoạt lựa chọn khi chạy Detection Job).
- **Tiền điều kiện:**
	1. Phiên bản mô hình (`model_versions`) đã được tạo từ một lần chạy huấn luyện thành công và có tệp artifact hợp lệ trên `IFileStorage`.
- **Hậu điều kiện:**
	- *Thành công:* Bản ghi `model_versions` được cập nhật `status = 'APPROVED'` và `decision_threshold` mới; các phiên bản mô hình khác giữ nguyên trạng thái hiện tại.
	- *Thất bại:* Không thay đổi trạng thái của `ModelVersion`.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút **“Activate Model”** tại trang chi tiết kết quả huấn luyện (`SUC-09`) hoặc tại bảng phiên bản trong Model Registry (`SUC-27`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn hành động **Activate Model** trên một `ModelVersion` (`version_id`, `semver`).
2. Hệ thống hiển thị hộp thoại **Activate Model Version Modal** gồm:
	- Thông tin định danh: Tên mô hình, số hiệu `semver`, framework, mã kiểm tra `checksum_sha256`.
	- Trường nhập **Decision Threshold (`decision_threshold`):** Mặc định điền sẵn giá trị ngưỡng mà người dùng đã chọn trên `Threshold Simulator` (hoặc `recommended_threshold` của lần chạy), cho phép tinh chỉnh trong khoảng `(0.0, 1.0)`.
	- Mô tả ghi chú phiên bản (`description`, tùy chọn).
3. Data Scientist kiểm tra thông tin và nhấn **Confirm Activate**.
4. Hệ thống gọi `POST /api/v1/training/versions/{version_id}/activate`.
5. Hệ thống kiểm tra tính toàn vẹn của tệp mô hình tại `artifact_uri` trên `IFileStorage` bằng cách xác nhận tệp tồn tại và đối chiếu mã băm SHA-256 thực tế với `checksum_sha256` đã lưu trong bản ghi `model_versions`.
6. Hệ thống cập nhật bản ghi `model_versions` với `status = ModelVersionStatus.APPROVED`, `decision_threshold` mới và `description` (nếu có).
7. Hệ thống trả về thông tin `ModelVersion` đã cập nhật và hiển thị thông báo kích hoạt thành công.

### Luồng ngoại lệ (Exception Flows)

- **5a. Tệp artifact không tồn tại hoặc sai lệch Checksum (`400 Bad Request`):**
	- Tại bước 5, nếu không tìm thấy tệp tại `artifact_uri` hoặc mã băm SHA-256 tính toán lại không khớp với `checksum_sha256` đã đăng ký, hệ thống chặn quá trình kích hoạt và trả về lỗi: *“Kiểm tra tính toàn vẹn thất bại: Artifact của phiên bản mô hình không tồn tại hoặc mã băm SHA-256 không khớp.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-04:** Mỗi `ModelVersion` được kích hoạt độc lập sang trạng thái `APPROVED` mà không tự động vô hiệu hóa các `ModelVersion` khác, cho phép nhiều mô hình/phiên bản cùng sẵn sàng phục vụ các tác vụ rà soát `SUC-15`.

---

## SUC-17: Import custom model (Tích hợp mô hình tùy chỉnh theo kiến trúc Plugin)

### Thông tin chung

- **Mã Use Case:** SUC-17
- **Tên Use Case:** Import custom model (Tích hợp mô hình tùy chỉnh theo kiến trúc Plugin)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `ModelPluginRegistrationService`, `ModelPluginValidator` (Static AST + Dynamic Dry-Run), `IModelRepository`, `IFileStorage`
- **Mô tả:** Cho phép Data Scientist tích hợp thuật toán học máy/học sâu tùy chỉnh (Bring-Your-Own-Algorithm) vào hệ thống bằng cách tải lên tệp nén `.zip` hoặc nhập đường dẫn thư mục/tệp `.zip` trên máy trạm (`model_artifact_path`), kèm cấu hình `manifest_override` tùy chọn. Hệ thống tự động kiểm định an toàn mã nguồn qua 2 giai đoạn trước khi lưu trữ và đăng ký vào Model Registry.
- **Tiền điều kiện:**
	1. Người dùng đang truy cập một Dự án (`Active Project`).
	2. Gói mã nguồn plugin chứa tệp `main.py` định nghĩa đủ 2 hàm giao tiếp chuẩn `run_training(...)` và `run_inference(...)` theo hợp đồng Plugin (`docs/features/detection/training/model_plugin/design.md`).
- **Hậu điều kiện:**
	- *Thành công:* Gói mã nguồn được đóng gói chuẩn hóa thành `models/{model_id}/plugin_source.zip` trên `IFileStorage`; bản ghi `Model` mới được tạo trong cơ sở dữ liệu với `execution_type = 'SCRIPT'`, gắn `project_id` hiện tại và sẵn sàng để huấn luyện tại `SUC-08`.
	- *Thất bại:* Không lưu tệp lên `IFileStorage` và không tạo bản ghi `Model`; danh sách lỗi kiểm định chi tiết được trả về cho người dùng.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút **“+ Import Custom Model”** trên màn hình Model Hub (`/models`) hoặc trong Training Wizard (`/models/train`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist nhấn nút **+ Import Custom Model**.
2. Hệ thống hiển thị hộp thoại **Import Custom Model Plugin Modal** cho phép chọn 1 trong 2 phương thức cung cấp mã nguồn:
	- **Phương thức 1 — Upload `.zip` Archive:** Kéo thả hoặc chọn tệp `.zip` từ trình duyệt (tối đa `10 MB`, chứa `main.py` và tùy chọn `plugin_manifest.json`).
	- **Phương thức 2 — Local Path (`model_artifact_path`):** Nhập hoặc duyệt chọn đường dẫn tuyệt đối tới thư mục plugin hoặc tệp `.zip` trên máy cục bộ.
3. (Tùy chọn) Data Scientist bật mục **Override / Provide Plugin Manifest** để khai báo hoặc ghi đè siêu dữ liệu nếu trong gói chưa có `plugin_manifest.json`:
	- Định danh kỹ thuật (`model_name`) và Tên hiển thị (`display_name`).
	- Framework (`scikit-learn`, `xgboost`, `lightgbm`, `pytorch`, `pyg`, `onnx`), cấu trúc dữ liệu (`data_modality`: `tabular`, `sequence`, `matrix_2d`, `graph`) và định dạng tệp đầu vào (`data_format`: `parquet` hoặc `csv`).
	- Bộ siêu tham số mặc định (`default_hyperparameters` dạng JSON) và lược đồ siêu tham số (`hyperparameter_schema` dạng JSON).
4. Data Scientist nhấn nút **Validate & Register Plugin**.
5. Hệ thống gửi yêu cầu tới máy chủ (`POST /api/v1/training/models/plugins/upload` đối với tệp `.zip` tải lên, hoặc `POST /api/v1/training/models/plugins` đối với đường dẫn `model_artifact_path`).
6. Hệ thống thực thi quy trình kiểm định 2 giai đoạn (`ModelPluginValidator`):
	- **Cổng 1 — Kiểm tra tĩnh (Static AST Check):** Quét cây cú pháp Python để xác nhận sự tồn tại và chữ ký của `run_training(train_file, test_file, artifact_dir, target_column, hyperparameters)` và `run_inference(input_file, artifact_dir)`, đồng thời chặn các thư viện/hàm hệ thống nguy hiểm (`subprocess`, `socket`, `requests`, `eval`, `exec`,...).
	- **Cổng 2 — Kiểm tra động (Dynamic Dry-Run Smoke Test):** Tự động sinh tập dữ liệu giả lập chuẩn `FEATURE_ENGINEERED`, tiêm `_usfds_runner.py` để chạy thử liên hoàn `run_training` (kiểm tra sinh tệp trọng số mô hình và `preprocessor.joblib`) và `run_inference` (kiểm tra vector xác suất đầu ra khớp kích thước dòng, không chứa `NaN`/`Inf` và nằm trong đoạn `[0.0, 1.0]`).
7. Khi vượt qua cả 2 cổng kiểm định, hệ thống đóng gói mã nguồn cùng `plugin_manifest.json` thành `models/{model_id}/plugin_source.zip` lưu vào `IFileStorage` và lưu thực thể `Model` (`execution_type = ExecutionType.SCRIPT`) vào Model Registry.
8. Hệ thống trả về thông tin mô hình vừa đăng ký (`201 Created`), đóng hộp thoại và cập nhật ngay danh sách mô hình trên giao diện.

### Luồng ngoại lệ (Exception Flows)

- **6a. Vi phạm cấu trúc gói hoặc vi phạm an toàn mã nguồn (Static AST Check Failed — `400 Bad Request`):**
	- Nếu gói thiếu `main.py`, thiếu hàm `run_training` / `run_inference`, vượt quá `10 MB`, hoặc chứa câu lệnh `import` / hàm bị cấm, hệ thống từ chối đăng ký và hiển thị danh sách lỗi cụ thể trên hộp thoại.
- **6b. Chạy thử nghiệm thất bại (Dynamic Dry-Run Failed — `400 Bad Request`):**
	- Nếu quá trình chạy thử `run_training` hoặc `run_inference` phát sinh ngoại lệ Python, không sinh tệp trọng số trong `artifact_dir`, hoặc trả về xác suất ngoài khoảng `[0.0, 1.0]`, hệ thống hiển thị toàn bộ thông báo lỗi (`validation_result.errors`) để Data Scientist sửa mã nguồn và tải lại.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-09 (2-Stage Plugin Validation):** Mọi mô hình tùy chỉnh (`SCRIPT`) bắt buộc phải vượt qua cả kiểm tra tĩnh AST và chạy thử động (Dry-Run Train + Inference) trên dữ liệu giả lập trước khi được phép lưu vào Model Registry.
- **BR-DT-10 (Model-Owned Normalization Contract):** Mã nguồn plugin tự chịu trách nhiệm biến đổi đặc trưng đầu vào và lưu bộ biến đổi (`preprocessor.joblib` hoặc tương đương) cùng trọng số mô hình vào `artifact_dir` để đảm bảo tính nhất quán khi suy diễn (`SUC-15`).
