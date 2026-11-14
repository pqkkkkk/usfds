import { NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { Briefcase, ShieldAlert } from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';
import { useProject } from '../../hooks/useProjects';
import { CaseQueueView, CaseWorkbenchView, PoliciesView } from './investigation/InvestigationViews';

export const InvestigationModule = () => {
	const { currentProjectId, currentProject, isLoading } = useProject();
	const location = useLocation();
	const isPoliciesView = location.pathname.startsWith('/investigation/policies');
	const isWorkbenchView = location.pathname.includes('/investigation/cases/');

	const breadcrumbs = [
		{ label: 'Investigation', href: '/investigation' },
		...(isPoliciesView
			? [{ label: 'Policies & Watchlists' }]
			: isWorkbenchView
				? [{ label: 'Case Workbench' }]
				: [{ label: 'Case Queue' }]),
	];

	return (
		<div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-dark-950 text-slate-100">
			<PageHeader
				title="Fraud Investigation & Case Management"
				subtitle={
					currentProject
						? `Điều tra hồ sơ giao dịch nghi vấn, đối chiếu chuẩn hành vi lịch sử và phản hồi chính sách cho dự án "${currentProject.project_name}"`
						: 'Quản lý hàng đợi hồ sơ điều tra, phân tích bằng chứng AI/Rule và cập nhật danh sách chặn thực thể'
				}
				breadcrumbs={breadcrumbs}
				actions={
					<nav
						className="inline-flex items-center rounded-lg border border-dark-700 bg-dark-900 p-1 text-xs"
						aria-label="Investigation views"
					>
						<NavLink
							end
							to="/investigation"
							className={({ isActive }) =>
								`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors ${isActive || isWorkbenchView
									? 'bg-brand-600 text-white shadow-sm'
									: 'text-slate-300 hover:text-slate-100'
								}`
							}
						>
							<Briefcase size={14} aria-hidden="true" />
							<span>Case Queue</span>
						</NavLink>
						<NavLink
							to="/investigation/policies"
							className={({ isActive }) =>
								`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors ${isActive
									? 'bg-brand-600 text-white shadow-sm'
									: 'text-slate-300 hover:text-slate-100'
								}`
							}
						>
							<ShieldAlert size={14} aria-hidden="true" />
							<span>Policies & Watchlists</span>
						</NavLink>
					</nav>
				}
			/>

			<main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
				{isLoading ? (
					<div role="status" className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Loading project context...
					</div>
				) : !currentProjectId ? (
					<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Select a project from the top navigation bar to view investigation cases.
					</div>
				) : (
					<Routes key={currentProjectId}>
						<Route
							index
							element={
								<CaseQueueView
									projectId={currentProjectId}
									readOnly={currentProject?.status === 'ARCHIVED'}
								/>
							}
						/>
						<Route
							path="cases/:caseId"
							element={
								<CaseWorkbenchView
									projectId={currentProjectId}
									readOnly={currentProject?.status === 'ARCHIVED'}
								/>
							}
						/>
						<Route
							path="policies"
							element={
								<PoliciesView
									projectId={currentProjectId}
									readOnly={currentProject?.status === 'ARCHIVED'}
								/>
							}
						/>
					</Routes>
				)}
			</main>
		</div>
	);
};
