# Plan: Web API client error propagation (ISS-028)

> **Task ID:** `web_api_client_error_propagation` · **Issues:** ISS-028 · **Spec:** — (bug fix theo đánh giá tại `docs/issues/11-14-2026.md:125-136`)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-16)

## 1. Context (facts)
- `usfds-web/src/api/client.ts:118-161`: Các method `get`, `post`, `put`, `patch`, `delete` của `ApiClient` đều bọc `try/catch` và trả về `{ success: false, data: null as unknown as T, error: err.message }` khi Axios reject.
- `usfds-web/src/api/client.ts:163-171`: `normalizeResponse` trả nguyên `data` nếu có key `'success'`, nên kể cả HTTP 200 với `{ success: false, error: ... }` cũng không throw.
- Hệ quả: `react-query` (`usfds-web/src/api/queryClient.ts:3-15`, cấu hình `retry: 1`) không bao giờ nhận rejected promise từ `apiClient` trực tiếp nếu caller không tự kiểm tra `!res.success` rồi throw.
- `usfds-web/src/types/api.ts:22-26`: Đã có interface `ApiError { message: string; statusCode?: number; details?: unknown; }`, nhưng chưa có class `Error` runtime tương ứng.
- Hiện trạng caller trong `usfds-web/src/`:
  - Một số module/hook đã tự unwrap & throw khi `!res.success` (ví dụ `usfds-web/src/api/investigationApi.ts:5-11`, `insightReportApi.ts`, `useProjects.tsx`, `useDataset*.ts`).
  - Nhiều component/page vẫn gọi `apiClient` (hoặc module API trả `ApiResponse<T>`) và kiểm tra `res.success` / `res.error` hoặc dùng `Promise.all` (`ModelHubView.tsx:63,73`, `TrainingWizardView.tsx:64,74`, `RuleDryRunWorkspace.tsx:120`, `DetectionJobWizardView.tsx:84,121`) — nếu `apiClient` throw mà chưa migrate, `Promise.all` sẽ fail toàn bộ khi một item lỗi và các nhánh `else` kiểm tra `!res.success` không `try/catch` sẽ thành unhandled rejection.

## 2. Goal, scope verdict & non-goals
- **Goal:** `ApiClient` (`get`, `post`, `put`, `patch`, `delete`) throw `ApiClientError` (mang `message`, `statusCode`, `details`) khi request lỗi hoặc payload có `success === false`, và toàn bộ caller trong `usfds-web` xử lý lỗi nhất quán qua `try/catch`, `react-query` error state, hoặc `Promise.allSettled` (với partial-failure loads).
- **Scope:** OK
- **Non-goals / omitted:**
  - Không thay đổi chữ ký trả về thành công `Promise<ApiResponse<T>>` của `apiClient` hay refactor toàn bộ typing `usfds-web` (thuộc `ISS-032`).
  - Không đổi copy/UI layout ngoài việc giữ thông điệp lỗi tiếng Việt hiện có.
- **Assumptions:**
  - Backend lỗi HTTP 4xx/5xx vẫn qua Axios response interceptor (`usfds-web/src/api/client.ts:55-83`, giữ nguyên cơ chế single-flight 401 refresh).
  - Các caller đã có `try { ... } catch` sẽ bắt được `ApiClientError` (là `instanceof Error`, nên `err.message` vẫn hoạt động).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| create | `usfds-web/src/api/client.test.ts` | M1 | Unit tests cho `ApiClient` error propagation & `ApiClientError` |
| modify | `usfds-web/src/types/api.ts` | M1 | Giữ `ApiError` interface; bổ sung/đồng bộ nếu cần |
| modify | `usfds-web/src/api/client.ts` | M1 | Hot-spot (append-only style): thêm `ApiClientError`, bỏ `try/catch` nuốt lỗi ở `get/post/put/patch/delete`, throw khi `success === false` |
| modify | `usfds-web/src/api/{datasetApi,detectionApi,docsDashboardApi,insightReportApi,investigationApi,storageApi}.ts` | M2 | Dọn dead-code `!res.success` hoặc đảm bảo tương thích khi `apiClient` throw |
| modify | `usfds-web/src/hooks/{useAuth.tsx,useDatasetDetail.ts,useDatasetImport.ts,useDatasetList.ts,useDatasetPipeline.ts,useModelLineage.ts,useProjectMembers.ts,useProjects.tsx}` | M2 | Bắt/propagate lỗi đúng qua `react-query` hoặc `try/catch` |
| modify | `usfds-web/src/components/modules/**`, `usfds-web/src/pages/AdminUsersPage.tsx` | M2 | Chuyển `Promise.all` partial-failure sang `Promise.allSettled`; đảm bảo imperative calls có `try/catch`; bỏ dead `!res.success` checks |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task nào `In progress` trên `.plan/BOARD.md`) |
| C2 | Hot-spot files touched | `usfds-web/src/api/client.ts` |
| C3 | Schema change | No |
| C4 | Public contract change | No (chỉ đổi hành vi error-path nội bộ frontend `apiClient`) |
| C5 | Shared UI shell change | Yes: `usfds-web/src/api/client.ts` (nhưng không có task khác đang chạy) |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `rejects with ApiClientError on HTTP 4xx/5xx` (`usfds-web/src/api/client.test.ts`) | Server trả HTTP 500 hoặc 400 với `{ detail: "Lỗi server" }` | Gọi `apiClient.get('/v1/test')` (và `post/put/patch/delete`) | Promise reject với `ApiClientError` (`instanceof Error`), `message === "Lỗi server"`, `statusCode === 500/400` | ISS-028 |
| M1 | `rejects with ApiClientError when response has success: false` (`usfds-web/src/api/client.test.ts`) | Server trả HTTP 200 với `{ success: false, error: "Thao tác thất bại" }` | Gọi `apiClient.post('/v1/test', {})` | Promise reject với `ApiClientError`, `message === "Thao tác thất bại"` | ISS-028 |
| M1 | `retries once then enters react-query error state on failure` (`usfds-web/src/api/client.test.ts`) | `useQuery` gọi `apiClient.get` và server luôn trả 500 | Render hook với `QueryClient` (`retry: 1`) | Request được gọi 2 lần (1 lần đầu + 1 retry) và `result.current.isError === true` với `result.current.error.message` đúng | ISS-028 |
| M2 | `ModelHubView renders partial data when per-model version fetch fails` (`usfds-web/src/components/modules/model/ModelHubView.test.tsx`) | Danh sách models & runs trả về thành công, nhưng 1 call `getModelVersions` trả lỗi 500 | Render `ModelHubView` | View không crash, vẫn hiển thị các models/runs còn lại (nhờ `Promise.allSettled`) | ISS-028 |
| M2 | `existing web test suite and TypeScript build stay green` (`./scripts/test.sh web` & `npm run build`) | Toàn bộ `usfds-web` đã migrate khỏi nuốt lỗi | Chạy `tsc -b` và vitest suite | 0 lỗi TypeScript, toàn bộ vitest tests pass | ISS-028 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)

- [x] **M1 — `ApiClientError` & `apiClient` throws on error** (`usfds-web`): `apiClient` không còn nuốt lỗi, `react-query` nhận error & retry hoạt động.
  - [x] [tests] Viết unit tests trong `usfds-web/src/api/client.test.ts` theo §5; xác nhận fail trước khi sửa (red)
  - [x] [web] Tạo `ApiClientError` trong `usfds-web/src/api/client.ts` (giữ `statusCode`, `details` từ `AxiosError`), bỏ `try/catch` nuốt lỗi ở `get/post/put/patch/delete`, throw `ApiClientError` trong `normalizeResponse` khi `success === false`
  - [x] [verify] Chạy `npx vitest run src/api/client.test.ts` trong `usfds-web`
- [x] **M2 — Migrate callers & partial-failure loads** (`usfds-web`): Toàn bộ API modules, hooks, components/pages tương thích với `apiClient` throw lỗi.
  - [x] [tests] Bổ sung test partial-failure (`ModelHubView.test.tsx`) và kiểm tra các test hiện có
  - [x] [web] Cập nhật các API modules (`datasetApi`, `detectionApi`, `docsDashboardApi`, `insightReportApi`, `investigationApi`, `storageApi`) và hooks (`useAuth`, `useDataset*`, `useModelLineage`, `useProjectMembers`, `useProjects`)
  - [x] [web] Cập nhật các components/pages kiểm tra `.success`/`.error` hoặc dùng `Promise.all` (`ModelHubView`, `TrainingWizardView`, `RuleDryRunWorkspace`, `DetectionJobWizardView`, `AdminUsersPage`, v.v.) sang `try/catch` và `Promise.allSettled`
  - [x] [verify] Chạy `npm run build` (`tsc -b && vite build`) và `./scripts/test.sh web`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-16 M1 done: `src/api/client.test.ts` 3 passed (3); notes: `ApiClientError` added in `client.ts` (left `types/api.ts` `ApiError` interface untouched).
- 26-11-16 M2 done: `npm run build` (0 errors), `npm run lint` (0 errors), `vitest run` 26 passed / 1 pre-existing MSW+undici blob failure in `DatasetHubView.test.tsx`; notes: `Promise.allSettled` & `try/catch` applied across partial-failure views and imperative components (`useAuth`, `ProfileModal`, `RuleCatalogView`, `RuleWorkspace`, `RuleVersionHistoryModal`, `AdminUsersPage`).

## 7. Review hotspots
- `usfds-web/src/api/client.ts:28-38,93-95,132-167` (M1): `ApiClientError` và việc bỏ `try/catch` nuốt lỗi ở `get/post/put/patch/delete` + throw trong `normalizeResponse` khi `success === false`; được cover bởi `src/api/client.test.ts`.
- `usfds-web/src/hooks/useAuth.tsx:25-93` (M2): `refreshMe`, `login`, `logout` bắt `ApiClientError` để fallback `local_auto`, trả `{ ok: false, error }`, và dọn token khi `logout` lỗi.
- `usfds-web/src/components/modules/model/ModelHubView.tsx:62-97` (M2): `Promise.allSettled` cho phép hiển thị partial data khi một số `listModelVersions` lỗi; được cover bởi `ModelHubView.test.tsx`.
- `usfds-web/src/components/modules/detection/DetectionJobWizardView.tsx:84-137` (M2): `Promise.allSettled` bỏ qua dataset/model bị lỗi khi load options cho wizard.

## 8. Open questions
- —
