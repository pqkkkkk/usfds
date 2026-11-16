import { Routes, Route } from 'react-router-dom';
import { RuleCatalogView } from '../components/modules/rule/RuleCatalogView';
import { RuleWorkspace } from '../components/modules/rule/RuleWorkspace';
import { FeatureRouteGuard } from '@/components/layout/FeatureRouteGuard';
import { useProject } from '@/hooks';

export function RuleEnginePage() {
  const { currentProjectId } = useProject();
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <Routes>
        <Route index element={<RuleCatalogView />} />
        <Route
          path="new"
          element={
            <FeatureRouteGuard feature="createRule" projectId={currentProjectId} fallbackPath="/rules">
              <RuleWorkspace />
            </FeatureRouteGuard>
          }
        />
        <Route
          path="new/:stepId"
          element={
            <FeatureRouteGuard feature="createRule" projectId={currentProjectId} fallbackPath="/rules">
              <RuleWorkspace />
            </FeatureRouteGuard>
          }
        />
        <Route path=":ruleId" element={<RuleWorkspace />} />
        <Route path=":ruleId/:stepId" element={<RuleWorkspace />} />
      </Routes>
    </div>
  );
}

export default RuleEnginePage;
