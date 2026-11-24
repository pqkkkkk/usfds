import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
	AlertTriangle,
	Ban,
	CheckCircle2,
	FolderPlus,
	GitFork,
	Network,
	Search,
	ShieldAlert,
} from 'lucide-react';
import { useActorContext } from '@/hooks/useActorContext';
import { useNetworkGraph } from '@/hooks/useNetworkGraph';
import type { EntityType } from '@/types/investigation';
import { CytoscapeCanvas } from './CytoscapeCanvas';
import {
	BUTTON_DANGER_CLASS,
	BUTTON_PRIMARY_CLASS,
	BUTTON_SECONDARY_CLASS,
	ENTITY_TYPES,
	ErrorNotice,
	INPUT_CLASS,
	SectionCard,
	StatusBadge,
	formatCurrencyAmount,
	formatDateTime,
	formatNumber,
} from './investigationShared';

const SECONDARY_ENTITY_FILTERS: { type: EntityType; label: string }[] = [
	{ type: 'DEVICE_ID', label: 'Thiết bị' },
	{ type: 'IP_ADDRESS', label: 'Địa chỉ IP' },
	{ type: 'CARD_ID', label: 'Thẻ' },
	{ type: 'MERCHANT_ID', label: 'Đơn vị chấp nhận' },
];

export function NetworkGraphExplorer({
	projectId,
	readOnly,
	initialSeedType = 'USER_ID',
	initialSeedValue = '',
	caseId = null,
	compact = false,
}: {
	projectId: string;
	readOnly: boolean;
	initialSeedType?: EntityType;
	initialSeedValue?: string;
	caseId?: string | null;
	compact?: boolean;
}) {
	const { features } = useActorContext(projectId);
	const canManageBlacklist = features.manageBlacklist.allowed && !readOnly;
	const canCreateCase = features.sendToInvestigation.allowed && !readOnly;

	const [bulkReason, setBulkReason] = useState('');

	const {
		seedType,
		setSeedType,
		seedValue,
		setSeedValue,
		activeSeed,
		searchSeed,
		hops,
		setHops,
		days,
		setDays,
		entityTypes,
		toggleEntityType,
		hideSuperNodes,
		setHideSuperNodes,
		hubsQuery,
		subgraphQuery,
		edgeTransactionsQuery,
		nodes,
		edges,
		patterns,
		notice,
		actionFeedback,
		selectedNodeIds,
		toggleNodeSelection,
		focusedNodeId,
		setFocusedNodeId,
		selectedEdge,
		selectEdge,
		selectedEdgeTxKeys,
		toggleEdgeTransaction,
		expandNode,
		isExpanding,
		expandError,
		bulkBlacklist,
		isBulkBlacklisting,
		bulkBlacklistError,
		bulkCaseIntake,
		isBulkIntaking,
		bulkCaseIntakeError,
	} = useNetworkGraph({
		projectId,
		initialSeedType,
		initialSeedValue,
		caseId,
	});

	const focusedNode = nodes.find((n) => n.id === focusedNodeId) ?? null;

	const handleBulkBlacklist = async () => {
		if (selectedNodeIds.length === 0 || bulkReason.trim().length < 10) {
			return;
		}
		const entities = nodes
			.filter((n) => selectedNodeIds.includes(n.id))
			.map((n) => ({ entity_type: n.entity_type, entity_value: n.entity_value }));
		if (entities.length === 0) {
			return;
		}
		await bulkBlacklist({ entities, reason: bulkReason.trim() });
		setBulkReason('');
	};

	const handleBulkCreateCases = async () => {
		const items = selectedEdgeTxKeys
			.map((key) => {
				const sep = key.indexOf('::');
				return sep > 0
					? { detection_job_id: key.slice(0, sep), event_id: key.slice(sep + 2) }
					: null;
			})
			.filter((item): item is { detection_job_id: string; event_id: string } => item !== null);
		if (items.length === 0) {
			return;
		}
		await bulkCaseIntake({ items });
	};

	const combinedError =
		(subgraphQuery.error as Error | null) ||
		(hubsQuery.error as Error | null) ||
		(expandError as Error | null) ||
		(bulkBlacklistError as Error | null) ||
		(bulkCaseIntakeError as Error | null);

	return (
		<div className="space-y-4">
			<SectionCard
				title="Khám phá đồ thị mạng lưới liên kết (SUC-19)"
				subtitle="Truy vết cụm chia sẻ thiết bị, IP, thẻ và vòng thông đồng đơn vị chấp nhận bằng openCypher"
				actions={
					subgraphQuery.data?.available && (
						<div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-slate-300">
							<span className="rounded border border-dark-700 bg-dark-950 px-2 py-0.5">
								{nodes.length} nút
							</span>
							<span className="rounded border border-dark-700 bg-dark-950 px-2 py-0.5">
								{edges.length} cạnh
							</span>
							<span className="rounded border border-amber-500/40 bg-amber-950/30 px-2 py-0.5 text-amber-200">
								{patterns.length} mẫu hình
							</span>
						</div>
					)
				}
			>
				<form
					onSubmit={(event) => {
						event.preventDefault();
						searchSeed();
					}}
					className="grid gap-3 md:grid-cols-[160px_minmax(0,1fr)_auto_auto_auto]"
				>
					<select
						aria-label="Loại thực thể hạt giống"
						value={seedType}
						onChange={(e) => setSeedType(e.target.value as EntityType)}
						className={INPUT_CLASS}
					>
						{ENTITY_TYPES.map((etype) => (
							<option key={etype} value={etype}>
								{etype}
							</option>
						))}
					</select>

					<input
						type="text"
						value={seedValue}
						onChange={(e) => setSeedValue(e.target.value)}
						placeholder="Nhập mã thực thể hạt giống (VD: user_123, dev_1)..."
						className={INPUT_CLASS}
					/>

					<select
						aria-label="Độ sâu duyệt đồ thị"
						value={hops}
						onChange={(e) => setHops(Number(e.target.value) as 1 | 2)}
						className={INPUT_CLASS}
					>
						<option value={1}>1-hop</option>
						<option value={2}>2-hop</option>
					</select>

					<select
						aria-label="Khung thời gian dữ liệu"
						value={days}
						onChange={(e) => setDays(Number(e.target.value))}
						className={INPUT_CLASS}
					>
						<option value={30}>30 ngày</option>
						<option value={90}>90 ngày</option>
						<option value={365}>365 ngày</option>
					</select>

					<button type="submit" className={BUTTON_PRIMARY_CLASS}>
						<Search size={14} aria-hidden="true" />
						<span>Phân tích đồ thị</span>
					</button>
				</form>

				<div className="flex flex-wrap items-center justify-between gap-3 border-t border-dark-800 pt-3 text-xs">
					<div className="flex flex-wrap items-center gap-3">
						<span className="text-[11px] font-medium text-slate-400">Loại nút liên kết:</span>
						{SECONDARY_ENTITY_FILTERS.map((item) => (
							<label key={item.type} className="inline-flex cursor-pointer items-center gap-1.5 text-slate-300">
								<input
									type="checkbox"
									checked={entityTypes.includes(item.type)}
									onChange={() => toggleEntityType(item.type)}
								/>
								<span>{item.label}</span>
							</label>
						))}
					</div>
					<label className="inline-flex cursor-pointer items-center gap-2 text-slate-300">
						<input
							type="checkbox"
							checked={hideSuperNodes}
							onChange={(e) => setHideSuperNodes(e.target.checked)}
						/>
						<span>Ẩn nút siêu lớn (Super-nodes)</span>
					</label>
				</div>
			</SectionCard>

			<ErrorNotice error={combinedError} />

			{actionFeedback && (
				<div
					role="status"
					className="flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-4 py-2.5 text-xs text-emerald-200"
				>
					<CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
					<span>{actionFeedback}</span>
				</div>
			)}

			{notice && (
				<div
					role="status"
					className="flex items-start gap-2.5 rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-2.5 text-xs text-amber-200"
				>
					<AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" />
					<span>{notice}</span>
				</div>
			)}

			{patterns.length > 0 && (
				<div className="flex flex-wrap gap-2">
					{patterns.map((pattern) => (
						<div
							key={`${pattern.pattern_type}:${pattern.node_id}`}
							className="inline-flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-950/25 px-3 py-1.5 text-xs text-rose-200"
						>
							<ShieldAlert size={14} className="shrink-0 text-rose-400" aria-hidden="true" />
							<span className="font-semibold">{pattern.pattern_type}</span>
							<span>{pattern.summary}</span>
						</div>
					))}
				</div>
			)}

			<div className={compact ? 'space-y-4' : 'grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]'}>
				<div className="min-w-0 space-y-4">
					{!activeSeed ? (
						<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-8 text-center text-xs text-slate-400">
							<Network size={28} className="mx-auto mb-2 text-slate-500" aria-hidden="true" />
							<p>Nhập mã thực thể hạt giống hoặc chọn một cụm rủi ro nổi bật để bắt đầu khám phá đồ thị.</p>
						</div>
					) : subgraphQuery.isPending ? (
						<div role="status" className="rounded-xl border border-dark-700/80 bg-dark-900 p-8 text-center text-xs text-slate-300">
							Đang dựng đồ thị liên kết từ kho dữ liệu dự án...
						</div>
					) : subgraphQuery.data?.available === false ? (
						<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-xs text-slate-300">
							{subgraphQuery.data.message || 'Chưa có dữ liệu đồ thị khả dụng.'}
						</div>
					) : (
						<CytoscapeCanvas
							nodes={nodes}
							edges={edges}
							selectedNodeIds={selectedNodeIds}
							focusedNodeId={focusedNodeId}
							selectedEdgeId={selectedEdge?.id ?? null}
							onToggleNodeSelect={toggleNodeSelection}
							onFocusNode={setFocusedNodeId}
							onExpandNode={(node) => expandNode({ entity_type: node.entity_type, entity_value: node.entity_value })}
							onSelectEdge={selectEdge}
							compact={compact}
						/>
					)}
				</div>

				<div className="min-w-0 space-y-4">
					{!compact && (
						<SectionCard
							title="Cụm rủi ro nổi bật"
							subtitle="Thực thể chia sẻ nhiều tài khoản hoặc có giao dịch bị gắn cờ"
						>
							{hubsQuery.isPending ? (
								<p className="text-xs text-slate-400">Đang quét cụm rủi ro...</p>
							) : (hubsQuery.data?.hubs.length ?? 0) === 0 ? (
								<p className="text-xs text-slate-400">
									{hubsQuery.data?.message || 'Chưa phát hiện cụm chia sẻ bất thường.'}
								</p>
							) : (
								<ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1 text-xs">
									{hubsQuery.data?.hubs.map((hub) => (
										<li key={hub.id}>
											<button
												type="button"
												onClick={() => searchSeed(hub.entity_type, hub.entity_value)}
												className="flex w-full items-center justify-between gap-2 rounded-lg border border-dark-800 bg-dark-950/70 px-2.5 py-2 text-left hover:border-brand-500/50 hover:bg-dark-900"
											>
												<div className="min-w-0">
													<p className="truncate font-mono font-semibold text-slate-100">
														{hub.entity_value}
													</p>
													<p className="text-[11px] text-slate-400">
														{hub.entity_type} &bull; {hub.distinct_users} tài khoản &bull; {hub.flagged_tx_count} gắn cờ
													</p>
												</div>
												<StatusBadge value={hub.pattern_type ?? hub.risk_status} />
											</button>
										</li>
									))}
								</ul>
							)}
						</SectionCard>
					)}

					<SectionCard
						title="Chi tiết thực thể & hành động cụm"
						subtitle={focusedNode ? focusedNode.id : 'Chọn một nút hoặc cạnh trên đồ thị'}
					>
						{focusedNode ? (
							<div className="space-y-2 text-xs">
								<div className="flex flex-wrap items-center justify-between gap-2">
									<StatusBadge value={focusedNode.risk_status} />
									<button
										type="button"
										disabled={isExpanding}
										onClick={() =>
											expandNode({
												entity_type: focusedNode.entity_type,
												entity_value: focusedNode.entity_value,
											})
										}
										className={BUTTON_SECONDARY_CLASS}
									>
										<GitFork size={13} aria-hidden="true" />
										<span>Mở rộng nhánh (+1 hop)</span>
									</button>
								</div>
								<dl className="grid grid-cols-2 gap-2 rounded-lg border border-dark-800 bg-dark-950 p-2.5">
									<div>
										<dt className="text-[11px] text-slate-400">Tổng giao dịch</dt>
										<dd className="font-mono font-semibold text-slate-100">{focusedNode.tx_count}</dd>
									</div>
									<div>
										<dt className="text-[11px] text-slate-400">Giao dịch gắn cờ</dt>
										<dd className="font-mono font-semibold text-amber-300">{focusedNode.flagged_tx_count}</dd>
									</div>
									<div>
										<dt className="text-[11px] text-slate-400">Điểm AI cao nhất</dt>
										<dd className="font-mono text-slate-100">{formatNumber(focusedNode.max_model_score, 3)}</dd>
									</div>
									<div>
										<dt className="text-[11px] text-slate-400">Tài khoản liên kết</dt>
										<dd className="font-mono text-slate-100">{focusedNode.distinct_users || '--'}</dd>
									</div>
								</dl>
								{focusedNode.case_ids.length > 0 && (
									<div className="flex flex-wrap items-center gap-1.5">
										<span className="text-[11px] text-slate-400">Hồ sơ liên quan:</span>
										{focusedNode.case_ids.slice(0, 3).map((cid) => (
											<Link
												key={cid}
												to={`/investigation/cases/${cid}`}
												className="font-mono text-[11px] text-brand-400 underline hover:text-brand-300"
											>
												{cid.slice(0, 8)}
											</Link>
										))}
									</div>
								)}
							</div>
						) : (
							<p className="text-xs text-slate-400">Chưa có nút nào được chọn.</p>
						)}

						{canManageBlacklist && (
							<div className="space-y-2 border-t border-dark-800 pt-3">
								<p className="text-[11px] font-medium text-slate-300">
									Đã chọn {selectedNodeIds.length} nút để đưa vào danh sách chặn
								</p>
								<input
									type="text"
									value={bulkReason}
									onChange={(e) => setBulkReason(e.target.value)}
									placeholder="Lý do chặn hàng loạt (tối thiểu 10 ký tự)..."
									className={INPUT_CLASS}
								/>
								<button
									type="button"
									data-action="bulk-blacklist"
									disabled={selectedNodeIds.length === 0 || bulkReason.trim().length < 10 || isBulkBlacklisting}
									onClick={() => void handleBulkBlacklist()}
									className={BUTTON_DANGER_CLASS}
								>
									<Ban size={13} aria-hidden="true" />
									<span>Chặn hàng loạt thực thể</span>
								</button>
							</div>
						)}
					</SectionCard>

					<SectionCard
						title="Soi giao dịch trên cạnh"
						subtitle={selectedEdge ? `${selectedEdge.user_id} → ${selectedEdge.entity_value}` : 'Nhấp vào một cạnh để xem giao dịch chi tiết'}
					>
						{!selectedEdge ? (
							<p className="text-xs text-slate-400">Chưa chọn cạnh liên kết nào.</p>
						) : edgeTransactionsQuery.isPending ? (
							<p className="text-xs text-slate-400">Đang tải danh sách giao dịch...</p>
						) : (edgeTransactionsQuery.data?.transactions.length ?? 0) === 0 ? (
							<p className="text-xs text-slate-400">Không có giao dịch trong khung thời gian này.</p>
						) : (
							<div className="space-y-3">
								<ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1 text-xs">
									{edgeTransactionsQuery.data?.transactions.map((tx) => {
										const txKey = `${tx.job_id}::${tx.event_id}`;
										const canSelect = Boolean(tx.job_id && tx.is_flagged && !tx.case_id);
										return (
											<li
												key={tx.event_id}
												className="flex items-start justify-between gap-2 rounded-lg border border-dark-800 bg-dark-950/70 p-2"
											>
												<div className="flex min-w-0 items-start gap-2">
													{canSelect && (
														<input
															type="checkbox"
															checked={selectedEdgeTxKeys.includes(txKey)}
															onChange={() => toggleEdgeTransaction(tx)}
															aria-label={`Chọn giao dịch ${tx.event_id}`}
														/>
													)}
													<div className="min-w-0">
														<p className="truncate font-mono font-semibold text-slate-100">{tx.event_id}</p>
														<p className="text-[11px] text-slate-400">
															{formatCurrencyAmount(tx.amount)} &bull; {formatDateTime(tx.tx_timestamp)}
														</p>
													</div>
												</div>
												<div className="flex shrink-0 flex-col items-end gap-1">
													<StatusBadge value={tx.final_action} />
													{tx.case_id && (
														<Link
															to={`/investigation/cases/${tx.case_id}`}
															className="font-mono text-[10px] text-brand-400 underline"
														>
															Mở hồ sơ
														</Link>
													)}
												</div>
											</li>
										);
									})}
								</ul>

								{canCreateCase && (
									<button
										type="button"
										data-action="bulk-case-intake"
										disabled={selectedEdgeTxKeys.length === 0 || isBulkIntaking}
										onClick={() => void handleBulkCreateCases()}
										className={BUTTON_PRIMARY_CLASS}
									>
										<FolderPlus size={13} aria-hidden="true" />
										<span>Tạo hồ sơ điều tra ({selectedEdgeTxKeys.length})</span>
									</button>
								)}
							</div>
						)}
					</SectionCard>
				</div>
			</div>
		</div>
	);
}
