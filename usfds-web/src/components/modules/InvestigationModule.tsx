import { NavLink, Route, Routes, useLocation, useSearchParams } from 'react-router-dom';
import { Briefcase, Network, ShieldAlert } from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';
import { useProject } from '../../hooks/useProjects';
import type { EntityType } from '../../types/investigation';
import {
	CaseQueueView,
	CaseWorkbenchView,
	NetworkGraphExplorer,
	PoliciesView,
} from './investigation/InvestigationViews';

const VALID_ENTITY_TYPES: EntityType[] = ['USER_ID', 'CARD_ID', 'DEVICE_ID', 'IP_ADDRESS', 'MERCHANT_ID'];

function NetworkRouteView({ projectId, readOnly }: { projectId: string; readOnly: boolean }) {
	const [searchParams] = useSearchParams();
	const rawSeedType = (searchParams.get('seed_type') || 'USER_ID').toUpperCase() as EntityType;
	const seedType = VALID_ENTITY_TYPES.includes(rawSeedType) ? rawSeedType : 'USER_ID';
	const seedValue = searchParams.get('seed_value') || '';
	const caseId = searchParams.get('case_id');

	return (
		<NetworkGraphExplorer
			key={`${projectId}:${seedType}:${seedValue}:${caseId ?? ''}`}
			projectId={projectId}
			readOnly={readOnly}
			initialSeedType={seedType}
			initialSeedValue={seedValue}
			caseId={caseId}
		/>
	);
}

export const InvestigationModule = () => {
	const { currentProjectId, currentProject, isLoading } = useProject();
	const location = useLocation();
	const isPoliciesView = location.pathname.startsWith('/investigation/policies');
	const isNetworkView = location.pathname.startsWith('/investigation/network');
	const isWorkbenchView = location.pathname.includes('/investigation/cases/');

	const breadcrumbs = [
		{ label: 'Điều tra', href: '/investigation' },
		...(isPoliciesView
			? [{ label: 'Chính sách & danh sách theo dõi' }]
			: isNetworkView
				? [{ label: 'Khám phá mạng lưới' }]
				: isWorkbenchView
					? [{ label: 'Không gian làm việc hồ sơ' }]
					: [{ label: 'Hàng đợi hồ sơ' }]),
	];

	return (
		<div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-dark-950 text-slate-100">
			<PageHeader
				title="Điều tra gian lận & quản lý hồ sơ"
				subtitle={
					currentProject
						? `Điều tra hồ sơ giao dịch nghi vấn, đối chiếu chuẩn hành vi lịch sử và phản hồi chính sách cho dự án "${currentProject.project_name}"`
						: 'Quản lý hàng đợi hồ sơ điều tra, phân tích bằng chứng AI/luật và cập nhật danh sách chặn thực thể'
				}
				breadcrumbs={breadcrumbs}
				actions={
					<nav
						className="inline-flex items-center rounded-lg border border-dark-700 bg-dark-900 p-1 text-xs"
						aria-label="Chế độ xem điều tra"
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
							<span>Hàng đợi hồ sơ</span>
						</NavLink>
						<NavLink
							to="/investigation/network"
							className={({ isActive }) =>
								`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors ${isActive
									? 'bg-brand-600 text-white shadow-sm'
									: 'text-slate-300 hover:text-slate-100'
								}`
							}
						>
							<Network size={14} aria-hidden="true" />
							<span>Khám phá mạng lưới</span>
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
							<span>Chính sách & danh sách theo dõi</span>
						</NavLink>
					</nav>
				}
			/>

			<main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
				{isLoading ? (
					<div role="status" className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Đang tải ngữ cảnh dự án...
					</div>
				) : !currentProjectId ? (
					<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Chọn một dự án trên thanh điều hướng phía trên để xem hồ sơ điều tra.
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
							path="network"
							element={
								<NetworkRouteView
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
