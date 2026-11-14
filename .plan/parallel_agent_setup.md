# Plan: Thiết lập môi trường cho multi AI agent làm việc song song

> **Nguồn:** `docs/issues/README.md` (index ISS-001..034), `.plan/*.md`, `TODO.md`, phân tích code ngày 26-11-14.
> **Trạng thái:** Phase 0 DONE (26-11-14). Phase 1 chưa bắt đầu; mỗi task cần plan riêng theo skill `usfds-plan`.

---

## 1. Mục tiêu

1. **Review bằng test.** Mỗi task có acceptance test viết trước dạng Given/When/Then. User duyệt danh sách test; code được chấp nhận khi test xanh. Khi xong, agent báo cáo **các điểm logic quan trọng cần đọc code** (Review hotspots), không yêu cầu đọc toàn bộ diff.
2. **Test không cần hạ tầng.** `./scripts/test.sh` chạy trên máy sạch, không cần Docker. DB = SQLite file tạm. S3 = `moto`. Queue = `InlineJobQueue`. Tích hợp thật (PostgreSQL + BullMQ + S3) do user tự test end-to-end.
3. **Task song song, phụ thuộc tối thiểu.** Phase 0 làm trước, một mình. Mỗi plan task bắt buộc có mục phân tích phụ thuộc và xung đột (skill `usfds-plan`).
4. **Agent đủ context.** `AGENTs.md` chính xác, 5 skill trong `.claude/skills/`, `.plan/BOARD.md`.

---

## 2. Hiện trạng (facts)

| Package | LOC | Vai trò | Ghi chú |
|---|---|---|---|
| `usfds-core` | ~22k | Entity, port (`I*Repository`, `IFileStorage`, dispatcher), service | Có `InMemory*Repository`, `InMemoryFileStorage` |
| `usfds-infra` | ~3k | SQLAlchemy ORM + repo, Local/S3 storage, BullMQ (Postgres) | `repositories.py` 1144 dòng; không có Alembic |
| `usfds-server` | ~5.6k | FastAPI, 8 router, 63 endpoint | DI bằng global trong `dependencies.py`; test mutate `settings` |
| `usfds-worker` | ~0.7k | 3 queue, 7 handler (map theo job name trong `main.py`) | Luôn dùng S3 |
| `usfds-web` | ~24k | React 19, react-query, axios, Tailwind | Không có test runner |
| `usfds-cli`, `usfds-agent` | <1k | Typer preprocess; Google ADK PoC | Agent không chạy được (ISS-033) |

**Baseline test (26-11-14, Python 3.14):**
- core: 128 pass / 15 skip, 2 file lỗi collect.
- infra: 19 pass / 2 fail.
- server: 12 pass.
- worker: 3 pass.

Chi tiết ở ISS-024 và ISS-025.

Toàn bộ issue (cũ và mới phát hiện) đã đánh index tại [`docs/issues/README.md`](../docs/issues/README.md).

---

## 3. Thiết kế môi trường test

### 3.1 Hai tầng

| Tầng | Phạm vi | DB | Storage | Queue | Cần hạ tầng |
|---|---|---|---|---|---|
| **Backend** | core service, infra repo, server API (TestClient), worker handler, luồng server→queue→worker | SQLite file tạm / test (Alembic `upgrade head`) | `LocalFileStorage` tmp; S3 path dùng `moto` | `sync` hoặc `InlineJobQueue` | Không |
| **Web** | component + hook + API mock | — | — | — | Không (vitest + jsdom + MSW) |

Bỏ tầng unit thuần với `InMemory*` repo. Code `InMemory*` giữ nguyên vì `src` và agent còn dùng; test mới không dùng nữa.

### 3.2 Queue không cần BullMQ
- Mode `sync`: router gọi thẳng service core, cùng service mà worker handler gọi. Đây là luồng mặc định của test.
- Phần sync **không** phủ được: nhánh `if settings.dispatch_backend == "queue"` trong router, việc serialize payload sang JSON, và glue code trong handler.
- `InlineJobQueue` (đặt trong `usfds_worker.testing`) có cùng chữ ký `enqueue` / `enqueue_and_wait` với `BullMQJobQueue`, và chạy theo các bước:
  1. JSON round-trip payload (bắt lỗi serialize như UUID, datetime, NaN).
  2. Tra handler qua các map `*_QUEUE_HANDLERS` có sẵn trong `usfds_worker.main`.
  3. Gọi handler ngay với `WorkerContext(session_factory, storage)` của test.
  4. Ánh xạ exception theo đúng quy ước `"TypeName: msg"` như BullMQ.
- Server test chỉ cần bật fixture `queue_mode`. `usfds-server` thêm `usfds-worker` làm dev-dependency.

### 3.3 Đảm bảo SQL tương thích PostgreSQL mà không chạy PostgreSQL
Không có tool nào đảm bảo 100% nếu không chạy PG thật. Phương án gồm 3 lớp kiểm tra tĩnh, đều chạy trong suite SQLite:

| # | Kiểm tra | Bắt được | Cơ chế |
|---|---|---|---|
| G1 | **DDL compile** | Kiểu cột/constraint không hợp lệ trên PG | Test compile mọi `Base.metadata` table bằng `CreateTable(...).compile(dialect=postgresql.dialect())`, và `alembic upgrade head --sql` offline với URL PG |
| G2 | **Statement compile guard** | Construct chỉ SQLite (`sqlite.insert().on_conflict_*`, …) | Fixture autouse gắn `event.listen(engine, "before_execute")` → compile mọi `clauseelement` bằng PG dialect; lỗi compile → test fail |
| G3 | **Denylist hàm/cú pháp SQLite** | Hàm hợp lệ cú pháp nhưng sai ngữ nghĩa trên PG, ví dụ `json_each` (ISS-018) | Cùng hook với G2: quét SQL đã compile và mọi `exec_driver_sql`/`text()` theo denylist: `json_each`, `json_extract`, `json_group_array`, `strftime`, `datetime(`, `julianday`, `ifnull`, `group_concat`, `instr`, `printf`, `glob`, `pragma`. Phần chủ đích chỉ cho SQLite (pragma trong `engine.py`) đặt trong allowlist theo module |

**Giới hạn (ghi rõ trong skill):** không bắt được khác biệt ngữ nghĩa (`LIKE` phân biệt hoa thường, kiểu dữ liệu lỏng của SQLite, thứ tự mặc định khi thiếu `ORDER BY`, so sánh timezone). Quy ước bù lại: không dùng raw SQL trong repo; luôn `ORDER BY` khi cần thứ tự; dùng `ilike` khi cần không phân biệt hoa thường. Lớp cuối là E2E của user trên PG.

### 3.4 Thành phần Phase 0
- `usfds-infra/src/usfds_infra/testing/`:
  - fixture `db_engine` (SQLite tmp + `alembic upgrade head` + guard G2/G3), `session_factory`, `storage` (local tmp), `s3_storage` (moto);
  - pytest plugin đăng ký qua `pytest11` hoặc `conftest.py` gọi `pytest_plugins`.
- `usfds-worker/src/usfds_worker/testing.py`: `InlineJobQueue`.
- `usfds-server`: `create_app(settings)` hoặc `dependency_overrides`. Fixture `client`, `client_queue_mode`. Không mutate global.
- `scripts/test.sh [core|infra|server|worker|web|all]`: một entrypoint, exit code ≠ 0 khi fail.
- Python 3.12 qua `uv python install 3.12` + `poetry env use`; `requires-python = ">=3.12,<3.13"`; thêm `.python-version`.
- Web: `vitest`, `@testing-library/react`, `jsdom`, `msw`; script `npm test`; helper `renderWithProviders`.

### 3.5 Quy ước acceptance test
- Backend: viết ở mức API (TestClient) khi tính năng có endpoint; ở mức service khi là logic thuần. Web: component test với MSW.
- Tên test là câu nghiệp vụ: `test_delete_dataset_used_by_training_run_returns_409`.
- Bug fix: test tái hiện bug phải đỏ trước khi sửa.

---

## 4. Quy trình agent

### 4.1 Vòng đời task (skill `usfds-task-workflow`)
1. **Plan** (skill `usfds-plan`): viết `.plan/<task>.md` theo template, gồm mục *Dependencies & Conflicts* và *Acceptance tests*. Cập nhật `.plan/BOARD.md`. **Dừng chờ user duyệt.**
2. **Test first:** viết acceptance test, chạy và xác nhận test đỏ.
3. **Implement** đến khi `./scripts/test.sh <pkg>` xanh, gồm guard G1–G3.
4. **Report:** kết quả test, file thay đổi, **Review hotspots** (2–5 điểm logic quan trọng nhất, dạng `path:line` kèm lý do), giả định, việc bỏ dở.
5. **Merge:** user duyệt → merge → cập nhật `TODO.md`, `CHANGELOG.md`, `BOARD.md`, và trạng thái ISS.

### 4.2 Tài nguyên
| File | Nội dung |
|---|---|
| `AGENTs.md` | Sửa link `docs/arch/*`, thêm mục Parallel work, lệnh test, issue index, quy tắc TODO/CHANGELOG mới |
| `.claude/skills/usfds-plan/SKILL.md` + `template.md` | Template plan thống nhất; checklist phân tích phụ thuộc/xung đột theo BOARD và hot-spot map |
| `.claude/skills/usfds-task-workflow/SKILL.md` | Vòng đời §4.1, format báo cáo cuối có Review hotspots |
| `.claude/skills/usfds-testing/SKILL.md` | Fixture, `InlineJobQueue`, moto, guard PG, mẫu test API/component |
| `.claude/skills/usfds-backend-change/SKILL.md` | Entity → port → repo → Alembic revision → service → router; quy tắc hot-spot |
| `.claude/skills/usfds-frontend-change/SKILL.md` | Design system, UI tiếng Việt, react-query, MSW |
| `.plan/BOARD.md` | Task, lane, trạng thái, phụ thuộc, file sở hữu, agent đang giữ |

Plan file chính là task card; không tạo thêm thư mục `.tasks/`.

### 4.3 Quy tắc song song
- Mỗi agent dùng một git worktree + branch `task/<id>`.
- **Alembic:** mỗi task một revision. Trước khi merge phải rebase `down_revision` lên head mới nhất; gate kiểm tra chỉ có 1 head.
- **Hot-spot file** (sau F3): chỉ append vào danh sách đăng ký; không reformat.
- **TODO.md / CHANGELOG.md / BOARD.md:** agent không sửa trong branch. Chỉ cập nhật lúc merge (đã duyệt, khác quy tắc 4 cũ).

---

## 5. Thứ tự ưu tiên

1. **Phase 0** (bắt buộc, chạy trước).
2. **ISS-006 User management + RBAC** (`.plan/user_management_rbac.md`), ưu tiên cao nhất sau Phase 0. Kèm ISS-014 và ISS-015.
3. Các issue còn lại theo Priority trong index, chia theo lane.

---

## 6. Quyết định đã duyệt (26-11-14)
1. Python 3.12.
2. Một tầng test backend (SQLite + moto + InlineJobQueue). Không có tầng PG; tương thích PG bảo đảm bằng guard G1–G3. User tự E2E trên PG + BullMQ + S3.
3. Alembic: baseline = schema hiện tại; DB đang có được `stamp`, giữ nguyên data.
4. Được sửa `AGENTs.md`, tạo `CHANGELOG.md`, đổi quy tắc TODO, đánh lại SUC ID trùng trong `docs/`.
5. Được tách `models.py`, `repositories.py`, `dependencies.py` theo domain.

---

## 7. Phân rã task

### Phase 0 — Nền tảng
| ID | Nội dung | Issue | Phụ thuộc |
|---|---|---|---|
| F0 | Python 3.12; `scripts/test.sh`; sửa 2 test core import infra; thay fake S3 bằng moto; untrack `.env` | ISS-024, ISS-013 | — |
| F1 | Testkit + `conftest.py`; server không mutate global; `InlineJobQueue` | ISS-025 | F0 |
| F2 | Alembic baseline + stamp DB cũ; bỏ `create_all`/`case_migration` ở startup; guard G1–G3 | ISS-020 | F1 |
| F3 | Tách `models.py`, `repositories.py`, `dependencies.py` theo domain | ISS-026 | F2 |
| F4 | Seam auth: `get_current_user()` trả admin local; bỏ `"mock_user"`/`"local-analyst"`; permission map tập trung để RBAC không phải sửa từng router | ISS-006 (chuẩn bị) | F3 |
| F5 | Web: vitest + MSW; `client.ts` ném lỗi; thống nhất port | ISS-028, ISS-029 | — (song song F0–F4) |
| F6 | Skills, BOARD, `AGENTs.md`, `CHANGELOG.md`, issue index, sửa SUC ID trùng | ISS-034 | — |

Backend chạy F0 → F4 tuần tự. F5 làm song song bởi agent khác. F6 làm trước tiên để agent có skill.

### Phase 1 — RBAC (ưu tiên 1) + các lane khác chạy song song khi không xung đột

> **[26-11-14] Không còn hiệu lực:** việc chia lane và task bên dưới chỉ là gợi ý ban đầu. Mô hình hiện tại: **1 task = 1 agent session = 1 plan file**. User chọn issue cho từng task; milestone chỉ là checkpoint trong plan. Xem `.plan/BOARD.md` và skill `usfds-plan`.
| Lane | ID | Nội dung | Issue | Phụ thuộc |
|---|---|---|---|---|
| B | B-1 | Core + infra: 7 bảng, repo, seed, hash/JWT | ISS-006 | Phase 0 |
| B | B-2 | Server: auth/user/rbac router, members, điền permission map, CORS, chặn path tùy ý | ISS-006, 014, 015 | B-1 |
| B | B-3 | Web: Login, AuthProvider, Admin users, Members tab | ISS-006 | B-2, F5 |
| A | A1 | Chặn xóa dataset đang dùng + fix xóa artifact | ISS-003, 017 | Phase 0 |
| A | A2 | Chặn xóa rule đang dùng | ISS-002 | Phase 0 |
| A | A3 | Artifact format tường minh + loader dispatch | ISS-001 | Phase 0 |
| A | A5 | Training evaluation metrics (TASK-105) | `.plan/training_evaluation_metrics.md` | Phase 0 |
| C | C1 | Việt hóa UI theo module | ISS-005 | F5; tránh module có task FE đang mở |
| C | C2 | Analytics đẩy xuống DuckDB, phân trang | ISS-012, 031 | Phase 0 |
| C | C3 | Hợp nhất system column alias | ISS-027 | Phase 0 |
| — | misc | ISS-016, 018, 019, 021, 022, 023 | | Phase 0 |

**Cần spec trước (Phase 2):** ISS-004, 007, 008, 009, 010, 011.

---

## 8. Tiêu chí nghiệm thu Phase 0
- [x] `./scripts/test.sh` xanh trên máy sạch (Python 3.12 + Node), không cần Docker. 6/6 package xanh, khoảng 28 s.
- [x] Không test nào gán trực tiếp `settings`; override qua fixture `server_settings` (monkeypatch, tự restore). Global trong `dependencies.py` được reset ở teardown.
- [x] Có server test chạy nhánh queue qua `InlineJobQueue` (`usfds-server/tests/test_queue_mode_api.py`).
- [x] Guard G1–G3 bật mặc định. ISS-018 được ghim bằng `xfail(strict=True)`.
- [x] `alembic upgrade head` trên SQLite. Offline SQL cho PG không lỗi. Bản sao DB demo được migrate, giữ nguyên toàn bộ dòng, không có drift.
- [x] `npm test` có component test dùng MSW (`PoliciesView.test.tsx`).
- [ ] Router `"mock_user"` / `"local-analyst"`: giữ nguyên, sẽ thay khi làm RBAC (ISS-006, session riêng). Phần seam auth đã gỡ (26-11-14).
- [x] Có 5 skill, `BOARD.md`, `AGENTs.md` đã cập nhật, `CHANGELOG.md`.
- [ ] Sửa SUC ID trùng (ISS-034): chờ đổi trên Notion trước.
- [ ] ISS-028 (`client.ts` ném lỗi): đã đánh giá, chuyển sang task C4.

## 9. Review hotspots Phase 0
1. `usfds-infra/src/usfds_infra/database/migrations/versions/0001_baseline_baseline_schema.py`: baseline chỉ tạo bảng còn thiếu. DB cũ có bảng lệch so với model sẽ **không** được sửa; `upgrade_database` chỉ log cảnh báo drift (`migrate.py`). Đây là điểm cần lưu ý khi chạy trên PostgreSQL thật.
2. `usfds-infra/src/usfds_infra/database/migrate.py` `upgrade_database`: fix-up SQLite cũ (`case_migration`) chỉ chạy khi DB chưa có `alembic_version`.
3. `usfds-infra/src/usfds_infra/testing/pg_compat.py`: guard dựa trên denylist, không bắt được khác biệt ngữ nghĩa giữa SQLite và PostgreSQL (xem docstring).
4. `usfds-server/src/usfds_server/routers/training_router.py:176,191,258,272`: user_id mặc định đổi từ `"mock_user"` sang UUID của user local (`0000…0000`). Client vẫn có thể tự truyền `user_id`; B-2 sẽ bỏ điểm này.
5. `usfds-server/src/usfds_server/dependencies.py` (cuối file): import provider ở cuối module là có chủ đích, để tránh import vòng.
