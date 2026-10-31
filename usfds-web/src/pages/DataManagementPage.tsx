import { Routes, Route } from 'react-router-dom';
import { DatasetHubView } from '../components/modules/data_management/DatasetHubView';
import { DatasetLineageExplorer } from '../components/modules/data_management/DatasetLineageExplorer';
import { DataPipelineWorkspace } from '../components/modules/data_management/DataPipelineWorkspace';

export function DataManagementPage() {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <Routes>
        <Route index element={<DatasetHubView />} />
        <Route path=":datasetId" element={<DatasetLineageExplorer />} />
        <Route path=":datasetId/workspace/:stepId" element={<DataPipelineWorkspace />} />
        <Route path=":datasetId/pipeline/:stepId" element={<DataPipelineWorkspace />} />
      </Routes>
    </div>
  );
}

export default DataManagementPage;
