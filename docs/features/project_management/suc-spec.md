<!-- [26-10-24] Approved creation of Project Management System Use Case Specification (SUC-22 to SUC-26) -->
# Đặc tả use case hệ thống phân hệ Project Management

Parent item: Đặc tả use case hệ thống (https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
Stage: 3. Design
Updated: 24/10/2026 `[26-10-24]`

# 0. Tài liệu liên quan

- `docs/features/project_management/design.md` (Thiết kế Kiến trúc Quản lý Dự án & Ràng buộc Schema)
- `docs/features/data_management/user-flow-and-ui-design.md` (`SUC-00` $\rightarrow$ `SUC-07`)
- `docs/features/detection/suc-spec.md` (`SUC-08` $\rightarrow$ `SUC-17`)
- `docs/features/investigation/suc-spec.md` (`SUC-17` $\rightarrow$ `SUC-21`)

# 1. Tổng quan nghiệp vụ Quản lý Dự án (Project Management)

Phân hệ **Project Management** đóng vai trò là lớp quản trị không gian làm việc (Workspace Governance) và kiểm soát tính tương thích lược đồ dữ liệu (`RAW` Schema Compatibility) xuyên suốt các phân hệ **Data Management**, **Model Management**, **Rule Management**, **Detection** và **Investigation**.

Mọi tài nguyên nghiệp vụ (`Dataset`, `Rule`, `TrainingRun`, `ModelVersion`, `Deployment`, `DetectionJob`) đều được cô lập theo `project_id`. Mỗi dự án duy trì cơ chế **Schema-on-First-Upload**:
- Khi mới khởi tạo, `project.raw_schema` ở trạng thái mở khóa (`UNLOCKED` / `None`).
- Khi Dataset `RAW` đầu tiên được nạp vào dự án, hệ thống tự động trích xuất danh sách cột cùng kiểu dữ liệu logic (`NUMERIC`, `STRING`, `BOOLEAN`, `DATETIME`) và khóa thành `project.raw_schema` (`LOCKED`).
- Tất cả các Dataset tải lên tiếp theo và các quy tắc `JsonLogic` trong `Rule Engine` đều được kiểm tra tương thích với `project.raw_schema`.

# 2. Tóm tắt danh mục Use Case hệ thống

Dưới đây là danh mục Use Case hệ thống (SUC) cho phân hệ **Project Management** (tiếp nối mã số từ `SUC-21` của phân hệ Investigation).

| Mã SUC | Tên Use Case | Primary Actor | Mô tả tóm tắt | Priority |
| --- | --- | --- | --- | --- |
| **SUC-22** | **Create project** | Data Scientist, Fraud Analyst | Khởi tạo dự án phát hiện gian lận mới với trạng thái `ACTIVE` và `raw_schema` mở khóa (`UNLOCKED`). | High |
| **SUC-23** | **View & switch project** | Data Scientist, Fraud Analyst | Xem danh sách dự án kèm thống kê tài nguyên (`datasets_count`, `rules_count`, `detection_jobs_count`), lọc/tìm kiếm và chuyển đổi ngữ cảnh dự án đang làm việc. | High |
| **SUC-24** | **Inspect & reset project RAW schema** | Data Scientist | Xem chi tiết cấu trúc `raw_schema` đã khóa của dự án (tên cột, kiểu dữ liệu logic/vật lý, `nullable`, `base_dataset_id`) và mở khóa/đặt lại schema khi chưa có tài nguyên phụ thuộc. | High |
| **SUC-25** | **Update & archive project** | Data Scientist | Cập nhật tên, mô tả dự án hoặc chuyển trạng thái dự án sang lưu trữ (`ARCHIVED`) / khôi phục (`ACTIVE`). | Medium |
| **SUC-26** | **Delete project** | Data Scientist | Xóa vĩnh viễn dự án cùng toàn bộ tài nguyên con và tệp lưu trữ vật lý khi không có tiến trình đang chạy. | Medium |

# 3. Chi tiết đặc tả Use Case

Phần này đặc tả chi tiết 5 Use Case thuộc phân hệ **Project Management** (`SUC-22` đến `SUC-26`).

---

## SUC-22: Create project (Khởi tạo dự án mới)

### Thông tin chung

- **Mã Use Case:** SUC-22
- **Tên Use Case:** Create project (Khởi tạo dự án mới)
- **Tác nhân chính (Primary Actor):** Data Scientist, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Hệ thống cơ sở dữ liệu (`IProjectRepository`)
- **Mô tả:** Cho phép người dùng tạo một không gian dự án mới để cô lập dữ liệu giao dịch, mô hình học máy, tập luật và các đợt rà soát gian lận theo từng bài toán nghiệp vụ riêng biệt.
- **Tiền điều kiện:** Người dùng đang truy cập hệ thống `usfds-web`.
- **Hậu điều kiện:**
	- *Thành công:* Bản ghi `Project` mới được lưu vào bảng `projects` với `status = 'ACTIVE'`, `raw_schema = None` (`is_schema_locked = False`), `base_dataset_id = None`; dự án mới được tự động chọn làm ngữ cảnh làm việc hiện hành trên `Topbar`.
	- *Thất bại:* Không sinh bản ghi mới trong bảng `projects`.
- **Sự kiện kích hoạt (Trigger):** Người dùng nhấn nút **“+ New Project”** trên menu chọn dự án ở `Topbar` hoặc trên trang **Project Management** (`/projects`).

### Luồng sự kiện chính (Basic Flow)

1. Người dùng nhấn nút **+ New Project**.
2. Hệ thống hiển thị hộp thoại **Create New Project Modal** gồm các trường:
	- **Tên dự án (`project_name`)** *(Bắt buộc, tối đa 255 ký tự)*.
	- **Mô tả dự án (`description`)** *(Tùy chọn, tối đa 2000 ký tự — ghi chú mục tiêu nghiệp vụ, nguồn dữ liệu giao dịch)*.
3. Người dùng nhập thông tin và nhấn nút **Create Project**.
4. Hệ thống gửi yêu cầu `POST /api/v1/projects` tới máy chủ.
5. Hệ thống chuẩn hóa chuỗi `project_name` và kiểm tra tính duy nhất của cặp `(user_id, project_name)` theo quy tắc `BR-PM-07`.
6. Hệ thống khởi tạo thực thể `Project` với `status = ProjectStatus.ACTIVE`, `raw_schema = None`, `base_dataset_id = None` và lưu xuống cơ sở dữ liệu.
7. Hệ thống trả về thông tin dự án vừa tạo (`201 Created`), đóng hộp thoại, cập nhật danh sách dự án và chuyển ngữ cảnh làm việc (`Active Project`) sang dự án mới.

### Luồng ngoại lệ (Exception Flows)

- **5a. Tên dự án để trống hoặc trùng lặp (`400 Bad Request`):**
	- Nếu `project_name` rỗng hoặc đã tồn tại trong phạm vi người dùng hiện tại, hệ thống trả về lỗi `400 Bad Request` và hiển thị thông báo trực tiếp trên biểu mẫu: *“Dự án với tên '<project_name>' đã tồn tại cho người dùng này. Vui lòng chọn tên khác.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-01 (Schema-on-First-Upload):** Khi mới tạo dự án, `raw_schema` luôn ở trạng thái mở khóa (`None`) và chỉ tự động khóa khi Dataset `RAW` đầu tiên được nạp thành công.
- **BR-PM-07 (Project-Scoped Uniqueness):** `project_name` phải là duy nhất trong phạm vi một người dùng `(user_id, project_name)`.

---

## SUC-23: View & switch project (Xem danh sách và chuyển đổi ngữ cảnh dự án)

### Thông tin chung

- **Mã Use Case:** SUC-23
- **Tên Use Case:** View & switch project (Xem danh sách và chuyển đổi ngữ cảnh dự án)
- **Tác nhân chính (Primary Actor):** Data Scientist, Fraud Analyst
- **Tác nhân phụ (Secondary Actor):** Hệ thống cơ sở dữ liệu (`IProjectRepository`, `IDatasetRepository`, `IRuleRepository`, `IDetectionJobRepository`)
- **Mô tả:** Cho phép người dùng xem danh mục tất cả các dự án kèm số liệu thống kê tài nguyên, lọc theo trạng thái (`ACTIVE` / `ARCHIVED`) hoặc từ khóa, và chuyển đổi dự án đang hoạt động (`Active Project Context`) để toàn bộ các phân hệ (`Data Management`, `Rule Management`, `Model Management`, `Detection`) tự động đồng bộ dữ liệu theo dự án được chọn.
- **Tiền điều kiện:** Người dùng đang truy cập hệ thống `usfds-web`.
- **Hậu điều kiện:**
	- Danh sách dự án hiển thị đầy đủ trạng thái khóa schema (`LOCKED` / `UNLOCKED`) và số lượng tài nguyên.
	- Khi chọn một dự án, `project_id` được lưu vào ngữ cảnh toàn cục (`ProjectContext` & `localStorage`) và làm mới dữ liệu các phân hệ con.
- **Sự kiện kích hoạt (Trigger):**
	1. Ứng dụng khởi chạy lần đầu và nạp danh sách dự án cho `Topbar`.
	2. Người dùng mở menu **Project Switcher** trên `Topbar` hoặc truy cập trang **Project Management** (`/projects`).

### Luồng sự kiện chính (Basic Flow)

1. Người dùng mở menu **Project Switcher** trên `Topbar` hoặc điều hướng tới trang **Project Management** (`/projects`).
2. Hệ thống gọi `GET /api/v1/projects` (kèm bộ lọc `status` và `search` nếu có).
3. Hệ thống truy vấn danh sách dự án và tổng hợp thống kê tài nguyên cho từng dự án:
	- Trạng thái dự án (`ACTIVE` hoặc `ARCHIVED`).
	- Trạng thái lược đồ dữ liệu (`is_schema_locked`: `LOCKED` với số lượng cột hoặc `UNLOCKED`).
	- Số lượng tập dữ liệu (`datasets_count`), quy tắc (`rules_count`), và tác vụ phát hiện (`detection_jobs_count`).
4. Hệ thống hiển thị danh sách dự án:
	- Trên **Topbar Dropdown**: Hiển thị nhanh tên dự án, nhãn trạng thái khóa schema, dấu kiểm tại dự án đang chọn, cùng nút **+ New Project** và **Manage Projects**.
	- Trên trang **Project Management (`/projects`)**: Hiển thị thẻ KPI tổng quan (Tổng số dự án, Dự án `ACTIVE`, Dự án đã khóa `RAW Schema`, Dự án `ARCHIVED`), thanh tìm kiếm/lọc theo trạng thái, và bảng/lưới danh mục dự án chi tiết.
5. Người dùng nhấp chọn một dự án làm **Active Workspace Project**.
6. Hệ thống cập nhật `currentProject` trong `ProjectContext`, lưu `project_id` vào `localStorage`, và tự động truy vấn lại danh sách Dataset / Rule thuộc dự án mới.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-06 (Cross-Project Isolation):** Mọi danh sách tài nguyên trên giao diện (`DatasetHubView`, `RuleCatalogView`,...) chỉ hiển thị và thao tác trên dữ liệu thuộc `currentProject.project_id`.

---

## SUC-24: Inspect & reset project RAW schema (Xem chi tiết và đặt lại lược đồ RAW của dự án)

### Thông tin chung

- **Mã Use Case:** SUC-24
- **Tên Use Case:** Inspect & reset project RAW schema (Xem chi tiết và đặt lại lược đồ RAW của dự án)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `ProjectManagementService`, `IProjectRepository`
- **Mô tả:** Cho phép Data Scientist kiểm tra chi tiết cấu trúc `raw_schema` đang áp dụng cho dự án (danh sách tên cột, kiểu dữ liệu logic `LogicalDataType`, kiểu dữ liệu vật lý `physical_dtype`, cờ `nullable`, thời điểm khóa `locked_at` và `source_dataset_id`), đồng thời hỗ trợ mở khóa / đặt lại (`Reset Schema`) nếu dự án không còn tài nguyên phụ thuộc.
- **Tiền điều kiện:** Dự án đã tồn tại trong hệ thống.
- **Hậu điều kiện:**
	- *Khi xem (Inspect):* Hiển thị đầy đủ bảng cấu trúc cột của `project.raw_schema`.
	- *Khi đặt lại (Reset) thành công:* `project.raw_schema` và `project.base_dataset_id` được đặt về `None` (`is_schema_locked = False`), cho phép nạp Dataset mới với cấu trúc cột khác.
- **Sự kiện kích hoạt (Trigger):** Data Scientist nhấn nút **“Inspect Schema”** tại dòng dự án trên trang `/projects` hoặc từ menu ngữ cảnh dự án.

### Luồng sự kiện chính (Basic Flow)

1. Data Scientist chọn hành động **Inspect Schema** trên một dự án.
2. Hệ thống gọi `GET /api/v1/projects/{project_id}` và mở ngăn **Project Schema Inspector Drawer** (hoặc Modal chi tiết).
3. Hệ thống hiển thị thông tin quản trị schema của dự án:
	- **Trạng thái Schema:** Badge `LOCKED` (kèm thời gian `locked_at` và `base_dataset_id`) hoặc `UNLOCKED` (chưa có Dataset cơ sở).
	- **Bảng danh sách cột (`raw_schema.columns`):**
		- Tên cột gốc (`Column Name`).
		- Kiểu dữ liệu logic (`LogicalDataType`: `NUMERIC`, `STRING`, `BOOLEAN`, `DATETIME`).
		- Kiểu dữ liệu vật lý (`physical_dtype`: `int64`, `float64`, `object`,...).
		- Ràng buộc rỗng (`nullable`: `Nullable` / `Required`).
	- **Thống kê tài nguyên phụ thuộc:** `datasets_count`, `rules_count`, `detection_jobs_count`.
4. Nếu Data Scientist cần đặt lại schema (do tải nhầm file đầu tiên và đã xóa hết các tài nguyên phụ thuộc), người dùng nhấn nút **Reset / Unlock RAW Schema** và xác nhận.
5. Hệ thống gọi `POST /api/v1/projects/{project_id}/schema/reset`.
6. Hệ thống kiểm tra điều kiện an toàn theo `BR-PM-03` (`datasets_count == 0`, `rules_count == 0`, `detection_jobs_count == 0`), đặt `raw_schema = None`, `base_dataset_id = None` và lưu xuống cơ sở dữ liệu.
7. Hệ thống cập nhật giao diện dự án về trạng thái `UNLOCKED` và hiển thị thông báo thành công.

### Luồng ngoại lệ (Exception Flows)

- **6a. Dự án vẫn còn tài nguyên phụ thuộc (`400 Bad Request`):**
	- Nếu trong dự án vẫn còn ít nhất 1 `Dataset`, `Rule` hoặc `DetectionJob`, hệ thống vô hiệu hóa nút Reset trên UI (hoặc trả về lỗi `400 Bad Request` nếu gọi API): *“Không thể đặt lại (reset) RAW schema khi dự án vẫn còn tài nguyên phụ thuộc (datasets=..., rules=..., detection_jobs=...). Vui lòng xóa các tài nguyên phụ thuộc trước.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-02 (Quy tắc tương thích cột):** Mọi Dataset nạp vào khi schema đang `LOCKED` phải khớp `LogicalDataType` và phủ đủ cột (cho phép khuyết tối đa 1 cột nhãn đối với tập `INFERENCE`).
- **BR-PM-03 (Điều kiện mở khóa Schema):** Chỉ cho phép mở khóa `raw_schema` khi dự án không còn bất kỳ `Dataset`, `Rule` hay `DetectionJob` nào phụ thuộc.

---

## SUC-25: Update & archive project (Cập nhật thông tin và lưu trữ dự án)

### Thông tin chung

- **Mã Use Case:** SUC-25
- **Tên Use Case:** Update & archive project (Cập nhật thông tin và lưu trữ dự án)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `ProjectManagementService`, `IProjectRepository`
- **Mô tả:** Cho phép người dùng chỉnh sửa tên hiển thị (`project_name`), mô tả (`description`) của dự án, hoặc chuyển đổi trạng thái dự án giữa `ACTIVE` (Đang hoạt động) và `ARCHIVED` (Lưu trữ).
- **Tiền điều kiện:** Dự án tồn tại trong hệ thống.
- **Hậu điều kiện:**
	- *Thành công:* Thông tin `project_name`, `description`, `status` và `updated_at` của dự án được cập nhật trong cơ sở dữ liệu.
	- *Thất bại:* Giữ nguyên thông tin dự án hiện tại.
- **Sự kiện kích hoạt (Trigger):** Người dùng nhấn nút **Edit** hoặc **Archive / Restore** tại dòng dự án trên trang `/projects`.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng chọn **Edit Project** trên một dự án trong danh sách `/projects`.
2. Hệ thống hiển thị hộp thoại chỉnh sửa với thông tin hiện tại (`project_name`, `description`, `status`).
3. Người dùng thay đổi tên, mô tả hoặc trạng thái (`ACTIVE` / `ARCHIVED`) và nhấn **Save Changes** (hoặc nhấn trực tiếp nút nhanh **Archive / Restore**).
4. Hệ thống gửi yêu cầu `PATCH /api/v1/projects/{project_id}`.
5. Hệ thống kiểm tra:
	- Nếu đổi `project_name`: Kiểm tra không để trống và không trùng với dự án khác của cùng người dùng (`BR-PM-07`).
	- Nếu chuyển trạng thái sang `ARCHIVED`: Kiểm tra dự án không có `TrainingRun` hoặc `DetectionJob` nào đang ở trạng thái `RUNNING` hoặc `PENDING` (`BR-PM-08`).
6. Hệ thống lưu bản ghi cập nhật và làm mới danh sách dự án trên giao diện.

### Luồng ngoại lệ (Exception Flows)

- **5a. Trùng tên dự án khi đổi tên (`400 Bad Request`):**
	- Hiển thị thông báo lỗi trùng tên ngay trên hộp thoại chỉnh sửa.
- **5b. Đang có tiến trình chạy ngầm khi chuyển sang `ARCHIVED` (`400 Bad Request`):**
	- Hệ thống từ chối lưu trữ và hiển thị cảnh báo: *“Không thể lưu trữ (ARCHIVE) dự án khi đang có tác vụ DetectionJob hoặc TrainingRun ở trạng thái RUNNING/PENDING.”*

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-07:** Tên dự án sau khi cập nhật vẫn phải đảm bảo tính duy nhất theo `(user_id, project_name)`.
- **BR-PM-08:** Không được phép lưu trữ (`ARCHIVE`) dự án khi đang có tiến trình huấn luyện hoặc phát hiện gian lận đang chạy.

---

## SUC-26: Delete project (Xóa dự án và dọn dẹp tài nguyên)

### Thông tin chung

- **Mã Use Case:** SUC-26
- **Tên Use Case:** Delete project (Xóa dự án và dọn dẹp tài nguyên)
- **Tác nhân chính (Primary Actor):** Data Scientist
- **Tác nhân phụ (Secondary Actor):** `ProjectManagementService`, `IProjectRepository`, `IDatasetRepository`, `IRuleRepository`, `IFileStorage`
- **Mô tả:** Cho phép người dùng xóa vĩnh viễn một dự án cùng toàn bộ các tập dữ liệu, quy tắc và tệp lưu trữ vật lý thuộc dự án đó.
- **Tiền điều kiện:** Dự án tồn tại trong hệ thống và không có tiến trình `TrainingRun` hay `DetectionJob` nào đang ở trạng thái `RUNNING` / `PENDING`.
- **Hậu điều kiện:**
	- *Thành công:* Bản ghi `Project` cùng các `Dataset`, `Rule` và thư mục lưu trữ vật lý (`datasets/{dataset_id}`, `models/{project_id}`) bị xóa hoàn toàn. Nếu dự án bị xóa đang là `Active Project`, giao diện tự động chuyển ngữ cảnh sang dự án `ACTIVE` kế tiếp.
	- *Thất bại:* Dự án và các tài nguyên liên quan được giữ nguyên.
- **Sự kiện kích hoạt (Trigger):** Người dùng nhấn nút **Delete Project** trên trang `/projects`.

### Luồng sự kiện chính (Basic Flow)

1. Người dùng nhấn nút **Delete** tại dòng dự án cần xóa trên trang `/projects`.
2. Hệ thống hiển thị hộp thoại xác nhận xóa (**Delete Confirmation**), cảnh báo rõ số lượng tài nguyên sẽ bị xóa dây chuyền (`datasets_count` datasets, `rules_count` rules).
3. Người dùng xác nhận xóa.
4. Hệ thống gọi `DELETE /api/v1/projects/{project_id}`.
5. Hệ thống kiểm tra không có `TrainingRun` hoặc `DetectionJob` nào đang `RUNNING` / `PENDING` (`BR-PM-08`).
6. Hệ thống thực hiện xóa dây chuyền (Cascade Delete) các `Rule`, `Dataset`, dọn dẹp các thư mục tệp vật lý trong `IFileStorage`, và xóa bản ghi `Project`.
7. Hệ thống cập nhật lại danh sách dự án trên giao diện; nếu dự án vừa xóa là dự án đang chọn trên `Topbar`, hệ thống tự động chọn dự án đầu tiên còn lại trong danh sách.

### Luồng ngoại lệ (Exception Flows)

- **5a. Có tác vụ đang thực thi (`400 Bad Request`):**
	- Nếu dự án đang có tiến trình `RUNNING` hoặc `PENDING`, hệ thống chặn thao tác xóa và hiển thị thông báo lỗi cho người dùng.

### Quy tắc nghiệp vụ (Business Rules)

- **BR-PM-08 (Bảo vệ khi xóa dự án):** Nghiêm cấm xóa dự án khi có `TrainingRun` hoặc `DetectionJob` đang ở trạng thái `RUNNING` / `PENDING`. Khi xóa hợp lệ, phải dọn dẹp đồng bộ cả cơ sở dữ liệu và tệp vật lý.
