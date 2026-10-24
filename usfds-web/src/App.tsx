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
	ProjectManagementPage,
	ProjectSettingsPage,
} from '@/pages';
import { ProjectProvider, useProject } from '@/hooks';
import { ProjectFormModal } from './components/modules/project_management/ProjectFormModal';
import type { AppModule } from '@/types';

const MODULE_ROUTE_MAP: Record<AppModule, string> = {
	'data-management': '/datasets',
	'model-management': '/models',
	'rule-management': '/rules',
	'detection': '/detection',
	'investigation': '/investigation',
	'insight-report': '/reports',
	'project-settings': '/settings',
};

function WorkspaceShell() {
	const location = useLocation();
	const navigate = useNavigate();
	const {
		projects,
		currentProject,
		isLoading,
		selectProject,
		openCreateModal,
	} = useProject();

	const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
	const [isOmnisearchOpen, setIsOmnisearchOpen] = useState(false);

	const activeModule: AppModule = useMemo(() => {
		const path = location.pathname;
		if (path.startsWith('/models')) {
			return 'model-management';
		}
		if (path.startsWith('/rules')) {
			return 'rule-management';
		}
		if (path.startsWith('/detection')) {
			return 'detection';
		}
		if (path.startsWith('/investigation')) {
			return 'investigation';
		}
		if (path.startsWith('/reports')) {
			return 'insight-report';
		}
		if (path.startsWith('/settings')) {
			return 'project-settings';
		}
		return 'data-management';
	}, [location.pathname]);

	const handleSelectModule = (mod: AppModule) => {
		const targetRoute = MODULE_ROUTE_MAP[mod] || '/datasets';
		navigate(targetRoute);
	};

	if (!isLoading && !currentProject) {
		return <Navigate to="/projects" replace />;
	}

	return (
		<div className="h-screen w-screen overflow-hidden flex flex-col bg-dark-950 text-slate-100 font-sans">
			{/* 1. Workspace Topbar */}
			<Topbar
				projects={projects}
				currentProject={currentProject}
				onSelectProject={selectProject}
				onCreateProjectClick={openCreateModal}
				onManageProjectsClick={() => navigate('/projects')}
				onOpenOmnisearch={() => setIsOmnisearchOpen(true)}
			/>

			{/* 2. Middle Core Shell: Module-based Sidebar + Main Content Viewport */}
			<div className="flex-1 flex overflow-hidden">
				<Sidebar
					activeModule={activeModule}
					onSelectModule={handleSelectModule}
					collapsed={sidebarCollapsed}
					onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
				/>

				<main className="flex-1 flex flex-col overflow-hidden bg-dark-950 relative">
					<Routes>
						<Route path="/datasets/*" element={<DataManagementPage />} />
						<Route path="/models/*" element={<ModelTrainingPage />} />
						<Route path="/rules/*" element={<RuleEnginePage />} />
						<Route path="/detection/*" element={<DetectionJobPage />} />
						<Route path="/investigation/*" element={<InvestigationPage />} />
						<Route path="/reports/*" element={<InsightReportPage />} />
						<Route path="/settings/*" element={<ProjectSettingsPage />} />
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

function AppRoutes() {
	const { isCreateModalOpen, closeCreateModal, createProject } = useProject();

	return (
		<>
			<Routes>
				{/* Standalone Project Management Portal (No Left Navigation Sidebar) */}
				<Route path="/projects/*" element={<ProjectManagementPage />} />

				{/* Default entry point goes to Project Selection / Management */}
				<Route path="/" element={<Navigate to="/projects" replace />} />

				{/* Project-scoped Workspace with Left Navigation Sidebar */}
				<Route path="/*" element={<WorkspaceShell />} />
			</Routes>

			{/* Global Create Project Modal */}
			<ProjectFormModal
				isOpen={isCreateModalOpen}
				onClose={closeCreateModal}
				onCreate={createProject}
			/>
		</>
	);
}

export function App() {
	return (
		<ProjectProvider>
			<AppRoutes />
		</ProjectProvider>
	);
}

export default App;
