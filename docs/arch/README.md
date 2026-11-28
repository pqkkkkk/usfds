# USFDS As-Built Architecture Documentation
<!-- [26-11-27] Created: 3-tier As-Built architecture index & navigation map. -->

Thư mục `docs/arch/` là **nguồn sự thật về kiến trúc đang vận hành thực tế (As-Built)** của hệ thống USFDS, phục vụ song song hai mục đích:
1. **Cho người duyệt (Human):** Đối chiếu nhanh ranh giới module, hợp đồng dữ liệu và rủi ro toàn hệ thống khi review `.plan/*.md` hoặc PR.
2. **Cho AI Agent:** Có đủ bối cảnh từ tổng quát đến chi tiết trước khi lên kế hoạch (`usfds-plan`), cài đặt (`usfds-task-workflow`) và phản biện (`usfds-review`).

---

## 1. Cấu trúc 3 tầng & Liên kết với góc nhìn thiết kế gốc

Hệ thống giữ nguyên 4 góc nhìn thiết kế tổng quan (từ bộ tài liệu thiết kế gốc trên Google Drive và [`high-level-design.md`](high-level-design.md)), nhưng chuẩn hóa lại theo đúng codebase thực tế và phân cấp độ chi tiết thành 3 tầng:

| Tầng | Tài liệu | Góc nhìn tương ứng | Trả lời câu hỏi gì? |
|---|---|---|---|
| **Tầng 0 — Điều hướng** | [`README.md`](README.md) *(file này)* | Bản đồ tổng | Chạm vào phần nào của hệ thống thì cần đọc tài liệu nào? |
| **Tầng 1 — Tổng quan & Luồng chính** | [`01-context-and-runtime.md`](01-context-and-runtime.md) | System Boundary + Logical Component + Deployment | Hệ thống gồm những package/process/storage nào, chạy ở chế độ nào, kết nối ra sao? |
| **Tầng 1 — Tổng quan & Luồng chính** | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) | Functional Process + Data & Functional Process | Dữ liệu đi qua luồng Training và Inference→Investigation→Insight như thế nào? Các hợp đồng dùng chung giữa module là gì? |
| **Tầng 2 — Chi tiết phân hệ** | [`modules/`](modules/) *(6 Bounded Contexts)* | Module Ownership & Contracts | Mỗi phân hệ sở hữu bảng/file nào, cung cấp contract gì, có state machine và bẫy kỹ thuật nào? |
| **Tầng 3 — Bất biến xuyên suốt** | [`03-system-invariants.md`](03-system-invariants.md) | Cross-cutting Rules & Guardrails | Những quy tắc kỹ thuật & nghiệp vụ nào **không được phép phá vỡ**, và được kiểm chứng bằng test tự động hay review? |

> [!NOTE]
> [`high-level-design.md`](high-level-design.md) giữ vai trò tài liệu bối cảnh/nghiên cứu ban đầu (khái niệm K8s, MinIO, Apache AGE). Khi có sai khác với code đang chạy, các file `01-*`, `02-*`, `03-*` và `modules/*` là nguồn sự thật hiện hành (`implementation-level-design.md` cũ đã được xóa vì lỗi thời).

---

## 2. Bản đồ định tuyến: Chạm vào X → Đọc file nào trước?

| Khi task chạm tới... | Đọc bắt buộc (theo thứ tự) | Đặc tả nghiệp vụ chi tiết (`docs/features/`) |
|---|---|---|
| **Mọi task** (lên plan & review) | [`03-system-invariants.md`](03-system-invariants.md) | — |
| Auth, Users, Roles, RBAC, Project membership, Storage presigned auth | [`01-context-and-runtime.md`](01-context-and-runtime.md) → [`modules/auth-and-tenancy.md`](modules/auth-and-tenancy.md) | [`project_management/suc-spec.md`](../features/project_management/suc-spec.md) |
| Dataset ingestion, Schema mapping, System metadata, Feature management, Preprocessing | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) → [`modules/data-and-features.md`](modules/data-and-features.md) | [`data_management/`](../features/data_management/), [`feature_management/context-modeling.md`](../features/feature_management/context-modeling.md), [`critical_changes.md`](../features/critical_changes.md) |
| Model training, Built-in/Plugin trainers, Model versions, Lineage, Remote compute (Modal) | [`01-context-and-runtime.md`](01-context-and-runtime.md) → [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) → [`modules/training-and-models.md`](modules/training-and-models.md) | [`detection/suc-spec.md`](../features/detection/suc-spec.md) |
| Detection jobs, Online/Batch inference, Rule engine, JsonLogic, Backtest | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) → [`modules/detection-and-rules.md`](modules/detection-and-rules.md) | [`detection/suc-spec.md`](../features/detection/suc-spec.md) |
| Case management, Blacklist/Watchlist, Behavior profile, Network graph (LadybugDB) | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) → [`modules/investigation-and-graph.md`](modules/investigation-and-graph.md) | [`investigation/suc-spec.md`](../features/investigation/suc-spec.md) |
| ProjectWarehouse (DuckDB), Insight metrics, SAR / Executive reports | [`02-data-and-lifecycle-flows.md`](02-data-and-lifecycle-flows.md) → [`modules/insight-and-warehouse.md`](modules/insight-and-warehouse.md) | [`insight_report/suc-spec.md`](../features/insight_report/suc-spec.md) |
| Worker queues, BullMQ, Storage backend, DB migrations, Docker/Env | [`01-context-and-runtime.md`](01-context-and-runtime.md) → [`03-system-invariants.md`](03-system-invariants.md) | — |

---

## 3. Quy tắc dừng độ chi tiết ("The Stop Rule")

Để tài liệu luôn ngắn gọn và không lỗi thời sau mỗi lần refactor:

- **PHẢI ghi trong `docs/arch/`:**
  - Ranh giới trách nhiệm giữa package và giữa 6 domain module (ai sở hữu bảng/file nào).
  - Hợp đồng dùng chung (Shared Contracts) mà ≥ 2 module cùng đọc/ghi (format artifact, cột hệ thống, schema `ProjectWarehouse`, payload queue, quy ước `project_id`/`user_id`).
  - Vòng đời trạng thái (State Machines) của thực thể cốt lõi.
  - Bất biến kỹ thuật & nghiệp vụ (`INV-001..N`) và các lỗi/bẫy xuyên module đã biết.
- **KHÔNG ghi trong `docs/arch/`:**
  - Danh sách chi tiết từng cột ORM, từng tham số hàm, từng component React, hay thuật toán nội bộ của 1 hàm (code + docstring + `docs/features/**/suc-spec.md` là nguồn sự thật cho những phần đó).
- **Quy tắc kiểm thử độ chi tiết:** Nếu một dòng phải sửa chỉ vì đổi tên biến/hàm nội bộ trong 1 module → **quá chi tiết, loại bỏ**. Nếu đổi nó có thể làm 1 module khác sai ngầm mà test cục bộ vẫn xanh → **bắt buộc phải ghi**.

---

## 4. Quy tắc đồng bộ tài liệu (Doc-Sync Policy)

Mỗi PR thay đổi bất kỳ mục nào sau đây **bắt buộc** cập nhật `docs/arch/` tương ứng (kèm comment `[YY-MM-DD]` theo `AGENTs.md`) trước khi merge:
- Thêm/xóa package, router mới, BullMQ queue/job mới, storage prefix mới, hoặc chế độ runtime mới → cập nhật `01-context-and-runtime.md`.
- Thay đổi luồng dữ liệu, định dạng artifact/warehouse/schema contract hoặc state machine → cập nhật `02-data-and-lifecycle-flows.md` và `modules/<module>.md`.
- Thêm/sửa/gỡ bất biến hoặc chuyển một bất biến từ Review Checklist sang Automation Test → cập nhật `03-system-invariants.md`.
