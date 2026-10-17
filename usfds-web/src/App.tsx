import { useState, useMemo } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Topbar, Sidebar, OmnisearchModal } from '@/components';
import {
  DataManagementPage,
  ModelTrainingPage,
  RuleEnginePage,
  DetectionJobPage,
  InvestigationPage,
  InsightReportPage,
} from '@/pages';
import type { AppModule, Project } from '@/types';

const MOCK_PROJECTS: Project[] = [
  { id: 'proj-ecom-2026', name: 'E-Commerce Fraud 2026', description: 'Real-time card & transaction fraud detection' },
  { id: 'proj-banking-aml', name: 'Banking AML & Wire Fraud', description: 'Anti-money laundering transaction surveillance' },
  { id: 'proj-crypto-risk', name: 'Crypto Wallet Risk Scoring', description: 'Blockchain transaction clustering & blacklists' }
];

const MODULE_ROUTE_MAP: Record<AppModule, string> = {
  'data-management': '/datasets',
  'model-management': '/models',
  'rule-management': '/rules',
  'detection': '/detection',
  'investigation': '/investigation',
  'insight-report': '/reports',
};

export function App() {
  const location = useLocation();
  const navigate = useNavigate();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isOmnisearchOpen, setIsOmnisearchOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(MOCK_PROJECTS[0]);

  // Determine active module based on current pathname
  const activeModule: AppModule = useMemo(() => {
    const path = location.pathname;
    if (path.startsWith('/models')) return 'model-management';
    if (path.startsWith('/rules')) return 'rule-management';
    if (path.startsWith('/detection')) return 'detection';
    if (path.startsWith('/investigation')) return 'investigation';
    if (path.startsWith('/reports')) return 'insight-report';
    return 'data-management';
  }, [location.pathname]);

  const handleSelectModule = (mod: AppModule) => {
    const targetRoute = MODULE_ROUTE_MAP[mod] || '/datasets';
    navigate(targetRoute);
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-dark-950 text-slate-100 font-sans">
      {/* 1. Topbar */}
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
          onSelectModule={handleSelectModule}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main Viewport: Routes */}
        <main className="flex-1 flex flex-col overflow-hidden bg-dark-950 relative">
          <Routes>
            <Route path="/datasets/*" element={<DataManagementPage />} />
            <Route path="/models/*" element={<ModelTrainingPage />} />
            <Route path="/rules/*" element={<RuleEnginePage />} />
            <Route path="/detection/*" element={<DetectionJobPage />} />
            <Route path="/investigation/*" element={<InvestigationPage />} />
            <Route path="/reports/*" element={<InsightReportPage />} />
            <Route path="/" element={<Navigate to="/datasets" replace />} />
            <Route path="*" element={<Navigate to="/datasets" replace />} />
          </Routes>
        </main>
      </div>

      {/* 3. Omnisearch Dialog (Ctrl+K) */}
      <OmnisearchModal
        isOpen={isOmnisearchOpen}
        onClose={() => setIsOmnisearchOpen(false)}
        onNavigateModule={(module) => {
          handleSelectModule(module);
          setIsOmnisearchOpen(false);
        }}
      />
    </div>
  );
}

export default App;
