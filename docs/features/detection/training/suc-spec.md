# Đặc tả use case hệ thống phân hệ Detection - Training
# 0. Tài liệu liên quan

[Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)

# 1. Tóm tắt
Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng training trong phân hệ Detection trong FDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-08** | **Start model training** | Data Scientist | Chọn thuật toán (XGBoost, Random Forest, GNN,…), cấu hình siêu tham số và chạy huấn luyện mẻ. | High |
| **SUC-09** | **View model training result** | Data Scientist | Xem các chỉ số đánh giá (ROC-AUC, PR-AUC, F1, Confusion Matrix) và giải thích mô hình (SHAP/Feature Importance). | High |
| **SUC-10** | **Activate model** | Data Scientist | Đưa phiên bản mô hình được chọn vào trạng thái hoạt động (Active) để có thể sử dụng nó cho SUC-15 | High |
| **SUC-17** | **Import custom model** | Data Scientist | Cho phép người dùng upload code huấn luyện mô hình để tự động tích hợp vào hệ thống | High |

# 2. Chi tiết

## SUC-08: Start model training (Khởi chạy huấn luyện mô hình)

### Thông tin chung

- **Mã Use Case:** SUC-08
- **Tên Use Case:** Start model training (Khởi chạy huấn luyện mô hình)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** Compute Engine / Training Worker (`TrainingRunExecutor`), Hệ thống lưu trữ (`IFileStorage` / Object Storage)
- **Mô tả:** Cho phép Data Scientist lựa chọn tập dữ liệu đã làm giàu đặc trưng, chọn thuật toán học máy hoặc học sâu (XGBoost, Random Forest, MLP, LSTM, 2D-CNN, GNN,…), cấu hình chiến lược chuẩn hóa đặc thù theo mô hình cùng bộ siêu tham số (Hyperparameters) và khởi chạy tiến trình huấn luyện theo mẻ trong nền.
- **Tiền điều kiện:**
    1. Người dùng đã đăng nhập hệ thống với vai trò `Data Scientist` và truy cập vào một Dự án (Project) cụ thể.
    2. Trong dự án đã có ít nhất một `DatasetArtifact` đạt trạng thái `FEATURE_ENGINEERED` (từ `SUC-05`) hoặc `PRE_PROCESSED`.
- **Hậu điều kiện:**
    - *Thành công:* Bản ghi `training_runs` được cập nhật trạng thái `succeeded` kèm bộ chỉ số đánh giá (`accuracy`, `precision_score`, `recall_score`, `f1_score`, `loss`, `custom_metrics`); liên kết dữ liệu huấn luyện được ghi nhận vào bảng `run_datasets`; tệp trọng số mô hình và pipeline biến đổi tương ứng được lưu trữ bất biến trên Object Storage kèm mã băm `checksum_sha256`; một phiên bản mô hình mới (`model_versions`) được tự động cấp phát số hiệu `semver` và đăng ký vào Model Registry ở trạng thái `registered`.
    - *Thất bại:* Bản ghi `training_runs` chuyển sang trạng thái `failed` kèm thông tin lỗi (`error_message`); không sinh bản ghi `model_versions` mới.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Start Model Training” tại phân hệ Detection hoặc nhấn “Send to Model Training” trực tiếp từ kết quả làm giàu dữ liệu (`SUC-05`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist mở giao diện **Start Model Training** trong phân hệ **Detection**.
2. Hệ thống tải danh sách các danh mục mô hình (`models`) thuộc dự án và danh sách các `DatasetArtifact` hợp lệ ở trạng thái `FEATURE_ENGINEERED` hoặc `PRE_PROCESSED`.
3. Data Scientist cấu hình thông tin huấn luyện (`TrainingConfig`) (*Review: đây là các bước cấu hình phức tạp, sẽ bổ sung sau như advanced setting nếu cần thiết, hiện tại không cần, hệ thống tự động chọn config phù hợp*)
    - **Chọn Mô hình mục tiêu (`model_id`):** Chọn mô hình sẵn có trong Model Catalog hoặc khởi tạo định danh mô hình mới.
    - **Chọn Tập dữ liệu đầu vào (`train_artifact_id`):** Chọn phiên bản `DatasetArtifact` chứa cặp tệp `train_enriched.parquet` và `test_enriched.parquet`.
    - **Cấu hình chuẩn hóa đặc thù mô hình (Model-Specific Normalization) (*review: chưa cần hiển thị để tránh phức tạp*)**
        - Nếu chọn *Tabular ML*: Cấu hình bộ biến đổi bảng phẳng (`StandardScaler`, `RobustScaler`, `MinMaxScaler`, `Log1pTransformer`), mã hóa biến phân loại (`OneHotEncoder`, `BinaryEncoder`), giảm chiều (`PCA`, `SelectKBest`), và cân bằng dữ liệu tập Train (`SMOTE`, `ADASYN`, `RUS`, `TomekLinks`, `SMOTEENN`).
        - Nếu chọn *Sequential / Graph DL*: Cấu hình độ dài chuỗi cửa sổ thời gian (`sequence_length` cho LSTM/GRU), kích thước ma trận không-thời gian (cho 2D-CNN) hoặc cấu hình cạnh liên kết thực thể (`user_id`, `card_id`, `merchant_id` cho GNN).
    - **Cấu hình Siêu tham số (`hyperparameters`):** Nhập hoặc giữ nguyên giá trị mặc định từ `default_hyperparameters` (ví dụ: `n_estimators`, `max_depth`, `learning_rate`, `scale_pos_weight`, `epochs`, `batch_size`).
4. Data Scientist nhấn nút **Start Training**.
5. Hệ thống thực thi huấn luyện mô hình
6. Hệ thống thông báo hoàn tất huấn luyện và cho phép người dùng điều hướng sang xem kết quả chi tiết (`SUC-09`).

### Luồng rẽ nhánh (Alternative Flows) (*Review: Là các chức năng nâng cao, sẽ cài đặt sau*)

- **3a. Sao chép cấu hình từ lần chạy trước (Clone Training Run):**
    - Tại bước 3, Data Scientist có thể chọn một `TrainingRun` trong lịch sử và nhấn “Clone Configuration”. Hệ thống tự động điền toàn bộ thuật toán, dataset và `hyperparameters` của lần chạy đó để người dùng tinh chỉnh nhanh.
- **6a. Huấn luyện mô hình mở rộng dạng Script Plugin (`ScriptPluginTrainer`):**
    - Nếu mô hình có `execution_type = 'script'` hoặc `'git_repo'`, Worker tự động nạp script theo chuẩn giao tiếp CLI (`--input` và `--output`), thực thi trong tiến trình con cô lập và thu thập tệp `/output/metrics.json` cùng trọng số trong `/output/model/`.

### Luồng ngoại lệ (Exception Flows)

- **5a. Tập dữ liệu thiếu nhãn mục tiêu đối với thuật toán học có giám sát:**
    - Tại bước 5, nếu Data Scientist chọn thuật toán Supervised (như `XGBoost`, `Random Forest`, `LSTM`, `GNN`) nhưng `DatasetArtifact` không có cột nhãn `label`, hệ thống từ chối khởi chạy và báo lỗi: *“Thuật toán có giám sát yêu cầu tập dữ liệu phải có cột nhãn (label). Vui lòng chọn tập dữ liệu khác hoặc sử dụng thuật toán không giám sát (Isolation Forest, Autoencoder).”*
- **6b. Lỗi quá tải bộ nhớ hoặc ngoại lệ trong quá trình huấn luyện (Out-of-Memory / Runtime Error):**
    - Tại bước 6, nếu quá trình huấn luyện gặp lỗi thiếu RAM/VRAM hoặc không hội tụ, `TrainingRunExecutor` bắt ngoại lệ, dọn dẹp thư mục tạm, trả về `is_success = False` kèm `error_message`. Hệ thống cập nhật `training_runs.status = 'failed'` và hiển thị nhật ký lỗi cho Data Scientist.
- **6c. Hủy tác vụ đang chạy (Cancel Training Run):**
    - Khi `training_runs` đang ở trạng thái `queued` hoặc `running`, nếu Data Scientist nhấn nút “Cancel Run”, hệ thống ngắt tiến trình Worker và cập nhật trạng thái bản ghi thành `cancelled`.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-03:** Mỗi phiên bản mô hình (`model_versions`) sau khi tạo là bất biến (immutable), bắt buộc gắn với mã kiểm tra toàn vẹn `checksum_sha256` (64 ký tự) và không được trùng lặp số hiệu `semver` trong cùng một `model_id`.

## SUC-09: View model training result (Xem kết quả huấn luyện mô hình)

### Thông tin chung

- **Mã Use Case:** SUC-09
- **Tên Use Case:** View model training result (Xem kết quả huấn luyện mô hình)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist xem báo cáo đánh giá hiệu năng chi tiết của mô hình sau khi huấn luyện (ROC-AUC, PR-AUC, Precision, Recall, F1-Score, Confusion Matrix), mô phỏng điều chỉnh ngưỡng cắt điểm rủi ro (Threshold Tuning) và xem giải thích mô hình (Explainable AI qua SHAP / Feature Importance).
- **Tiền điều kiện:** Đã có ít nhất một lần chạy huấn luyện (`training_runs`) hoàn tất ở trạng thái `succeeded` (hoặc `failed` để xem log lỗi).
- **Hậu điều kiện:** Báo cáo hiệu năng, biểu đồ đánh giá và mức độ đóng góp đặc trưng được hiển thị trực quan; người dùng có thể chọn phiên bản mô hình phù hợp để triển khai (`SUC-10`).
- **Sự kiện kích hoạt (Trigger):** Data Scientist chọn một lần chạy từ danh sách `Training Runs` hoặc nhấn “View Result” ngay sau khi `SUC-08` hoàn tất.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist truy cập vào mục **Model Training Results** và chọn một bản ghi `TrainingRun` (hoặc `ModelVersion` tương ứng).
2. Hệ thống truy xuất thông tin từ bảng `training_runs`, `model_versions`, `run_datasets` và tải dữ liệu biểu đồ đánh giá.
3. Hệ thống hiển thị bảng điều khiển kết quả huấn luyện gồm 4 khu vực chính:
    - **Thông tin định danh & Truy vết (Lineage Metadata):** Tên mô hình, số hiệu `semver`, thuật toán, danh sách `hyperparameter` *(review: tạm thời bỏ việc hiển thị các thông tin hypermeter phức tạp này)*,thời gian thực thi (`duration_seconds`), và liên kết ngược tới `DatasetArtifact` đã dùng để huấn luyện.
    - **Bộ chỉ số hiệu năng cốt lõi (Performance Metrics):**
        - Các chỉ số chuẩn: `Precision`, `Recall`, `F1-Score.`
        - Các chỉ số chuyên biệt cho dữ liệu gian lận mất cân bằng (`custom_metrics`): `ROC-AUC`, `PR-AUC` (Precision-Recall AUC),.
    - **Đồ thị & Mô phỏng ngưỡng quyết định (Interactive Curves & Threshold Simulator):**
        - Biểu đồ đường cong `ROC Curve` và `Precision-Recall Curve`.
        - Ma trận nhầm lẫn (`Confusion Matrix`) hiển thị số lượng giao dịch `TP` (bắt đúng gian lận), `FP` (báo động giả), `TN` (hợp lệ đúng), `FN` (bỏ sót gian lận).
        - Thanh trượt **Decision Threshold Slider** (từ `0.00` đến `1.00`): Khi Data Scientist kéo thay đổi ngưỡng cắt điểm gian lận, hệ thống tính toán lại tức thời ma trận nhầm lẫn cùng tỷ lệ `Precision` / `Recall` để hỗ trợ chọn ngưỡng vận hành tối ưu.
    - **Giải thích mô hình (Explainable AI - SHAP / Feature Importance):**
        - Hiển thị bảng xếp hạng và biểu đồ `Top-K Feature Importance` / `SHAP Summary Plot`, chỉ rõ những đặc trưng nghiệp vụ nào (ví dụ: `feature.velocity_1h`, `mapped.amount`, `feature.ratio_to_avg_amount`) đóng góp lớn nhất vào điểm số dự đoán gian lận.
4. Data Scientist phân tích kết quả để đánh giá chất lượng mô hình và có thể nhấn nút **Deploy Model** để chuyển sang `SUC-10`.

### Luồng rẽ nhánh (Alternative Flows)

- **1a. So sánh nhiều phiên bản mô hình (Compare Training Runs):** *(Review: advanced feature, sẽ cài đặt sau)*
    - Data Scientist có thể tích chọn từ 2 đến 4 bản ghi `TrainingRun` để mở chế độ **Side-by-Side Comparison**. Hệ thống hiển thị bảng đối chiếu cấu hình siêu tham số, đồ thị ROC/PR chồng lớp và bảng so sánh các chỉ số (`PR-AUC`, `F1-Score`, `Latency`) để chọn ra mô hình vượt trội nhất.

### Luồng ngoại lệ (Exception Flows)

- **2a. Lần chạy huấn luyện bị thất bại (`status = 'failed'`):**
    - Nếu Data Scientist mở một `TrainingRun` có trạng thái `failed`, hệ thống ẩn các biểu đồ metric và hiển thị khung **Execution Error Log** chứa chi tiết nguyên nhân lỗi (`error_message`), thời điểm dừng và nút **Retry Training** để cấu hình lại.

## SUC-10: Activate model

### Thông tin chung

- **Mã Use Case:** SUC-10
- **Tên Use Case:** Activate model
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist đưa một phiên bản mô hình (`ModelVersion`) đã huấn luyện vào trạng thái hoạt động chính thức (`active` deployment) để sẵn sàng thực hiện chấm điểm rủi ro gian lận cho các tác vụ phát hiện.
- **Tiền điều kiện:**
    1. Phiên bản mô hình (`model_versions`) được chọn đang ở trạng thái `registered` hoặc `validated` và có tệp artifact hợp lệ trên lưu trữ.
- **Hậu điều kiện:**
    - *Thành công:* Bản ghi  `model_versions` được cập nhật với trạng thái `active`
    - *Thất bại:* Không thay đổi phiên bản mô hình đang hoạt động hiện tại.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Activate Model” tại trang chi tiết kết quả huấn luyện (`SUC-09`) hoặc từ danh mục Model Registry.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn một phiên bản mô hình (`version_id`, `semver`) trong Model Registry và nhấn nút **Deploy Model**.
2. Data Scientist xác nhận thông tin và nhấn **Confirm Activate**.
3. Hệ thống kiểm tra tính toàn vẹn của tệp mô hình tại `artifact_uri` bằng cách đối chiếu mã băm `checksum_sha256` với bản ghi trong bảng `model_versions`
4. Hệ thống nạp thử (smoke test) tệp mô hình và pipeline đi kèm để đảm bảo tương thích với môi trường runtime hiện tại.
5. Hệ thống cập nhật trạng thái bản ghi `model_versions` thành `active`
6. Hệ thống thông báo triển khai mô hình thành công.

### Luồng rẽ nhánh (Alternative Flows)

- 

### Luồng ngoại lệ (Exception Flows)

- **4a. Tệp artifact bị hỏng hoặc sai lệch Checksum:**
    - Tại bước 4, nếu không tìm thấy tệp tại `artifact_uri` hoặc mã băm SHA-256 tính toán lại không khớp với `checksum_sha256` đã đăng ký, hệ thống chặn quá trình triển khai và cảnh báo: *“Kiểm tra tính toàn vẹn thất bại: Artifact của phiên bản mô hình không tồn tại hoặc đã bị thay đổi ngoài luồng.”*
- **5a. Lỗi không tương thích thư viện khi nạp mô hình:**
    - Tại bước 5, nếu quá trình deserialize mô hình thất bại, hệ thống giữ nguyên deployment cũ đang chạy và báo lỗi chi tiết cho người dùng.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-04:** Hệ thống áp dụng ràng buộc toàn vẹn `ON DELETE RESTRICT` từ bảng `deployments` tới `model_versions` — nghiêm cấm xóa bất kỳ phiên bản mô hình nào đang hoặc đã từng được tham chiếu trong lịch sử triển khai vận hành.

## SUC-17: Import custom model