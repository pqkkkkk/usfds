# 29/10/2026 <!-- [26-10-29] -->
- [x] Infinite loop in `DataPipelineWorkspace.tsx`, lead to can not route to any other pages.
```text
DataPipelineWorkspace.tsx:242
 Maximum update depth exceeded. This can happen when a component calls setState inside useEffect, but useEffect either doesn't have a dependency array, or one of the dependencies changes on every render.
onConfigChange	@	DataPipelineWorkspace.tsx:288
(anonymous)	@	SchemaMappingWorkspace.tsx:100
```
- [x] Still add `SUC-<number>` in UI, need to remove all
