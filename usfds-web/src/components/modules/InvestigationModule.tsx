import { NavLink, Route, Routes } from 'react-router-dom';
import { useProject } from '../../hooks/useProjects';
import { CaseQueueView, CaseWorkbenchView, PoliciesView } from './investigation/InvestigationViews';

export const InvestigationModule = () => {
	const { currentProjectId, currentProject, isLoading } = useProject();
	return <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-dark-950 text-slate-100">
		<header className="flex flex-wrap items-center justify-between gap-3 border-b border-dark-700 px-5 py-4"><h1 className="text-lg font-semibold">Investigation</h1><nav className="flex gap-4 text-sm" aria-label="Investigation views"><NavLink end to="/investigation" className={({ isActive }) => isActive ? 'text-blue-300' : 'text-slate-300'}>Case queue</NavLink><NavLink to="/investigation/policies" className={({ isActive }) => isActive ? 'text-blue-300' : 'text-slate-300'}>Policies</NavLink></nav></header>
		<main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-5">
			{isLoading ? <p role="status">Loading project...</p> : !currentProjectId ? <p className="text-sm text-slate-300">Select a project to view investigation cases.</p> : <Routes key={currentProjectId}>
				<Route index element={<CaseQueueView projectId={currentProjectId} readOnly={currentProject?.status === 'ARCHIVED'} />} />
				<Route path="cases/:caseId" element={<CaseWorkbenchView projectId={currentProjectId} readOnly={currentProject?.status === 'ARCHIVED'} />} />
				<Route path="policies" element={<PoliciesView projectId={currentProjectId} readOnly={currentProject?.status === 'ARCHIVED'} />} />
			</Routes>}
		</main>
	</div>;
};
