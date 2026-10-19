import { Routes, Route } from 'react-router-dom';
import { RuleCatalogView } from '../components/modules/rule/RuleCatalogView';
import { RuleWorkspace } from '../components/modules/rule/RuleWorkspace';

export function RuleEnginePage() {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <Routes>
        <Route index element={<RuleCatalogView />} />
        <Route path="new" element={<RuleWorkspace />} />
        <Route path="new/:stepId" element={<RuleWorkspace />} />
        <Route path=":ruleId" element={<RuleWorkspace />} />
        <Route path=":ruleId/:stepId" element={<RuleWorkspace />} />
      </Routes>
    </div>
  );
}

export default RuleEnginePage;
