import { useState, useMemo } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Topbar, Sidebar, OmnisearchModal } from '@/components';
import { FeatureRouteGuard } from '@/components/layout/FeatureRouteGuard';
import {
	DataManagementPage,
	FeatureManagementPage,
	ModelTrainingPage,
	RuleEnginePage,
	DetectionJobPage,
	InvestigationPage,
	InsightReportPage,
	ProjectManagementPage,
	ProjectSettingsPage,
	LoginPage,
	AdminUsersPage,
	DocsDashboardPage,
} from '@/pages';
import { AuthProvider, ProjectProvider, ThemeProvider, useActorContext, useAuth, useProject } from '@/hooks';
import { getFirstAllowedModule } from '@/lib/feature-policy';
import { ProjectFormModal } from './components/modules/project_management/ProjectFormModal';
import type { AppModule } from '@/types';

const MODULE_ROUTE_MAP: Record<AppModule, string> = {
	'data-management': '/datasets',
	'feature-management': '/features',
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
	const { isLoading: authLoading } = useAuth();
	const { actor } = useActorContext(currentProject?.project_id);

	const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
	const [isOmnisearchOpen, setIsOmnisearchOpen] = useState(false);

	const defaultModule = useMemo(
		() => getFirstAllowedModule(actor, currentProject?.project_id),
		[actor, currentProject?.project_id]
	);
	const defaultRoute = defaultModule ? MODULE_ROUTE_MAP[defaultModule] : '/projects';

	const activeModule: AppModule = useMemo(() => {
		const path = location.pathname;
		if (path.startsWith('/features')) {
			return 'feature-management';
		}
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
		const targetRoute = MODULE_ROUTE_MAP[mod] || defaultRoute;
		navigate(targetRoute);
	};

	if (authLoading || isLoading) {
		return (
			<div className="h-screen w-screen flex items-center justify-center bg-dark-950 text-xs text-slate-400">
				Đang tải không gian làm việc...
			</div>
		);
	}

	if (!currentProject) {
		return <Navigate to="/projects" replace />;
	}

	const pid = currentProject.project_id;

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
						<Route
							path="/datasets/*"
							element={
								<FeatureRouteGuard feature="dataManagement" projectId={pid} fallbackPath={defaultRoute}>
									<DataManagementPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/features/*"
							element={
								<FeatureRouteGuard feature="featureManagement" projectId={pid} fallbackPath={defaultRoute}>
									<FeatureManagementPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/models/*"
							element={
								<FeatureRouteGuard feature="modelManagement" projectId={pid} fallbackPath={defaultRoute}>
									<ModelTrainingPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/rules/*"
							element={
								<FeatureRouteGuard feature="ruleManagement" projectId={pid} fallbackPath={defaultRoute}>
									<RuleEnginePage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/detection/*"
							element={
								<FeatureRouteGuard feature="detection" projectId={pid} fallbackPath={defaultRoute}>
									<DetectionJobPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/investigation/*"
							element={
								<FeatureRouteGuard feature="investigation" projectId={pid} fallbackPath={defaultRoute}>
									<InvestigationPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/reports/*"
							element={
								<FeatureRouteGuard feature="insightReport" projectId={pid} fallbackPath={defaultRoute}>
									<InsightReportPage />
								</FeatureRouteGuard>
							}
						/>
						<Route
							path="/settings/*"
							element={
								<FeatureRouteGuard feature="projectSettings" projectId={pid} fallbackPath={defaultRoute}>
									<ProjectSettingsPage />
								</FeatureRouteGuard>
							}
						/>
						<Route path="*" element={<Navigate to={defaultRoute} replace />} />
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
	const { authMode, isLoading, isAuthenticated } = useAuth();
	const location = useLocation();

	if (authMode === 'required' && !isLoading && !isAuthenticated && location.pathname !== '/login') {
		return <Navigate to="/login" replace />;
	}

	return (
		<>
			<Routes>
				<Route path="/login" element={<LoginPage />} />
				<Route
					path="/admin"
					element={
						<FeatureRouteGuard feature="adminUsers" fallbackPath="/projects">
							<AdminUsersPage />
						</FeatureRouteGuard>
					}
				/>
				<Route path="/admin/users" element={<Navigate to="/admin" replace />} />
				{/* Interactive Docs & Plan Review Dashboard */}
				<Route path="/__docs/*" element={<DocsDashboardPage />} />
				<Route path="/docs/*" element={<DocsDashboardPage />} />

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
		<ThemeProvider>
			<AuthProvider>
				<ProjectProvider>
					<AppRoutes />
				</ProjectProvider>
			</AuthProvider>
		</ThemeProvider>
	);
}

export default App;
