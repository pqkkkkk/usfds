# Đặc tả use case hệ thống phân hệ Detection
# 0. Tài liệu liên quan

[Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21) 

# 1. Sơ đồ

# 2. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho phân hệ Detection trong FDS.

Mục đích: Mục đích: Xây dựng, quản lý mô hình học máy, động cơ tập luật và thực thi việc chấm điểm rủi ro cho dữ liệu giao dịch.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-08** | **Start model training** | Data Scientist | Chọn thuật toán (XGBoost, Random Forest, GNN,…), cấu hình siêu tham số và chạy huấn luyện mẻ. | High |
| **SUC-09** | **View model training result** | Data Scientist | Xem các chỉ số đánh giá (ROC-AUC, PR-AUC, F1, Confusion Matrix) và giải thích mô hình (SHAP/Feature Importance). | High |
| **SUC-10** | **Activate model** | Data Scientist | Đưa phiên bản mô hình được chọn vào trạng thái hoạt động (Active) để có thể sử dụng nó cho SUC-15 | High |
| **SUC-11** | **Create rule** | Data Scientist | Soạn thảo các điều kiện logic phát hiện gian lận (kết hợp các đặc trưng và ngưỡng giá trị). | High |
| **SUC-12** | **Test rule** | Data Scientist | Chạy thử nghiệm (dry-run/backtest) tập luật trên tập dữ liệu lịch sử để đánh giá độ chính xác và tỷ lệ báo động giả. | High |
| **SUC-13** | **Get recommended rules** | Data Scientist | Nhận các quy tắc được hệ thống/AI gợi ý tự động dựa trên cây quyết định hoặc mẫu bất thường mới. | Low |
| **SUC-14** | **Activate rule** | Data Scientist | Đưa rule vào trạng thái hoạt động (Active) để có thể sử dụng nó cho SUC-15 | High |
| **SUC-15** | **Start detection job** | Data Scientist, Fraud Analyst | Khởi chạy tác vụ chấm điểm mẻ trên tập giao dịch cần rà soát bằng cách kết hợp Mô hình AI và Rule Engine. | High |
| **SUC-16** | **View detection result** | Fraud Analyst, Data Scientist | Xem danh sách kết quả phân loại, điểm số rủi ro, và chuyển tiếp các giao dịch đáng ngờ sang module Investigation để tạo Case. | High |
| **SUC-17** | **Import custom model** | Data Scientist | Cho phép người dùng upload code huấn luyện mô hình để tự động tích hợp vào hệ thống | High |

# 3. Chi tiết

Phần này đặc tả chi tiết 9 Use Case thuộc phân hệ **Detection** (`SUC-08` đến `SUC-16`).

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

### Luồng rẽ nhánh (Alternative Flows)
- 

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