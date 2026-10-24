# Plan: Project Management Use Case Specification & Front-End Implementation

## 1. Context & Facts
- **Backend APIs (`usfds-server`)**: Already implemented in `usfds-server/src/usfds_server/routers/project_router.py` (`/api/v1/projects`):
	- `POST /api/v1/projects`: Create project (`project_name`, `user_id`, `description`).
	- `GET /api/v1/projects`: List projects with optional `user_id`, `status` (`ACTIVE` | `ARCHIVED`), `search`, returning stats (`datasets_count`, `rules_count`, `detection_jobs_count`).
	- `GET /api/v1/projects/{project_id}`: Get project details including `is_schema_locked`, `base_dataset_id`, `raw_schema`.
	- `PATCH /api/v1/projects/{project_id}`: Update `project_name`, `description`, `status`.
	- `POST /api/v1/projects/{project_id}/schema/reset`: Reset/unlock `raw_schema` (`BR-PM-03`).
	- `DELETE /api/v1/projects/{project_id}`: Delete project with active-workload guard (`BR-PM-08`).
- **Frontend State (`usfds-web`)**:
	- `App.tsx` currently uses `MOCK_PROJECTS` and local state without backend integration.
	- Modules (`DatasetHubView`, `ImportDatasetModal`, `RuleCatalogView`) currently use hardcoded or undefined `project_id` instead of active project context.

## 2. Proposed Execution Steps
1. **Use Case Specification (`docs/features/project_management/suc-spec.md`)**:
	- Document Project Management SUCs covering: Create Project, List & Switch Active Project, View Project & Locked RAW Schema, Update/Archive Project, Reset RAW Schema (`BR-PM-03`), and Delete Project (`BR-PM-08`).
	- Append `[26-10-24]` modification tag upon user approval.
2. **API & Types Layer (`usfds-web`)**:
	- Create `usfds-web/src/types/project.ts` matching `ProjectResponse`, `CreateProjectRequest`, `UpdateProjectRequest`, and `ProjectRawSchema`.
	- Create `usfds-web/src/api/projectApi.ts` wrapping `/v1/projects` endpoints and export in `usfds-web/src/api/index.ts`.
3. **Global Project Context & Hook (`usfds-web`)**:
	- Create `ProjectContext` / `useProjects` hook (TanStack Query + `localStorage` persistence for active `project_id`) so switching projects in `Topbar` automatically refreshes and scopes Datasets, Rules, Models, and Detection Jobs.
4. **Project Management UI (`usfds-web`)**:
	- Separate `/projects` into a standalone Project Portal layout (no Left Navigation Sidebar). Clicking a project selects it as the active workspace and navigates into `/datasets` (the main Workspace Shell with Left Navigation).
	- Replace `HashRouter` with `BrowserRouter` in `src/main.tsx` (retaining `HashRouter` fallback only for `file:` protocol) to eliminate `#/` in browser URLs.
	- Update `Topbar.tsx` project selector in the Workspace Shell to switch active project or return to `/projects`.
	- Build Project Management UI (Project catalog/settings, Create/Edit modal, Locked `RAW` Schema inspector table with `Reset Schema` action per `BR-PM-03`, Archive/Delete actions per `BR-PM-08`).
	- Wire active `project_id` into `DatasetHubView`, `ImportDatasetModal`, and `RuleCatalogView`.
5. **Verification**:
	- Add unit/integration tripwire test for project API/context flow and verify TypeScript build (`npm run build` / `tsc -b`).

## 3. Success Criteria
- [x] `docs/features/project_management/suc-spec.md` approved and created with `[26-10-24]` timestamp.
- [x] `usfds-web` fetches real projects from `/api/v1/projects` instead of `MOCK_PROJECTS`.
- [x] Users can create, edit, archive/unarchive, delete projects, and inspect/reset `raw_schema` from the UI.
- [x] Switching the active project in `Topbar` propagates `project_id` to Data Management and Rule Management views.
- [x] `usfds-web` passes TypeScript typecheck and build with zero errors.
