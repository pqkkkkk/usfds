# Thiết kế kiến trúc high-level

Stage: 3. Design
Status: Not started
Task ID: TASK-103

# System Boundary Architecture

Link diagram: <u>[System Boundary Architecture](https://app.diagrams.net/#G1sfkxI8ykZ83JPuzKFrtabHKMdhUJt0tO#%7B%22pageId%22%3A%22haGty0TupYkQBxqcn8wv%22%7D)</u>

Sơ đồ kiến trúc ở mức độ tổng quát nhất. Sơ đồ xác định ranh giới của hệ thống (hệ thống sẽ làm gì và không làm gì) và các tác nhân bên ngoài tương tác với hệ thống

# Functional Process Architecture

Link diagram: <u>[Functional Process Architecture](https://app.diagrams.net/#G1sfkxI8ykZ83JPuzKFrtabHKMdhUJt0tO#%7B%22pageId%22%3A%22maI9puIA24e5IPLXIYoS%22%7D)</u>

Sơ đồ kiến trúc ở mức quy trình chức năng. Sau khi đã xác định ranh giới của hệ thống ở System Boundary Architecture, Function Process Architecture sẽ đi chi tiết hơn vào luồng nghiệp vụ chức năng của hệ thống. Luồng chức năng này được chia thành các module chức năng tổng quát có liên kết mật thiết với nhau. Luồng chức năng này gắn liền với vòng đời dữ liệu từ khi còn là dữ liệu thô đến khi trở thành tri thức cho doanh nghiệp

# Data and Functional Process Architecture

Link diagram: <u>[Data and Function Process Architecture](https://app.diagrams.net/#G1sfkxI8ykZ83JPuzKFrtabHKMdhUJt0tO#%7B%22pageId%22%3A%22WU5WfWrJMS8sluc2sOvG%22%7D)</u>

Sơ đồ kiến trúc ở mức quy trình chức năng gắn liền với kỹ thuật dữ liệu. Vì quy trình chức năng của hệ thống gắn liền với vòng đời dữ liệu, sơ đồ này sẽ thể hiện mỗi bước trong quy trình sẽ biến đổi dữ liệu thành dạng nào và sau khi biến đổi thì dữ liệu sẽ được lưu trữ ở không gian lưu trữ nào.

## File Storage (Đại diện cho Data Lake / Schema on read)

Nằm ở đầu luồng dữ liệu, nhận đầu vào từ Ingestion và Batch Detection Request, đồng thời cung cấp dữ liệu cho Feature Engineering ở giai đoạn huấn luyện (Training Stage).

- Vai trò: Là nơi lưu trữ toàn bộ dữ liệu thô (raw data) và dữ liệu lịch sử chưa qua xử lý.
- Trong FDS, dữ liệu đầu vào cực kỳ đa dạng (JSON, CSV, Server Logs, v.v.). Việc áp dụng cơ chế "Schema on read" (định hình cấu trúc khi đọc dữ liệu) giúp hệ thống Ingestion có thể "đổ" dữ liệu vào liên tục với tốc độ cao mà không bị nghẽn bởi các ràng buộc cấu trúc (như khi lưu vào SQL).
- Đặc biệt trong Training Stage, các Data Scientist cần tiếp cận những dữ liệu gốc trong quá khứ để liên tục tìm ra các "đặc trưng" (features) mới phục vụ cho việc huấn luyện lại (retrain) mô hình. File Storage (giống như Amazon S3, Hadoop HDFS) cung cấp không gian lưu trữ chi phí thấp và không giới hạn để đáp ứng nhu cầu này.

## Metadata / Registry

Nằm ở trung tâm kiến trúc, bao gồm Data Schema Definition và Model Artifacts. Cụm này đóng vai trò như "bộ não cấu hình", liên kết giữa giai đoạn Training và Inference.

- Data Schema Definition:
    - Vai trò: Lưu trữ các định nghĩa về cấu trúc dữ liệu, phục vụ cho bước Data Mapping, Feature Engineering và Pre-Processing Pipeline.
    - Để luồng detection ở Inference Stage chạy ổn định, hệ thống cần biết chính xác các field dữ liệu gửi lên (ví dụ: IP, DeviceID, Amount) có hợp lệ không và cần được map (ánh xạ) như thế nào trước khi đưa vào mô hình. Việc tách riêng kho Schema giúp bạn dễ dàng cập nhật hoặc hỗ trợ nhiều phiên bản mô hình học máy khác nhau cho đối tác mà không cần phải viết lại code lõi của hệ thống.
- Model Artifacts:
    - Vai trò: Quản lý và lưu trữ các phiên bản của mô hình máy học đã được huấn luyện (được đẩy xuống từ bước Deploy Model).
    - Tách biệt Model Artifacts giúp tối ưu hóa Inference Stage. Các mô hình FDS thường cần được tải (load) thẳng lên RAM để chấm điểm (scoring) với độ trễ thấp. Ngoài ra, việc quản lý phiên bản (Model Versioning) ở đây giúp hệ thống dễ dàng thực hiện A/B Testing (chạy song song nhiều mô hình) hoặc Rollback ngay lập tức nếu một mô hình mới deploy bắt đầu tạo ra quá nhiều cảnh báo giả (False Positives).

## Operational DBs

Cụm này nằm ở cuối luồng Inference, tương tác trực tiếp với Decision Engine và Dashboard. Dữ liệu khi đi vào đây đã được làm sạch, có tính toàn vẹn cao và cấu trúc chặt chẽ (Schema-on-write)

- Transactional DB (Cơ sở dữ liệu giao dịch / OLTP):
    - Vai trò: Lưu trữ các dữ liệu giao dịch lịch sử, hồ sơ người dùng (User Profiles), và các blacklist/whitelist.
    - Đòi hỏi tốc độ truy xuất cực nhanh và tính nhất quán dữ liệu (ACID) tuyệt đối. Khi một giao dịch đang diễn ra, Rule Engine cần tra cứu ngay lập tức xem người dùng này đã vượt quá hạn mức giao dịch trong ngày chưa. Các CSDL dạng NoSQL (Redis, Cassandra) hoặc RDBMS tối ưu hoá (PostgreSQL) thường được dùng ở đây để đảm bảo độ trễ không làm gián đoạn trải nghiệm thanh toán.
- Graph Database (Cơ sở dữ liệu đồ thị):
    - Vai trò: Phân tích các mối quan hệ đa tầng, mạng lưới tương tác thực thể.
    - Đây là một trong những thành phần quan trọng nhất của FDS hiện đại. Tội phạm gian lận ngày nay hiếm khi hoạt động đơn lẻ mà theo các đường dây (Fraud Rings)*.* Việc thực hiện phép JOIN nhiều bảng trên CSDL quan hệ để tìm ra quy luật này là không phù hợp với mục đích và bản chất của CSDL quan hệ. Graph DB giải quyết bài toán truy vấn quan hệ lưới này với tốc độ thời gian thực.
- Analytic Database (Data Warehouse / OLAP):
    - Vai trò: Tổng hợp và phân tích dữ liệu phục vụ báo cáo trực quan cho Dashboard.
    - Dashboard của đội ngũ điều tra viên (Fraud Analysts) cần thực hiện các truy vấn phức tạp trên tập dữ liệu hàng triệu dòng (ví dụ: *"Tổng số giao dịch bị từ chối bởi Rule #5 trong 30 ngày qua"*). Analytic DB được tối ưu hóa cho các thao tác đọc số lượng lớn (OLAP) để không làm ảnh hưởng đến hiệu năng của hệ thống Real-time (Transactional DB).

# Logical Component Architecture

Link diagram: <u>[Logical Component Architecture](https://app.diagrams.net/#G1sfkxI8ykZ83JPuzKFrtabHKMdhUJt0tO#%7B%22pageId%22%3A%22eFOskQ0gRDzQM9sKppKY%22%7D)</u>

![4. Logical Component Architecture.png](Thi%E1%BA%BFt%20k%E1%BA%BF%20ki%E1%BA%BFn%20tr%C3%BAc%20high-level/4._Logical_Component_Architecture.png)

Sơ đồ kiến trúc ở mức thành phần logic tổng quát. Sơ đồ này chia hệ thống thành nhiều thành phần nhỏ ở góc độ cài đặt. Hệ thống được chia thành nhiều thành phần logic nhỏ hơn có thể phát triển, triển khai độc lập và cách từng thành phần tương tác với nhau

# Physical Component Architecture

Sơ đồ kiến trúc về mặt triển khai thực tế, từng component ở Logical Component sẽ được triển khai trên hạ tầng nào

## K8s

K8s giải quyết được nhiều vấn đề của FDS đặc biệt là trong các tác vụ tự động huấn luyện mô hình (AutoML):

1. Cơ chế Tự phục hồi (Self-healing) cho luồng Real-time Inference

- Đặc thù FDS: Hệ thống đánh giá giao dịch phải hoạt động 24/7. Nếu API dự đoán bị sập dù chỉ 1 phút trong đợt cao điểm, hàng ngàn giao dịch gian lận có thể lọt lưới, hoặc toàn bộ cổng thanh toán của khách hàng sẽ bị tê liệt.
- Sức mạnh K8s: K8s có cơ chế Liveness và Readiness Probes. Nếu Pod xử lý API Inference bị tràn bộ nhớ (OOM) hoặc bị treo do lỗi code, K8s sẽ tự động bắn chết Pod đó và dựng lại một Pod mới thay thế trong vòng vài giây mà người dùng bên ngoài hoàn toàn không hề hay biết. Ở kiến trúc VM đơn lẻ, nếu tiến trình sập, bạn phải chờ DevOps vào restart thủ công hoặc viết script script giám sát bên ngoài rất phức tạp.

2. MLOps & Ephemeral Workload Management (Quản lý Job AutoML ngắn hạn)

- Đặc thù FDS: Tính năng tự động huấn luyện mô hình (AutoML) của bạn đòi hỏi tài nguyên cực kỳ lớn (CPU/RAM/GPU) nhưng chỉ diễn ra trong một khoảng thời gian ngắn (vài chục phút đến vài giờ) khi doanh nghiệp kích hoạt lại việc học máy.
- Sức mạnh K8s: K8s cung cấp đối tượng gọi là Kubernetes Jobs. Khi backend FDS nhận yêu cầu *"Huấn luyện lại mô hình"*, nó gọi K8s API để tạo ra một Job ngắn hạn (ephemeral job). Job này sẽ được K8s cấp phát riêng một không gian tài nguyên cô lập khổng lồ để "nhai" dữ liệu. Ngay khi huấn luyện xong và xuất ra file mô hình (.pmml, .pth), Job này tự động bị hủy hoàn toàn, trả lại 100% tài nguyên sạch cho hệ thống. Tư duy chạy task "xong rồi xóa" này giúp hệ thống FDS cực kỳ tối ưu về chi phí hạ tầng Cloud.

3. Zero-downtime Rollout (Cập nhật Mô hình AI và Luật Nghiệp vụ liên tục)

- Đặc thù FDS: Gian lận luôn biến đổi đối kháng liên tục. Các Data Scientist sẽ phải cập nhật các phiên bản mô hình AI mới hoặc các Fraud Analyst cập nhật bộ luật (Rule Engine) mới liên tục hàng tuần.
- Sức mạnh K8s: K8s quản lý việc cập nhật bằng chiến lược Rolling Update hoặc hỗ trợ cấu hình Canary Deployment. Khi bạn có mô hình V2, K8s sẽ không tắt hệ thống để cài lại, mà nó sẽ bật từ từ từng Pod V2 lên, kiểm tra xem Pod đó chạy ổn định chưa, rồi mới tắt dần các Pod V1 cũ. Giao dịch thanh toán của khách hàng vẫn chảy qua hệ thống mượt mà, đạt trạng thái không gián đoạn (Zero downtime).

4. Multi-tenancy & Isolation (Cô lập tài nguyên giữa các Doanh nghiệp/Dự án)

- Đặc thù FDS: Nếu hệ thống FDS của bạn được thiết kế theo hướng nền tảng (SaaS) cho nhiều doanh nghiệp thuê chung, hoặc chia thành nhiều Dự án (Project-Scoped) độc lập như bạn đã phân tích trong phần *Dynamic Schema*.
- Sức mạnh K8s: Dựa vào Namespaces, Network Policies và Resource Quotas, K8s giúp bạn phân tách tuyệt đối: Dữ liệu và luồng xử lý của Doanh nghiệp A nằm ở một phân vùng mạng hoàn toàn tách biệt với Doanh nghiệp B. Việc Doanh nghiệp A đang chạy một tác vụ AutoML cực nặng sạt tải bộ nhớ sẽ tuyệt đối không bao giờ làm ảnh hưởng đến tốc độ phản hồi API <100ms của Doanh nghiệp B.

Ưu điểm:

- Toàn quyền kiểm soát hạ tầng vật lý
- Không phụ thuộc vào hạ tầng, công nghệ của bên thứ ba

Nhược điểm:

- Thời gian, công sức phát triển nhiều hơn
- Cần có chuyên môn cao về DevOps để quản lý hạ tầng
- Việc quản lý các storage engine trên K8S gặp nhiều khó khăn: FDS yêu cầu nhiều thành phần lưu trữ đa dạng (object storage, graph database, transactional database)... Việc triển khai và vận hành các thành phần *Stateful* (có trạng thái/dữ liệu) trên K8s là cần rất nhiều chuyên môn và công sức về quản lý I/O đĩa cứng, backup/restore và nguy cơ mất mát dữ liệu tài chính khi Pod bị sập.

## Dedicated Worker

Xây dựng 1 hoặc nhiều worker instance để nhận job từ server (thường qua job queue), thực thi và thông báo kết quả lại cho server

Quá trình giao tiếp giữa worker và server thường được quản lý bởi thư viện background jobs management như BullMQ, Celery. BullMQ sẽ được chọn vì nó hỗ trợ Postgres back-end nên không cần thêm hạ tầng cho queue.

⇒ Đây là lựa chọn phù hợp cho phạm vi khóa luận khi không quá phức tạp trong triển khai và vận hành nhưng vẫn là kiến trúc phù hợp cho các hệ thống vừa và nhỏ

# Kiến trúc triển khai đề xuất

> *Kiến trúc triển khai tối giản, phù hợp với phạm vi khóa luận, prototype*
> 

Dựa trên phân tích ưu nhược điểm của các mô hình hạ tầng ở trên và đối chiếu với phạm vi triển khai thực tế của hệ thống USFDS, kiến trúc triển khai đề xuất áp dụng mô hình phân tán `Client – Server – Worker`. Thiết kế này đảm bảo tính chuẩn mực của một hệ thống FDS hiện đại (tách biệt luồng điều phối API và luồng tính toán nặng ML), đồng thời tối giản hóa chi phí vận hành hạ tầng.

## 1. Các Quyết định Kỹ thuật Cốt lõi (Core Technical Decisions)

| Thành phần Kiến trúc | Công nghệ Lựa chọn | Vai trò & Lý do Quyết định |
| --- | --- | --- |
| **Transactional Database (OLTP & Metadata Registry)** | **PostgreSQL** | Lưu trữ toàn bộ dữ liệu có cấu trúc chặt chẽ (ACID): thông tin dự án (`projects`), phả hệ dữ liệu (`datasets`, `dataset_artifacts`), Model Registry (`models`, `model_versions`, `training_runs`), Rule Engine (`rules`, `rule_versions`, `rule_execution_logs`), và Hồ sơ điều tra (`fraud_cases`, `case_transactions`, `entity_watchlists`, `case_audit_logs`). |
| **Object / File Storage (Data Lake & Artifact Store)** | **MinIO** *(S3-Compatible Object Storage)* | Đóng vai trò là Data Lake (Schema-on-read) và kho lưu trữ nhị phân tập trung cho toàn bộ các tệp dữ liệu lớn: tập dữ liệu qua từng bước pipeline (`.csv`, `.parquet`), kết quả chấm điểm hàng loạt (`predictions.parquet`), bộ biến đổi đặc trưng (`fitted_feature_engineers.joblib`, `preprocessor.joblib`) và trọng số mô hình (`model.joblib`, `model_bundle.zip`). Giúp `Server` và `Worker` chia sẻ dữ liệu lớn qua giao thức S3 chuẩn mà không phụ thuộc ổ đĩa cục bộ chung. |
| **Graph Database (Network & Link Analysis)** | [**Apache AGE**](https://age.apache.org/) *(trên cùng instance PostgreSQL)* | Tích hợp trực tiếp tiện ích mở rộng đồ thị **Apache AGE** ngay trên cùng instance PostgreSQL của Transactional DB. Cho phép mô hình hóa mạng lưới đa thực thể (`User`, `Card`, `Device`, `IP`, `Merchant`) và thực thi truy vấn đồ thị chuẩn **openCypher** (`MATCH (u:User)-[:USED_DEVICE]->(d:Device)...`) kết hợp trực tiếp với SQL trong cùng một giao dịch. Loại bỏ hoàn toàn chi phí vận hành một hệ quản trị Graph DB rời rạc (như Neo4j) và triệt tiêu độ trễ đồng bộ dữ liệu (ETL lag) khi điều tra đường dây gian lận (`Fraud Rings`). |
| **Giao tiếp Bất đồng bộ `Server <-> Worker` (Job Queue)** | **BullMQ Pattern với PostgreSQL Backend** *(trên cùng instance PostgreSQL)* | Sử dụng cơ chế hàng đợi tác vụ theo mô hình **BullMQ** đặt nền tảng lưu trữ trạng thái ngay trên cùng instance PostgreSQL (tận dụng cơ chế khóa hàng mức thấp `FOR UPDATE SKIP LOCKED` và kênh sự kiện `LISTEN / NOTIFY`). Quản lý toàn bộ vòng đời các tác vụ tính toán nặng (`waiting`/`queued`, `active`/`running`, `completed`, `failed`, retry & backoff) mà không cần triển khai thêm cụm Redis hay RabbitMQ độc lập. |

## 2. Sơ đồ Kiến trúc Triển khai `Client – Server – Worker`

```
+---------------------------------------------------------------------------------------------------+
|                                      CLIENT TIER (Presentation)                                   |
|                                                                                                   |
|   +-------------------------------------------------------------------------------------------+   |
|   |                                  usfds-web (React SPA)                                    |   |
|   |   • Data Management UI   • Detection & Rule Studio   • Investigation Workbench   • Report |   |
|   +---------------------------------------------+---------------------------------------------+   |
+-------------------------------------------------|-------------------------------------------------+
                                                  | HTTP / REST API (JSON)
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                   APPLICATION & COMPUTE TIER                                      |
|                                                                                                   |
|   +---------------------------------------------+   Enqueue / Events    +---------------------+   |
|   |         usfds-server (FastAPI Backend)      |======================>|                     |   |
|   |  • API Gateway & Schema Validation          |                       |    usfds-worker     |   |
|   |  • Orchestration (Pre-dispatch & Callback)  |   Job Result / State  | (Stateless Compute) |   |
|   |  • Rule CRUD, Case Triage & Graph Query API |<======================|  • Model Training   |   |
|   |  • Insight & Compliance Report Aggregation  |                       |  • Batch Inference  |   |
|   +----------------------+----------------------+                       |  • Feature Eng.     |   |
|                          |                                              +----------+----------+   |
+--------------------------|---------------------------------------------------------|--------------+
                           | SQL / Cypher / Queue Ops                                | S3 API / Queue
                           v                                                         v
+---------------------------------------------------------------------------------------------------+
|                                  UNIFIED DATA & STORAGE TIER                                      |
|                                                                                                   |
|   +-------------------------------------------------------------------+   +-------------------+   |
|   |               PostgreSQL Unified Instance (Single DB)             |   |       MinIO       |   |
|   |                                                                   |   | (Object Storage)  |   |
|   |  +------------------+  +------------------+  +-----------------+  |   |                   |   |
|   |  |  Relational OLTP |  |    Apache AGE    |  |   Job Queue     |  |   | • Raw/Enriched    |   |
|   |  |  • projects      |  |  (Graph Engine)  |  | (BullMQ-style   |  |   |   Parquet Data    |   |
|   |  |  • rules / runs  |  |  • Entity Nodes  |  |  PG Backend)    |  |   | • Model Bundles   |   |
|   |  |  • fraud_cases   |  |  • Link Edges    |  | • job_queues    |  |   | • Predictions     |   |
|   |  |  • watchlists    |  |  • openCypher    |  | • SKIP LOCKED   |  |   |   (.parquet)      |   |
|   |  +------------------+  +------------------+  +-----------------+  |   +-------------------+   |
|   +-------------------------------------------------------------------+                           |
+---------------------------------------------------------------------------------------------------+
```

## 3. Luồng Phối hợp Giữa `Server`, `PostgreSQL Queue`, `MinIO` và `Worker`

Mọi tác vụ tiêu tốn nhiều tài nguyên CPU/RAM (bao gồm Huấn luyện mô hình AI, Chấm điểm phát hiện gian lận theo batch, và Làm giàu đặc trưng cửa sổ trượt) đều tuân thủ nghiêm ngặt vòng đời bất đồng bộ 3 giai đoạn:

1. Giai đoạn 1 — Khởi tạo & Đẩy vào Hàng đợi (Pre-dispatch tại `usfds-server`):
    - Khi người dùng kích hoạt tác vụ từ `usfds-web`, `usfds-server` kiểm tra tính hợp lệ của cấu hình và khởi tạo bản ghi nghiệp vụ (`training_runs` hoặc `detection_jobs`) ở trạng thái `QUEUED`.
    - `usfds-server` đóng gói toàn bộ thông tin đầu vào (đường dẫn URI trên MinIO, siêu tham số, danh sách mô hình và snapshot tập luật) thành `JobPayload` độc lập và đẩy vào bảng hàng đợi trên PostgreSQL, sau đó trả về ngay phản hồi `HTTP 202 Accepted` cho Client.
2. Giai đoạn 2 — Nhận việc & Thực thi Tính toán (Execution tại `usfds-worker`):
    - Tiến trình `usfds-worker` lắng nghe hàng đợi PostgreSQL (`LISTEN/NOTIFY` kết hợp `SELECT ... FOR UPDATE SKIP LOCKED`), nhận job đang chờ và chuyển trạng thái sang `RUNNING`.
    - Worker tải trực tiếp các tệp dữ liệu `.parquet` và gói mô hình từ MinIO về không gian làm việc tạm thời (`Workspace`), thực thi thuật toán học máy / đánh giá tập luật đa mô hình, và đẩy tệp kết quả (`model_bundle.zip` hoặc `predictions.parquet`) ngược lên MinIO.
3. Giai đoạn 3 — Hoàn tất & Đồng bộ Kết quả (Post-execution & Graph Sync):
    - Sau khi lưu trữ tệp đầu ra lên MinIO thành công, Worker cập nhật kết quả hoàn tất (hoặc gọi callback nội bộ về `usfds-server`).
    - `usfds-server` cập nhật trạng thái bản ghi sang `COMPLETED` (hoặc `FAILED`), ghi nhận bộ chỉ số đánh giá (`metrics`, `summary_metrics`), cấp phát phiên bản `ModelVersion` mới (đối với Training), hoặc đồng bộ các đỉnh/cạnh giao dịch nghi vấn vào đồ thị Apache AGE để sẵn sàng phục vụ điều tra mạng lưới tại phân hệ Investigation.