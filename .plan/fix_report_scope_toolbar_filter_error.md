# Fix Plan: `detectionJobs.filter is not a function` in ReportScopeToolbar

## 1. Root Cause Analysis
- **Location**: `usfds-web/src/components/modules/reports/ReportScopeToolbar.tsx:18:38`
- **Issue**:
  - `ReportScopeToolbar` calls `detectionJobs.filter(...)` assuming `detectionJobs` is always a raw array of `DetectionJobResponse[]`.
  - In `InsightReportModule.tsx`, the query uses `queryKey: ['detection-jobs', currentProjectId]`.
  - However, `DetectionJobsHubView.tsx` also queries the exact same `queryKey: ['detection-jobs', projectId]` returning `ApiResponse<DetectionJobResponse[]>` (`{ success: true, data: [...] }`).
  - When switching between Detection Jobs and Insight & Reports, TanStack Query cache serves the cached `ApiResponse` object.
  - In `InsightReportModule.tsx`, `detectionJobsRes || []` evaluates to the object `{ success: true, data: [...] }`, which has no `.filter` method, triggering `Uncaught TypeError: detectionJobs.filter is not a function`.

## 2. Proposed Changes
1. **`ReportScopeToolbar.tsx`**:
   - Defensively extract the jobs list:
     ```ts
     const jobsList = Array.isArray(detectionJobs)
       ? detectionJobs
       : Array.isArray((detectionJobs as any)?.data)
         ? (detectionJobs as any).data
         : [];
     const completedJobs = jobsList.filter((j) => j.status === 'COMPLETED');
     ```
   - Use `jobsList` across the component to guarantee no runtime crash even if passed invalid/wrapped objects.
2. **`InsightReportModule.tsx`**:
   - Align queryFn with `detectionApi.listJobs({ projectId: currentProjectId! })`.
   - Memoize and normalize `detectionJobs`: extract `Array.isArray(detectionJobsRes) ? detectionJobsRes : (detectionJobsRes?.data || [])`.
   - Pass normalized array to `<ReportScopeToolbar detectionJobs={detectionJobsList} ... />`.

## 3. Verifiable Success Criteria
- [ ] Build passes cleanly with `npm run build` (`tsc -b && vite build`) in `usfds-web`.
- [ ] Lint check passes with `npm run lint` in `usfds-web`.
- [ ] Runtime resilience: `ReportScopeToolbar` handles array, `ApiResponse` object, `undefined`, and `null` without throwing `TypeError`.

