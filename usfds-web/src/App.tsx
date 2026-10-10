import { useState } from 'react';
import { Topbar } from './components/layout/Topbar';
import { Sidebar } from './components/layout/Sidebar';
import { OmnisearchModal } from './components/layout/OmnisearchModal';
import { InspectorDrawer } from './components/layout/InspectorDrawer';
import { DataManagementModule } from './components/modules/DataManagementModule';
import { ModelTrainingModule } from './components/modules/ModelTrainingModule';
import { RuleEngineModule } from './components/modules/RuleEngineModule';
import { DetectionJobModule } from './components/modules/DetectionJobModule';
import { InvestigationModule } from './components/modules/InvestigationModule';
import { InsightReportModule } from './components/modules/InsightReportModule';
import type { AppModule, Project } from './types/navigation';

const MOCK_PROJECTS: Project[] = [
  { id: 'proj-ecom-2026', name: 'E-Commerce Fraud 2026', description: 'Real-time card & transaction fraud detection' },
  { id: 'proj-banking-aml', name: 'Banking AML & Wire Fraud', description: 'Anti-money laundering transaction surveillance' },
  { id: 'proj-crypto-risk', name: 'Crypto Wallet Risk Scoring', description: 'Blockchain transaction clustering & blacklists' }
];

export function App() {
  const [activeModule, setActiveModule] = useState<AppModule>('data-management');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isOmnisearchOpen, setIsOmnisearchOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(MOCK_PROJECTS[0]);
  
  // Inspector drawer state
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorItem, setInspectorItem] = useState<any>(null);
  const [inspectorTab, setInspectorTab] = useState('overview');

  const handleOpenInspector = (item: any) => {
    setInspectorItem(item);
    setInspectorOpen(true);
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-dark-950 text-slate-100 font-sans">
      {/* 1. Topbar (56px) - Project Switcher & Global Omnisearch */}
      <Topbar
        projects={MOCK_PROJECTS}
        currentProject={currentProject}
        onSelectProject={setCurrentProject}
        onOpenOmnisearch={() => setIsOmnisearchOpen(true)}
      />

      {/* 2. Middle Core Shell: Module-based Sidebar + Main Content Viewport */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar: Lists 6 System Modules */}
        <Sidebar
          activeModule={activeModule}
          onSelectModule={setActiveModule}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main Viewport: Render the selected module */}
        <main className="flex-1 flex flex-col overflow-hidden bg-dark-950 relative">
          {activeModule === 'data-management' && (
            <DataManagementModule onOpenInspector={handleOpenInspector} />
          )}

          {activeModule === 'model-management' && (
            <ModelTrainingModule />
          )}

          {activeModule === 'rule-management' && (
            <RuleEngineModule />
          )}

          {activeModule === 'detection' && (
            <DetectionJobModule />
          )}

          {activeModule === 'investigation' && (
            <InvestigationModule />
          )}

          {activeModule === 'insight-report' && (
            <InsightReportModule />
          )}
        </main>
      </div>

      {/* 3. Slide-over Inspector Drawer (Detail view) */}
      <InspectorDrawer
        isOpen={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        title={inspectorItem?.name || 'Artifact Inspector'}
        subtitle={`Artifact ID: ${inspectorItem?.id || 'N/A'}`}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'profiling', label: 'Profiling' },
          { id: 'lineage', label: 'Lineage' },
          { id: 'schema', label: 'Schema' }
        ]}
        activeTab={inspectorTab}
        onSelectTab={setInspectorTab}
        footerActions={
          <button
            onClick={() => setInspectorOpen(false)}
            className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-xs text-slate-300 transition"
          >
            Close
          </button>
        }
      >
        {inspectorItem && (
          <div className="space-y-4 font-mono text-xs">
            <div className="bg-dark-950 p-3 rounded-lg border border-dark-800 space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Pipeline Stage:</span>
                <span className="text-brand-400 font-bold">{inspectorItem.stage}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Rows:</span>
                <span className="text-slate-200">{inspectorItem.rows?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Feature Columns:</span>
                <span className="text-slate-200">{inspectorItem.features} columns</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-slate-400 uppercase font-sans">SHA-256 Checksum</span>
              <div className="p-2 rounded bg-dark-950 border border-dark-800 text-[11px] text-slate-300 break-all select-all">
                {inspectorItem.checksum}
              </div>
            </div>
          </div>
        )}
      </InspectorDrawer>

      {/* 4. Omnisearch Dialog (Ctrl+K) */}
      <OmnisearchModal
        isOpen={isOmnisearchOpen}
        onClose={() => setIsOmnisearchOpen(false)}
        onNavigateModule={(module) => {
          setActiveModule(module);
          setIsOmnisearchOpen(false);
        }}
      />
    </div>
  );
}

export default App;
