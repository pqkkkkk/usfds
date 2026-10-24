# Phân tích khoảng trống (Gap Analysis) - Phân hệ Detection

> **Phân hệ:** Detection (Phát hiện gian lận)  
> **Mục tiêu:** Xây dựng, quản lý mô hình học máy, động cơ tập luật và thực thi việc chấm điểm rủi ro cho dữ liệu giao dịch.

---
## Phân tích ngày 10-10-2026
### 1. `usfds-core`

Phân hệ Detection gồm **9 System Use Cases (SUC-08 đến SUC-16)**:
- **Đã đáp ứng đầy đủ ở tầng Core ML (4 SUC):** `SUC-08`, `SUC-09`, `SUC-15` (phần AI/ML), `SUC-16`.
- **Đã đáp ứng một phần / Có sẵn mô hình dữ liệu & chu trình xử lý (1 SUC):** `SUC-10` (Deployment lifecycle & ModelVersion registration).
- **Chưa cài đặt (4 SUC):** `SUC-11`, `SUC-12`, `SUC-13`, `SUC-14` (Toàn bộ các use case thuộc động cơ tập luật **Rule Engine**).

#### 1.1. Phân hệ Rule Engine (`SUC-11` đến `SUC-14`):
* Hiện tại `usfds-core` tập trung sâu vào toàn bộ chu trình ML Pipeline (từ Data Cleansing, Split, Preprocessing đến Model Training, Inference và Investigation).
* Chưa có cấu trúc dữ liệu cho Rule (Rule Definition AST), bộ thông dịch logic điều kiện (ví dụ: `amount > 5000 AND tx_freq_last_1h > 3`), và động cơ backtest trên tệp `enriched.parquet`.

#### 1.2. Động cơ chấm điểm tích hợp Hybrid Detection (`SUC-15`):
* `InferenceService` hiện tại đang vận hành thuần thục mô hình ML (Machine Learning Scoring).
* Theo đặc tả hệ thống FDS chuẩn, động cơ chấm điểm cần phối hợp:
  1. Chạy mô hình ML cho ra xác suất rủi ro `risk_score`.
  2. Đồng thời đánh giá danh sách tập luật `Active Ruleset`.
  3. Tổng hợp quyết định cuối cùng (ví dụ: Vi phạm Hard Rule blacklist $\rightarrow$ Từ chối giao dịch ngay lập tức; nếu không thì dùng ngưỡng `decision_threshold` của mô hình).

### 2. `usfds-server`

### 3. `usfds-web`


### 4. Danh sách các khoảng trống cần bổ sung (Action Items)

1. **Xây dựng module `Rule Engine` (`usfds_core.services.rules`):**
   * **Rule Domain Entity & Schema (`SUC-11`):** Định nghĩa cấu trúc luật (trường so sánh, toán tử so sánh, ngưỡng, điểm phạt/hành động).
   * **Rule Evaluator & Backtester (`SUC-12`):** Thực thi đánh giá điều kiện luật trên DataFrame hoặc từng sự kiện giao dịch; tính toán precision, trigger rate, false positive rate.
   * **Rule Recommendation (`SUC-13`):** Cài đặt giải thuật duyệt qua các nút rẽ nhánh của cây quyết định (`DecisionTreeClassifier` hoặc `RandomForest`) để tự động sinh các điều kiện rủi ro cao.
   * **Rule Management & Deployment (`SUC-14`):** Quản lý tập luật đang kích hoạt (Active Ruleset).
2. **Nâng cấp `InferenceService` thành Hybrid Detection (`SUC-15`):**
   * Kết hợp kết quả từ `ModelScorer` và `RuleEvaluator` trong cả 2 chế độ `batch_inference()` và `online_inference()`.
3. **Bổ sung các API Endpoints tại `usfds-server`:**
   * Endpoint kích hoạt triển khai mô hình (`POST /deployments/{id}/activate`) (`SUC-10`).
   * Endpoints quản lý và chạy thử nghiệm tập luật (`SUC-11` - `SUC-14`).

