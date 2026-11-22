import React, { useCallback, useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
	Search,
	Plus,
	Edit,
	Trash2,
	History,
	RefreshCw,
	Play,
	AlertTriangle,
	Lock,
	Unlock,
	X,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { OwnerBadge } from '../../common/OwnerBadge';
import type { RuleResponse, RuleStatus } from '../../../types/rule';
import { ruleApi } from '../../../api/ruleApi';
import { useProject } from '../../../hooks/useProjects';
import { useActorContext } from '@/hooks/useActorContext';
import { RuleVersionHistoryModal } from './RuleVersionHistoryModal';

const FALLBACK_PROJECT_ID = '11111111-1111-1111-1111-111111111111';

export const RuleCatalogView: React.FC = () => {
	const navigate = useNavigate();
	const { currentProject, currentProjectId, refetchProjects } = useProject();
	const effectiveProjectId = currentProjectId || FALLBACK_PROJECT_ID;
	const { features, canAccessRecord } = useActorContext(currentProjectId);
	const canCreateRule = features.createRule.allowed;
	const [rules, setRules] = useState<RuleResponse[]>([]);
	const [nextCursor, setNextCursor] = useState<string | null>(null);
	const [loadingMore, setLoadingMore] = useState(false);
	const [loading, setLoading] = useState(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const [searchTerm, setSearchTerm] = useState('');
	const [statusFilter, setStatusFilter] = useState<'ALL' | RuleStatus>('ALL');

	// Modal version
	const [inspectingRule, setInspectingRule] = useState<RuleResponse | null>(null);
	const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);

	const fetchRules = useCallback(async () => {
		setLoading(true);
		setErrorMsg(null);
		try {
			const res = await ruleApi.listRules(effectiveProjectId);
			setRules(res.data?.items || []);
			setNextCursor(res.data?.nextCursor ?? null);
		} catch (err: any) {
			setErrorMsg(err?.message || 'Không thể tải danh sách quy tắc từ máy chủ.');
		} finally {
			setLoading(false);
		}
	}, [effectiveProjectId]);

	const handleLoadMore = async () => {
		if (!nextCursor || loadingMore) return;
		setLoadingMore(true);
		try {
			const res = await ruleApi.listRules(effectiveProjectId, undefined, { cursor: nextCursor });
			setRules((prev) => [...prev, ...(res.data?.items || [])]);
			setNextCursor(res.data?.nextCursor ?? null);
		} catch (err: any) {
			setErrorMsg(err?.message || 'Không thể tải thêm quy tắc.');
		} finally {
			setLoadingMore(false);
		}
	};

	useEffect(() => {
		fetchRules();
	}, [fetchRules]);

	const handleToggleStatus = async (ruleId: string, currentStatus: RuleStatus) => {
		setErrorMsg(null);
		const nextStatus: RuleStatus = currentStatus === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
		try {
			const res = await ruleApi.setRuleStatus(ruleId, nextStatus);
			if (res.data) {
				setRules((prev) => prev.map((r) => (r.rule_id === ruleId ? res.data : r)));
				refetchProjects();
			}
		} catch (err: any) {
			setErrorMsg(
				err?.message ||
					`Không thể chuyển trạng thái quy tắc sang ${nextStatus}. Vui lòng kiểm tra lược đồ thô của dự án.`
			);
		}
	};

	const handleDeleteRule = async (ruleId: string) => {
		if (!window.confirm('Bạn có chắc chắn muốn xóa quy tắc nghiệp vụ này cùng lịch sử phiên bản?')) {
			return;
		}
		setErrorMsg(null);
		try {
			await ruleApi.deleteRule(ruleId);
			setRules((prev) => prev.filter((r) => r.rule_id !== ruleId));
			refetchProjects();
		} catch (err: any) {
			setErrorMsg(err?.message || 'Không thể xóa quy tắc.');
		}
	};

	const handleOpenVersions = (rule: RuleResponse) => {
		setInspectingRule(rule);
		setIsVersionModalOpen(true);
	};

	const filteredRules = useMemo(() => {
		return rules.filter((rule) => {
			const matchesSearch =
				rule.rule_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
				rule.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
				(rule.description || '').toLowerCase().includes(searchTerm.toLowerCase());

			const matchesStatus = statusFilter === 'ALL' || rule.status === statusFilter;
			return matchesSearch && matchesStatus;
		});
	}, [rules, searchTerm, statusFilter]);

	const activeCount = rules.filter((r) => r.status === 'ACTIVE').length;
	const draftCount = rules.filter((r) => r.status === 'DRAFT').length;
	const inactiveCount = rules.filter((r) => r.status === 'INACTIVE').length;
	const isSchemaLocked = Boolean(currentProject?.is_schema_locked);
	const rawColCount = currentProject?.raw_schema?.columns
		? Object.keys(currentProject.raw_schema.columns).length
		: 0;

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			{/* 1. Common Page Header */}
			<PageHeader
				title="Quản lý luật"
				breadcrumbs={[{ label: 'Quản lý luật' }]}
				actions={
					<div className="flex items-center gap-2.5">
						<span
							className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-mono border ${
								isSchemaLocked
									? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
									: 'bg-amber-950/30 border-amber-500/40 text-amber-300'
							}`}
							title={
								isSchemaLocked
									? `Dự án đã khóa lược đồ thô (${rawColCount} cột)`
									: 'Dự án chưa khóa lược đồ thô (chưa tải lên tập dữ liệu đầu tiên)'
							}
						>
							{isSchemaLocked ? (
								<>
									<Lock className="w-3 h-3" />
									<span>Lược đồ thô: {rawColCount} cột</span>
								</>
							) : (
								<>
									<Unlock className="w-3 h-3" />
									<span>Lược đồ thô: Chưa khóa</span>
								</>
							)}
						</span>

						<button
							type="button"
							onClick={fetchRules}
							disabled={loading}
							className="p-2 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition cursor-pointer"
							title="Làm mới danh sách"
						>
							<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-brand-400' : ''}`} />
						</button>

						{canCreateRule && (
							<button
								type="button"
								onClick={() => navigate('/rules/new')}
								className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
							>
								<Plus className="w-4 h-4" />
								<span>Luật nghiệp vụ mới</span>
							</button>
						)}
					</div>
				}
			/>

			{/* 2. Main Content Viewport */}
			<div className="flex-1 p-6 space-y-5 overflow-y-auto">
				{/* Error Notice */}
				{errorMsg && (
					<div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/50 text-red-300 text-xs flex items-start justify-between gap-3">
						<div className="flex items-start gap-2.5">
							<AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
							<span className="font-mono">{errorMsg}</span>
						</div>
						<button
							type="button"
							onClick={() => setErrorMsg(null)}
							className="text-red-400 hover:text-red-200 cursor-pointer"
						>
							<X className="w-4 h-4" />
						</button>
					</div>
				)}

				{/* Search & Filter Bar */}
				<div className="flex flex-wrap items-center justify-between gap-3">
					{/* Search */}
					<div className="relative w-80">
						<input
							type="text"
							value={searchTerm}
							onChange={(e) => setSearchTerm(e.target.value)}
							placeholder="Tìm theo mã rule, tên hoặc mô tả..."
							className="w-full bg-dark-900 border border-slate-800 focus:border-brand-500 text-slate-200 text-xs rounded-lg pl-9 pr-3 py-2 focus:outline-none placeholder-slate-500"
						/>
						<Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
					</div>

					{/* Filter Pills */}
					<div className="flex items-center gap-1.5 bg-dark-900 p-1 rounded-lg border border-slate-800">
						<button
							type="button"
							onClick={() => setStatusFilter('ALL')}
							className={`px-3 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer ${
								statusFilter === 'ALL'
									? 'bg-brand-600 text-white shadow-sm'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							ALL ({rules.length})
						</button>
						<button
							type="button"
							onClick={() => setStatusFilter('ACTIVE')}
							className={`px-3 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer ${
								statusFilter === 'ACTIVE'
									? 'bg-emerald-600 text-white shadow-sm'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							ACTIVE ({activeCount})
						</button>
						<button
							type="button"
							onClick={() => setStatusFilter('DRAFT')}
							className={`px-3 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer ${
								statusFilter === 'DRAFT'
									? 'bg-dark-700 text-slate-100 shadow-sm'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							DRAFT ({draftCount})
						</button>
						<button
							type="button"
							onClick={() => setStatusFilter('INACTIVE')}
							className={`px-3 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer ${
								statusFilter === 'INACTIVE'
									? 'bg-red-800 text-white shadow-sm'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							INACTIVE ({inactiveCount})
						</button>
					</div>
				</div>

				{/* Rules Table */}
				<div className="bg-dark-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
					<div className="overflow-x-auto">
						<table className="w-full text-left text-xs">
							<thead className="bg-dark-950/80 text-[11px] font-mono uppercase tracking-wider text-slate-400 border-b border-slate-800">
								<tr>
									<th className="py-3 px-4">Rule Code &amp; Title</th>
									<th className="py-3 px-4">Action</th>
									<th className="py-3 px-4">Chủ sở hữu</th>
									<th className="py-3 px-4">Updated At</th>
									<th className="py-3 px-4">Version</th>
									<th className="py-3 px-4 text-center">Status</th>
									<th className="py-3 px-4 text-right">Thao tác</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-slate-800/60 text-slate-300">
								{loading ? (
									<tr>
										<td colSpan={7} className="py-12 text-center text-slate-500 font-mono">
											Đang nạp danh sách rules từ project...
										</td>
									</tr>
								) : filteredRules.length === 0 ? (
									<tr>
										<td colSpan={7} className="py-12 text-center text-slate-500 font-mono">
											{rules.length === 0
												? 'Chưa có quy tắc nghiệp vụ nào trong dự án này. Nhấn "+ Luật nghiệp vụ mới" để khởi tạo.'
												: 'Không tìm thấy rule nào phù hợp với bộ lọc.'}
										</td>
									</tr>
								) : (
									filteredRules.map((rule) => {
										const action = rule.current_version?.action || 'REVIEW';
										const versionNum = rule.current_version?.version_number || 1;
										const canDryRunRule = canAccessRecord('dryRunRule', rule.user_id);
										const canUpdateRule = canAccessRecord('updateRule', rule.user_id);
										const canDeleteRule = canAccessRecord('deleteRule', rule.user_id);
										const canDeployRule = canAccessRecord('deployRule', rule.user_id);
										const canUndeployRule = canAccessRecord('undeployRule', rule.user_id);

										return (
											<tr
												key={rule.rule_id}
												className="hover:bg-dark-850/50 transition-colors group"
											>
												{/* Code & Title */}
												<td className="py-3.5 px-4">
													<div className="flex items-start gap-2.5">
														<span className="font-mono font-bold text-brand-400 text-xs px-2 py-0.5 rounded bg-brand-950 border border-brand-800/80">
															{rule.rule_code}
														</span>
														<div>
															<button
																type="button"
																onClick={() => navigate(`/rules/${rule.rule_id}`)}
																className="font-semibold text-slate-100 hover:text-brand-300 transition-colors text-left cursor-pointer"
															>
																{rule.name}
															</button>
															<p className="text-[11px] text-slate-400 line-clamp-1 max-w-lg mt-0.5">
																{rule.description}
															</p>
														</div>
													</div>
												</td>

												{/* Action */}
												<td className="py-3.5 px-4">
													<span
														className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold font-mono border ${
															action === 'REVIEW'
																? 'bg-amber-950/40 text-amber-300 border-amber-600/40'
																: action === 'REJECT'
																	? 'bg-red-950/40 text-red-300 border-red-600/40'
																	: 'bg-emerald-950/40 text-emerald-300 border-emerald-600/40'
														}`}
													>
														{action}
													</span>
												</td>

												{/* Chủ sở hữu */}
												<td className="py-3.5 px-4">
													<OwnerBadge owner={rule.owner} userId={rule.user_id} />
												</td>

												{/* Updated At */}
												<td className="py-3.5 px-4 font-mono text-slate-400 text-[11px]">
													{rule.updated_at
														? new Date(rule.updated_at).toLocaleString()
														: '—'}
												</td>

												{/* Version */}
												<td className="py-3.5 px-4">
													<button
														type="button"
														onClick={() => handleOpenVersions(rule)}
														className="font-mono text-[10px] px-2 py-0.5 rounded bg-dark-950 border border-slate-800 text-slate-400 hover:text-brand-300 hover:border-brand-500 transition-colors flex items-center gap-1 cursor-pointer"
														title="Xem lịch sử phiên bản"
													>
														<History className="w-2.5 h-2.5" />
														<span>v{versionNum}</span>
													</button>
												</td>

												{/* Status Toggle Switch */}
												<td className="py-3.5 px-4 text-center">
													{(rule.status === 'ACTIVE' ? canUndeployRule : canDeployRule) ? (
														<button
															type="button"
															onClick={() => handleToggleStatus(rule.rule_id, rule.status)}
															title="Nhấn để chuyển đổi trạng thái ACTIVE / INACTIVE"
															className={`px-2.5 py-1 rounded-full text-[10px] font-bold font-mono border transition-all cursor-pointer ${
																rule.status === 'ACTIVE'
																	? 'bg-emerald-950/40 text-emerald-400 border-emerald-600/60 shadow-[0_0_8px_rgba(16,185,129,0.2)]'
																	: rule.status === 'DRAFT'
																		? 'bg-slate-800/80 text-slate-400 border-slate-700 hover:border-emerald-500/50'
																		: 'bg-red-950/40 text-red-400 border-red-600/50'
															}`}
														>
															{rule.status}
														</button>
													) : (
														<span
															className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold font-mono border ${
																rule.status === 'ACTIVE'
																	? 'bg-emerald-950/40 text-emerald-400 border-emerald-600/60'
																	: rule.status === 'DRAFT'
																		? 'bg-slate-800/80 text-slate-400 border-slate-700'
																		: 'bg-red-950/40 text-red-400 border-red-600/50'
															}`}
														>
															{rule.status}
														</span>
													)}
												</td>

												{/* Operations */}
												<td className="py-3.5 px-4 text-right">
													<div className="flex items-center justify-end gap-1.5">
														{canDryRunRule && (
															<button
																type="button"
																onClick={() => navigate(`/rules/${rule.rule_id}/step-dryrun`)}
																className="p-1.5 rounded hover:bg-emerald-950/40 text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer"
																title="Chạy thử (dry run) trên dữ liệu lịch sử"
															>
																<Play className="w-3.5 h-3.5" />
															</button>
														)}
														{canUpdateRule && (
															<button
																type="button"
																onClick={() => navigate(`/rules/${rule.rule_id}/step-builder`)}
																className="p-1.5 rounded hover:bg-dark-800 text-slate-400 hover:text-brand-300 transition-colors cursor-pointer"
																title="Chỉnh sửa trong trình thiết kế luật"
															>
																<Edit className="w-3.5 h-3.5" />
															</button>
														)}
														{canDeleteRule && (
															<button
																type="button"
																onClick={() => handleDeleteRule(rule.rule_id)}
																className="p-1.5 rounded hover:bg-red-950/30 text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
																title="Xóa luật"
															>
																<Trash2 className="w-3.5 h-3.5" />
															</button>
														)}
													</div>
												</td>
											</tr>
										);
									})
								)}
							</tbody>
						</table>
					</div>
					{nextCursor && (
						<div className="p-3 border-t border-slate-800 flex justify-center bg-dark-950/40">
							<button
								type="button"
								disabled={loadingMore}
								onClick={() => void handleLoadMore()}
								className="px-4 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-slate-700 text-xs text-slate-200 font-medium disabled:opacity-50"
							>
								{loadingMore ? 'Đang tải...' : 'Tải thêm'}
							</button>
						</div>
					)}
				</div>
			</div>

			{/* Version History Modal */}
			<RuleVersionHistoryModal
				rule={inspectingRule}
				isOpen={isVersionModalOpen}
				onClose={() => setIsVersionModalOpen(false)}
				onRestoreVersion={() => {
					if (inspectingRule) {
						navigate(`/rules/${inspectingRule.rule_id}`);
					}
				}}
			/>
		</div>
	);
};
