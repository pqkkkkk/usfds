<!-- [26-10-25] Approved update of Detection - Rule Management System Use Case Specification (SUC-11, SUC-12, SUC-13, SUC-14, SUC-18) -->
# Đặc tả use case hệ thống phân hệ Detection — Rule Management

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Stage: 3. Design
Updated: 25/10/2026 `[26-10-25]`

# 0. Tài liệu liên quan

- [Xác định các yêu cầu tự động hóa cho FDS](https://app.notion.com/p/X-c-nh-c-c-y-u-c-u-t-ng-h-a-cho-FDS-3e7b99c6a950801db925e4077d521232?pvs=21)
- `docs/features/project_management/design.md` (Thiết kế Kiến trúc Quản lý Dự án & Ràng buộc Schema `BR-PM-04`, `BR-PM-05`)
- `docs/features/detection/user-flow-and-ui-design.md` (Thiết kế User Flow & UI/UX: Module Detection)

# 1. Tóm tắt

Dưới đây là danh mục use case hệ thống (SUC) cho các chức năng quản lý tập luật nghiệp vụ (**Rule Engine**) trong phân hệ **Detection** của hệ thống USFDS.

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-18** | **View rules** | Data Scientist | Xem danh mục các quy tắc nghiệp vụ (`Rule`) trong dự án, lọc theo trạng thái (`ACTIVE`, `DRAFT`, `INACTIVE`), xem lịch sử các phiên bản (`RuleVersion`) và xóa quy tắc. | High |
| **SUC-11** | **Create rule** | Data Scientist | Soạn thảo mới hoặc cập nhật quy tắc phát hiện gian lận theo cây điều kiện `JsonLogic` dựa trên `project.raw_schema`, thiết lập hành động (`ALLOW`, `REVIEW`, `REJECT`) và tự động quản lý phiên bản bất biến (`RuleVersion`). | High |
| **SUC-12** | **Test rule** | Data Scientist | Chạy thử nghiệm (`Dry-run` / `Backtest`) quy tắc trên tập dữ liệu lịch sử (`DatasetArtifact`) hoặc kiểm thử trực tiếp trên một ngữ cảnh giao dịch đơn lẻ để đánh giá tỷ lệ kích hoạt, độ chính xác (`Precision`, `Recall`, `FPR`) và thời gian thực thi. | High |
| **SUC-14** | **Activate rule** | Data Scientist | Chuyển trạng thái quy tắc sang hoạt động chính thức (`ACTIVE`) hoặc tạm ngưng (`INACTIVE`) sau khi kiểm tra ràng buộc `project.raw_schema` (`BR-PM-04`, `BR-PM-05`) để phục vụ `SUC-15`. | High |
| **SUC-13** | **Get recommended rules** | Data Scientist | Nhận các quy tắc được hệ thống/AI gợi ý tự động dựa trên cây quyết định giải thích được (`Surrogate Decision Tree`). *(Chức năng nâng cao — sẽ bổ sung sau)* | Low |

---

# 2. Chi tiết đặc tả Use Case

## SUC-18: View rules (Xem danh sách quy tắc và lịch sử phiên bản)

### Thông tin chung

- **Mã Use Case:** SUC-18
- **Tên Use Case:** View rules (Xem danh sách quy tắc và lịch sử phiên bản)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `RuleManager`, `IRuleRepository`, `IRuleVersionRepository`
- **Mô tả:** Cho phép Data Scientist theo dõi toàn bộ danh mục các quy tắc nghiệp vụ (`Rule`) thuộc dự án hiện tại, tìm kiếm theo mã/tên/mô tả, lọc theo trạng thái (`ALL`, `ACTIVE`, `DRAFT`, `INACTIVE`), tra cứu lịch sử kiểm toán các phiên bản bất biến (`RuleVersion`), khôi phục phiên bản cũ vào trình soạn thảo, hoặc xóa quy tắc không còn sử dụng.
- **Tiền điều kiện:** Người dùng đã chọn một Dự án (`Active Project`) trên hệ thống.
- **Hậu điều kiện:** Danh sách quy tắc cùng phiên bản hiện hành (`current_version`) và lịch sử các phiên bản (`RuleVersion`) được hiển thị chính xác theo dự án đang chọn.
- **Sự kiện kích hoạt (Trigger):** Data Scientist điều hướng tới mục **Rules** (`/rules`) trên thanh điều hướng bên trái.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist truy cập màn hình **Rule Catalog** (`/rules`).
2. Hệ thống gọi `GET /api/v1/rules?project_id={project_id}` để lấy danh sách các quy tắc thuộc dự án kèm thông tin phiên bản hiện hành (`current_version`).
3. Hệ thống hiển thị thanh công cụ tìm kiếm, bộ lọc trạng thái (`ALL`, `ACTIVE`, `DRAFT`, `INACTIVE`) kèm số lượng quy tắc tương ứng, và bảng danh sách quy tắc gồm các cột:
	- Mã định danh (`rule_code`), Tên quy tắc (`name`) và Mô tả (`description`).
	- Hành động quyết định của phiên bản hiện tại (`action`: `ALLOW`, `REVIEW`, `REJECT`).
	- Số hiệu phiên bản hiện hành (`v{version_number}`).
	- Trạng thái hoạt động (`status`: `ACTIVE`, `DRAFT`, `INACTIVE`).
	- Các thao tác nhanh: **Dry Run** (`/rules/{rule_id}/step-dryrun`), **Edit in Studio** (`/rules/{rule_id}/step-builder`), **View Versions**, và **Delete**.
4. Khi Data Scientist nhấn vào nút phiên bản `v{version_number}` (hoặc nút **Versions** trong Rule Studio):
	- Hệ thống gọi `GET /api/v1/rules/{rule_id}/versions`.
	- Hệ thống hiển thị hộp thoại **Version History & Audit Trail Modal** gồm dòng thời gian các phiên bản (`version_number`, `change_summary`, `created_by`, `created_at`, nhãn `Current Live`) ở cột trái và trình xem cấu trúc `JsonLogic AST` cùng `action` ở cột phải.
	- Data Scientist có thể nhấn **Load Into Studio** trên bất kỳ phiên bản lịch sử nào để nạp lại cây điều kiện và hành động của phiên bản đó vào trình soạn thảo.

### Luồng rẽ nhánh (Alternative Flows)

- **3a. Xóa quy tắc nghiệp vụ (`DELETE /api/v1/rules/{rule_id}`):**
	- Khi Data Scientist nhấn nút **Xóa Rule** (`Trash`) trên một dòng quy tắc và xác nhận hộp thoại, hệ thống gọi `DELETE /api/v1/rules/{rule_id}`, xóa bản ghi `Rule` cùng các `RuleVersion` liên quan, đồng thời cập nhật lại bộ đếm tài nguyên của dự án (hỗ trợ mở khóa `raw_schema` nếu dự án không còn tài nguyên phụ thuộc theo `BR-PM-03`).

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-06 (Cross-Project Isolation):** Danh sách quy tắc được cô lập chặt chẽ theo `project_id` đang làm việc.

---

## SUC-11: Create rule (Tạo và cập nhật quy tắc phát hiện gian lận)

### Thông tin chung

- **Mã Use Case:** SUC-11
- **Tên Use Case:** Create rule (Tạo và cập nhật quy tắc phát hiện gian lận)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `RuleManager`, `ProjectSchemaValidator`, `IRuleRepository`, `IRuleVersionRepository`
- **Mô tả:** Cho phép Data Scientist khởi tạo mới hoặc chỉnh sửa quy tắc phát hiện gian lận thông qua trình dựng quy tắc trực quan (**Rule Studio Builder**). Biểu thức điều kiện được biên dịch sang chuẩn cây cú pháp **`JsonLogic`** tham chiếu trực tiếp tới các cột trong `project.raw_schema` (và/hoặc đặc trưng `enriched.<field>`). Mọi thay đổi đối với logic điều kiện (`condition`) hoặc hành động (`action`) khi cập nhật quy tắc đều tự động sinh một bản ghi `RuleVersion` bất biến mới (`version_number + 1`).
- **Tiền điều kiện:** Người dùng đang làm việc trong một Dự án (`Active Project`) có trạng thái `ACTIVE` (không phải `ARCHIVED`).
- **Hậu điều kiện:**
	- *Tạo mới thành công:* Bản ghi `Rule` mới và `RuleVersion` đầu tiên (`version_number = 1`) được lưu vào cơ sở dữ liệu, `current_version_id` trỏ tới phiên bản vừa tạo.
	- *Cập nhật thành công:* Nếu thay đổi `condition` hoặc `action`, hệ thống tạo `RuleVersion` mới (`version_number = N + 1`) và cập nhật `current_version_id`; nếu chỉ sửa `name` hoặc `description`, hệ thống cập nhật trực tiếp bản ghi `Rule`.
	- *Thất bại:* Không lưu thay đổi vào cơ sở dữ liệu và hiển thị thông báo lỗi kiểm định chi tiết.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút **“+ New Business Rule”** (`/rules/new`) hoặc chọn chỉnh sửa một quy tắc hiện có (`/rules/{rule_id}/step-builder`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist mở giao diện **Rule Studio Builder** (`/rules/new` hoặc `/rules/{rule_id}/step-builder`).
2. Hệ thống kiểm tra trạng thái `raw_schema` của Dự án hiện tại (`currentProject.raw_schema`):
	- Nếu dự án đã khóa `raw_schema` (`is_schema_locked = true`), hệ thống nạp danh sách các cột chuẩn từ `project.raw_schema.columns` kèm kiểu dữ liệu logic (`NUMERIC`, `STRING`, `BOOLEAN`, `DATETIME`) vào bộ chọn trường dữ liệu của trình dựng quy tắc.
	- Nếu dự án chưa có `raw_schema` (`is_schema_locked = false`), hệ thống hiển thị cảnh báo: quy tắc chỉ có thể lưu ở trạng thái `DRAFT` hoặc `INACTIVE` cho tới khi tải lên Dataset đầu tiên (`BR-PM-04`).
3. Data Scientist nhập hoặc chỉnh sửa thông tin định danh và trạng thái của quy tắc:
	- Mã quy tắc duy nhất trong dự án (`rule_code`, ví dụ: `R-022`, bắt buộc khi tạo mới).
	- Tên quy tắc (`name`) và Trạng thái (`status`: `DRAFT`, `ACTIVE`, `INACTIVE`).
4. Data Scientist thiết lập cây điều kiện logic (`RuleGroup` $\rightarrow$ biên dịch sang `JsonLogic` AST):
	- Chọn toán tử kết hợp nhóm (`ALL of` $\rightarrow$ `{"and": [...]}`, `ANY of` $\rightarrow$ `{"or": [...]}`, `NONE of` $\rightarrow$ `{"!": {"or": [...]}}`), hỗ trợ nhóm lồng nhau tối đa 3 cấp.
	- Thêm các mệnh đề so sánh đơn (`RuleClause`) gồm:
		- Trường dữ liệu (`field` lấy từ `project.raw_schema.columns` hoặc nhập tên trường tùy chỉnh).
		- Toán tử so sánh (`ComparisonOperator`: `>`, `>=`, `<`, `<=`, `==`, `!=`, `in`, `not_in`, `regex`).
		- Giá trị ngưỡng (`value`).
	- Khung **Live Preview** bên phải tự động hiển thị diễn giải ngôn ngữ tự nhiên (**Natural Language Interpretation**) và mã `JsonLogic AST` thời gian thực.
5. Data Scientist cấu hình kết quả đầu ra tại mục **Execution Outcome & Action (THEN)**:
	- Chọn Hành động quyết định (`action` thuộc `RuleAction`: `ALLOW` — Chấp nhận, `REVIEW` — Đưa vào hàng đợi duyệt thủ công, `REJECT` — Từ chối giao dịch ngay lập tức).
	- Nhập mô tả nghiệp vụ (`description`) và ghi chú thay đổi phiên bản (`change_summary`).
6. Data Scientist nhấn **Save Draft** (lưu với trạng thái `DRAFT`), **Save Changes** (cập nhật quy tắc), hoặc **Chuyển sang Dry Run**.
7. Hệ thống gọi `POST /api/v1/rules` (nếu tạo mới) hoặc `PUT /api/v1/rules/{rule_id}` (nếu cập nhật).
8. `RuleManager` thực hiện kiểm tra hợp lệ:
	- Kiểm tra tính duy nhất của `(project_id, rule_code)` khi tạo mới (`BR-DT-05`).
	- Kiểm tra ràng buộc `BR-PM-04` (chặn trạng thái `ACTIVE` nếu dự án chưa khóa `raw_schema`).
	- Kiểm tra tĩnh biểu thức `JsonLogic` qua `ProjectSchemaValidator.validate_rule_condition` (`BR-PM-05`): mọi biến `{"var": "<col>"}` (hoặc `raw.<col>`) phải tồn tại trong `project.raw_schema.columns`, và toán tử số học (`>`, `>=`, `<`, `<=`) không được áp dụng sai kiểu lên cột `STRING` hoặc `BOOLEAN`.
9. Hệ thống lưu `Rule` và `RuleVersion`, trả về dữ liệu mới nhất và hiển thị thông báo lưu thành công.

### Luồng ngoại lệ (Exception Flows)

- **8a. Trùng mã quy tắc (`rule_code` — `400 Bad Request`):**
	- Nếu `rule_code` đã tồn tại trong dự án hiện tại, hệ thống trả về lỗi và hiển thị thông báo trên giao diện để người dùng đổi mã khác.
- **8b. Vi phạm `project.raw_schema` hoặc toán tử không tương thích (`BR-PM-04` / `BR-PM-05` — `400 Bad Request`):**
	- Nếu cây điều kiện tham chiếu tới cột không tồn tại trong `project.raw_schema.columns`, dùng toán tử số học cho cột chuỗi/boolean, hoặc kích hoạt `ACTIVE` khi dự án chưa có `raw_schema`, hệ thống chặn thao tác lưu và hiển thị nguyên văn danh sách lỗi kiểm định trên giao diện Rule Studio.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-DT-05 (Project-Scoped Rule Code Uniqueness):** Mã quy tắc (`rule_code`) là duy nhất trong phạm vi một Dự án (`UNIQUE (project_id, rule_code)`).
- **BR-DT-06 (Immutable Rule Versioning):** Mỗi khi `condition` hoặc `action` của một quy tắc được cập nhật, hệ thống bắt buộc tạo một bản ghi `RuleVersion` mới có `version_number` tăng tự động (`N + 1`) thay vì ghi đè phiên bản cũ, đảm bảo khả năng truy vết lịch sử.
- **BR-PM-04 & BR-PM-05 (Schema Governance):** Biểu thức `JsonLogic` của quy tắc được kiểm tra tĩnh đối chiếu với `project.raw_schema` trước khi lưu hoặc kích hoạt.

---

## SUC-12: Test rule (Kiểm thử quy tắc / Dry-run & Backtest)

### Thông tin chung

- **Mã Use Case:** SUC-12
- **Tên Use Case:** Test rule (Kiểm thử quy tắc / Dry-run & Backtest)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `RuleExecutor`, `JsonLogicEvaluator`, `IDatasetArtifactRepository`, `IFileStorage`
- **Mô tả:** Cho phép Data Scientist kiểm thử quy tắc theo 2 chế độ:
	1. **Historical Dataset Backtest (`POST /api/v1/rules/backtest`):** Chạy mô phỏng quy tắc trên toàn bộ một `DatasetArtifact` lịch sử của dự án để đo lường tổng số lượt kích hoạt (`total_hits`, `hit_rate`), các chỉ số hiệu quả phát hiện gian lận (`TP`, `FP`, `TN`, `FN`, `Precision`, `Recall`, `False Positive Rate`, tổng giá trị giao dịch gian lận chặn được `fraud_amount_caught` khi tập dữ liệu có cột nhãn), thời gian thực thi và danh sách các giao dịch khớp điều kiện (`sample_hits`).
	2. **Single-Transaction Evaluation (`POST /api/v1/rules/{rule_id}/evaluate`):** Kiểm thử nhanh quy tắc trên một payload giao dịch JSON đơn lẻ để kiểm tra kết quả kích hoạt (`is_triggered`), lý do (`trigger_reason`) và độ trễ (`execution_time_ms`).
- **Tiền điều kiện:**
	1. Người dùng đang mở một quy tắc trong **Rule Workspace** (`/rules/{rule_id}/step-dryrun`) hoặc đã định nghĩa cây điều kiện `JsonLogic` hợp lệ.
	2. Đối với chế độ Backtest trên tập dữ liệu: trong dự án đã có ít nhất một `DatasetArtifact` (`RAW`, `MAPPED`, hoặc `FEATURE_ENGINEERED`).
- **Hậu điều kiện:** Báo cáo kết quả kiểm thử (các thẻ KPI Telemetry, bảng giao dịch mẫu khớp điều kiện, chi tiết đánh giá từng mệnh đề AST, hoặc kết quả đánh giá giao dịch đơn lẻ) được hiển thị trực quan mà không làm thay đổi dữ liệu vận hành.
- **Sự kiện kích hoạt (Trigger):** Data Scientist chuyển sang bước **Dry Run Simulation** (`step-dryrun`) trong Rule Workspace hoặc nhấn biểu tượng **Play (Dry Run)** từ danh sách quy tắc (`SUC-18`).

### Luồng sự kiện chính (Basic Flow — Chế độ 1: Historical Dataset Backtest)

1. Data Scientist mở màn hình **Dry Run Simulation** (`/rules/{rule_id}/step-dryrun`).
2. Hệ thống tải danh sách các `Dataset` và `DatasetArtifact` thuộc dự án hiện tại (`GET /api/v1/datasets?project_id={project_id}`).
3. Data Scientist chọn `DatasetArtifact` mục tiêu cần chạy kiểm thử, tùy chọn chỉ định tên cột nhãn (`target_column`, mặc định tự động nhận diện `is_fraud`, `label`, `fraud_label`, `target`, `class`) và cột số tiền (`amount_column`), sau đó nhấn **Run Dry Run Simulation**.
4. Hệ thống gửi yêu cầu `POST /api/v1/rules/backtest` kèm `project_id`, `dataset_artifact_id`, và `rule_id` (hoặc biểu thức `condition` + `action` hiện tại trên trình soạn thảo).
5. Hệ thống đọc dữ liệu từ `DatasetArtifact` trên `IFileStorage` (nếu là artifact `FEATURE_ENGINEERED` có `train`/`test`, ưu tiên nạp tập `test` hoặc toàn bộ bảng dữ liệu), thực thi `RuleExecutor.backtest_dataframe` duyệt cây `JsonLogic` trên từng dòng dữ liệu và đo thời gian thực thi.
6. Hệ thống tổng hợp và hiển thị báo cáo kết quả kiểm thử gồm:
	- **6 Thẻ KPI Telemetry:**
		- `Total Rule Hits` & `Hit Rate (%)` trên tổng số giao dịch kiểm thử (`total_transactions`).
		- `Precision` ($\frac{TP}{TP + FP}$) và `Recall` ($\frac{TP}{TP + FN}$) (hiển thị khi tập dữ liệu có cột nhãn thực tế `has_ground_truth = true`).
		- `False Positive Rate (FPR)` ($\frac{FP}{FP + TN}$) kèm số lượng báo động giả (`FP`).
		- `Execution Latency`: Tổng thời gian chạy (`execution_time_ms`) và thời gian trung bình mỗi giao dịch (`avg_execution_time_ms`).
		- `Fraud Prevented`: Tổng giá trị giao dịch gian lận thực tế bị quy tắc bắt trúng (`fraud_amount_caught`, nếu tập dữ liệu có cột số tiền và cột nhãn).
	- **Bảng Sample Hits Inspection Matrix:**
		- Hiển thị danh sách các giao dịch mẫu khớp điều kiện (hỗ trợ lọc theo `All Hits`, `True Positives (TP)`, `False Positives (FP)`).
		- Khi nhấn **Inspect AST** trên một giao dịch, hệ thống mở hộp thoại hiển thị trạng thái đánh giá từng mệnh đề (`matched_clauses`) và toàn bộ ngữ cảnh đặc trưng JSON của giao dịch đó.
7. Nếu kết quả kiểm thử đạt yêu cầu, Data Scientist có thể nhấn **Triển khai & Kích hoạt** (`SUC-14`) ngay trên thanh công cụ để đưa quy tắc vào trạng thái `ACTIVE`.

### Luồng rẽ nhánh (Alternative Flows)

- **3a. Chế độ 2 — Kiểm thử nhanh trên một giao dịch đơn lẻ (Single-Transaction Test):**
	- Data Scientist chuyển sang khu vực/hộp thoại **Single Transaction Evaluator**, nhập hoặc chỉnh sửa payload JSON của một giao dịch (`transaction_id`, `raw_features`, `enriched_features`) — được điền sẵn mẫu từ các cột trong `project.raw_schema` — và nhấn **Evaluate Transaction**.
	- Hệ thống gọi `POST /api/v1/rules/{rule_id}/evaluate`, thực thi `RuleExecutor.evaluate_rule` và hiển thị tức thời trạng thái `TRIGGERED` / `NOT TRIGGERED`, hành động `action`, `trigger_reason`, và thời gian thực thi (`execution_time_ms`).

### Luồng ngoại lệ (Exception Flows)

- **5a. Tập dữ liệu kiểm thử không có cột nhãn (`has_ground_truth = false`):**
	- Nếu `DatasetArtifact` được chọn không chứa cột nhãn gian lận (ví dụ tập dữ liệu Inference không nhãn), hệ thống vẫn tính toán đầy đủ `Total Rule Hits`, `Hit Rate (%)`, `Execution Latency` và bảng `Sample Hits`, đồng thời hiển thị nhãn `N/A (Unlabeled Dataset)` tại các thẻ `Precision`, `Recall`, `FPR`.

---

## SUC-14: Activate rule (Triển khai / Chuyển đổi trạng thái quy tắc)

### Thông tin chung

- **Mã Use Case:** SUC-14
- **Tên Use Case:** Activate rule (Triển khai / Chuyển đổi trạng thái quy tắc)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `RuleManager`, `ProjectSchemaValidator`, `IRuleRepository`
- **Mô tả:** Cho phép Data Scientist kích hoạt một quy tắc từ trạng thái nháp (`DRAFT`) hoặc tạm ngưng (`INACTIVE`) sang trạng thái hoạt động chính thức (`ACTIVE`), hoặc tạm ngưng một quy tắc đang `ACTIVE` sang `INACTIVE`.
- **Tiền điều kiện:**
	1. Quy tắc đã tồn tại hợp lệ trong dự án hiện tại.
	2. Dự án đã khóa `raw_schema` (`is_schema_locked = true` — đã tải lên ít nhất một Dataset `RAW` theo `BR-PM-04`).
- **Hậu điều kiện:**
	- *Thành công:* Trạng thái `status` và `updated_at` của quy tắc được cập nhật trong cơ sở dữ liệu; các quy tắc có `status = 'ACTIVE'` lập tức được bao gồm khi gọi `RuleManager.get_active_rules_with_versions(project_id)` trong luồng phát hiện gian lận (`SUC-15`).
	- *Thất bại:* Trạng thái quy tắc giữ nguyên như cũ và hiển thị thông báo lỗi.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút chuyển trạng thái (`ACTIVE` / `DRAFT` / `INACTIVE`) trên bảng **Rule Catalog** (`SUC-18`) hoặc nhấn nút **“Triển khai & Kích hoạt”** tại màn hình **Rule Workspace** (`SUC-11` / `SUC-12`).

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn kích hoạt quy tắc (hoặc chuyển đổi trạng thái `ACTIVE` $\leftrightarrow$ `INACTIVE`).
2. Hệ thống gọi `PATCH /api/v1/rules/{rule_id}/status` với payload `{"status": "ACTIVE"}` (hoặc trạng thái đích tương ứng).
3. `RuleManager.set_rule_status` kiểm tra các ràng buộc an toàn của dự án:
	- Kiểm tra dự án không ở trạng thái `ARCHIVED`.
	- Nếu chuyển sang `ACTIVE`, kiểm tra dự án đã khóa `raw_schema` (`BR-PM-04`) và xác thực lại toàn bộ các biến trong `current_version.condition` khớp với `project.raw_schema` (`BR-PM-05`).
4. Hệ thống cập nhật `rule.status` và `rule.updated_at`, lưu vào cơ sở dữ liệu và trả về `RuleResponse` đã cập nhật.
5. Giao diện cập nhật tức thời nhãn trạng thái và bộ đếm quy tắc.

### Luồng ngoại lệ (Exception Flows)

- **3a. Dự án chưa có `raw_schema` hoặc biểu thức điều kiện không tương thích với `raw_schema` (`400 Bad Request`):**
	- Nếu người dùng kích hoạt quy tắc sang `ACTIVE` khi dự án chưa tải lên tập dữ liệu đầu tiên (`is_schema_locked = false`) hoặc quy tắc chứa trường không thuộc `project.raw_schema`, hệ thống từ chối kích hoạt và hiển thị thông báo lỗi trên giao diện.

---

## SUC-13: Get recommended rules (Nhận đề xuất quy tắc tự động) *(Chức năng nâng cao — sẽ bổ sung sau)*

### Thông tin chung

- **Mã Use Case:** SUC-13
- **Tên Use Case:** Get recommended rules (Nhận đề xuất quy tắc tự động)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Mô tả:** Cho phép Data Scientist sử dụng công cụ học máy giải thích được (White-box Decision Tree / Rule Extraction) để tự động phân tích các mẫu gian lận trong dữ liệu lịch sử, từ đó trích xuất và đề xuất các quy tắc phát hiện gian lận tiềm năng dưới dạng cây điều kiện `JsonLogic` chuẩn của Rule Engine.
- **Tiền điều kiện:** Trong dự án đã có `DatasetArtifact` có nhãn mục tiêu (`label` / `is_fraud`).
- **Hậu điều kiện:** Danh sách các quy tắc gợi ý được sinh ra kèm các chỉ số ước lượng (`Precision`, `Recall`, `Support`); các quy tắc được Data Scientist chấp nhận sẽ được lưu vào bảng `rules` ở trạng thái `DRAFT`.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút “Get Recommended Rules” tại màn hình quản lý Rule Engine.
