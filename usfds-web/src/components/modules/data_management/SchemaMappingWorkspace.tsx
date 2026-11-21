import { useState, useMemo, useEffect, useRef } from 'react';
import {
	CheckCircle2,
	AlertTriangle,
	ArrowRight,
	Plus,
	Trash2,
	Clock,
	DollarSign,
	User,
	Hash,
	Flame,
	Layers,
	Database,
} from 'lucide-react';
import { useSystemMetadata } from '@/hooks/useSystemMetadata';
import type {
	DatasetArtifactResponse,
	DataMappingConfig,
} from '../../../types/dataset';
import type { SystemColumnMetadata } from '@/types/systemMetadata';

interface SchemaMappingWorkspaceProps {
	rawArtifact: DatasetArtifactResponse | null;
	mappedArtifact: DatasetArtifactResponse | null;
	onConfigChange?: (config: DataMappingConfig, isValid: boolean) => void;
	saveError?: string | null;
}

const FALLBACK_SYSTEM_COLUMNS: SystemColumnMetadata[] = [
	{
		metadata_id: 'fallback-event-id',
		column_key: 'event_id',
		display_name: 'Mã giao dịch',
		category: 'CORE',
		logical_type: 'STRING',
		is_required: true,
		ml_role: 'IDENTIFIER',
		aliases: ['event_id', 'transaction_id', 'TransactionID', 'tx_id', 'trans_id', 'id', 'trans_num'],
		description: 'Mã định danh giao dịch duy nhất',
		is_active: true,
		display_order: 1,
	},
	{
		metadata_id: 'fallback-timestamp',
		column_key: 'timestamp',
		display_name: 'Thời gian giao dịch',
		category: 'CORE',
		logical_type: 'DATETIME',
		is_required: true,
		ml_role: 'TIMESTAMP',
		aliases: ['timestamp', 'transaction_time', 'TransactionDT', 'tx_time', 'trans_date_time', 'datetime', 'time'],
		description: 'Dấu thời gian sự kiện giao dịch',
		is_active: true,
		display_order: 2,
	},
	{
		metadata_id: 'fallback-amount',
		column_key: 'amount',
		display_name: 'Số tiền giao dịch',
		category: 'CORE',
		logical_type: 'NUMERIC',
		is_required: true,
		ml_role: 'FEATURE',
		aliases: ['amount', 'Amount', 'transaction_amount', 'TransactionAmt', 'tx_amount', 'amt'],
		description: 'Giá trị tiền tệ / thanh toán',
		is_active: true,
		display_order: 3,
	},
	{
		metadata_id: 'fallback-user-id',
		column_key: 'user_id',
		display_name: 'Mã người dùng / tài khoản',
		category: 'CORE',
		logical_type: 'STRING',
		is_required: true,
		ml_role: 'IDENTIFIER',
		aliases: ['user_id', 'customer_id', 'client_id', 'account_id', 'cc_num', 'card1', 'CLIENTNUM'],
		description: 'Mã token tài khoản / thẻ',
		is_active: true,
		display_order: 4,
	},
	{
		metadata_id: 'fallback-label',
		column_key: 'label',
		display_name: 'Nhãn gian lận',
		category: 'CORE',
		logical_type: 'NUMERIC',
		is_required: true,
		ml_role: 'LABEL',
		aliases: ['label', 'is_fraud', 'isFraud', 'target', 'fraud', 'Class', 'class'],
		description: 'Nhãn gian lận thực tế',
		is_active: true,
		display_order: 5,
	},
	{
		metadata_id: 'fallback-merchant',
		column_key: 'merchant',
		display_name: 'Đơn vị chấp nhận thẻ',
		category: 'DOMAIN',
		logical_type: 'STRING',
		is_required: false,
		ml_role: 'FEATURE',
		aliases: ['merchant', 'merch_name', 'merchant_name'],
		description: 'Tên đơn vị kinh doanh',
		is_active: true,
		display_order: 10,
	},
	{
		metadata_id: 'fallback-category',
		column_key: 'category',
		display_name: 'Danh mục giao dịch',
		category: 'DOMAIN',
		logical_type: 'STRING',
		is_required: false,
		ml_role: 'FEATURE',
		aliases: ['category', 'merchant_category', 'mcc'],
		description: 'Nhóm ngành hàng giao dịch',
		is_active: true,
		display_order: 11,
	},
];

function normalizeName(value: string): string {
	return value.trim().toLowerCase().replace(/[\s_-]+/g, '');
}

function matchRawColumnByAliases(
	rawColumns: string[],
	aliases: string[],
	usedCols: Set<string>
): string {
	const available = rawColumns.filter((c) => !usedCols.has(c));
	const candidates = aliases.filter(Boolean);

	// 1. Exact match
	for (const alias of candidates) {
		const exact = available.find((c) => c === alias);
		if (exact) {
			return exact;
		}
	}

	// 2. Case-insensitive match
	for (const alias of candidates) {
		const lower = alias.toLowerCase();
		const matched = available.find((c) => c.toLowerCase() === lower);
		if (matched) {
			return matched;
		}
	}

	// 3. Normalized match
	for (const alias of candidates) {
		const norm = normalizeName(alias);
		const matched = available.find((c) => normalizeName(c) === norm);
		if (matched) {
			return matched;
		}
	}

	return '';
}

interface SnapshotEntry {
	column_key: string;
	category?: string;
	logical_type?: string;
	is_required?: boolean;
	ml_role?: string;
	is_active?: boolean;
}

function detectSchemaDrift(
	mappedArtifact: DatasetArtifactResponse | null,
	activeColumns: SystemColumnMetadata[]
): string[] {
	const report = mappedArtifact?.validation_report as Record<string, unknown> | undefined;
	const snapshotRaw = report?.metadata_snapshot;
	if (!Array.isArray(snapshotRaw) || snapshotRaw.length === 0 || activeColumns.length === 0) {
		return [];
	}

	const snapshotMap = new Map<string, SnapshotEntry>();
	for (const entry of snapshotRaw as SnapshotEntry[]) {
		if (entry?.column_key) {
			snapshotMap.set(entry.column_key, entry);
		}
	}

	const activeMap = new Map<string, SystemColumnMetadata>();
	for (const col of activeColumns) {
		activeMap.set(col.column_key, col);
	}

	const diffs: string[] = [];
	for (const col of activeColumns) {
		const prev = snapshotMap.get(col.column_key);
		if (!prev) {
			if (col.is_required) {
				diffs.push(`Cột bắt buộc mới '${col.column_key}' chưa có trong artifact cũ`);
			}
			continue;
		}
		if (prev.ml_role && prev.ml_role !== col.ml_role) {
			diffs.push(`Vai trò ML của '${col.column_key}' đã đổi (${prev.ml_role} → ${col.ml_role})`);
		}
		if (prev.logical_type && prev.logical_type !== col.logical_type) {
			diffs.push(`Kiểu logic của '${col.column_key}' đã đổi (${prev.logical_type} → ${col.logical_type})`);
		}
	}

	for (const [key] of snapshotMap) {
		if (!activeMap.has(key)) {
			diffs.push(`Cột '${key}' trong artifact cũ đã bị tắt hoặc xóa khỏi siêu dữ liệu hiện hành`);
		}
	}

	return diffs;
}

export const SchemaMappingWorkspace = ({
	rawArtifact,
	mappedArtifact,
	onConfigChange,
	saveError: externalSaveError = null,
}: SchemaMappingWorkspaceProps) => {
	const { columns: fetchedColumns } = useSystemMetadata({ includeInactive: false });
	const activeColumns = useMemo<SystemColumnMetadata[]>(
		() => (fetchedColumns.length > 0 ? fetchedColumns : FALLBACK_SYSTEM_COLUMNS),
		[fetchedColumns]
	);

	const coreMetaByKey = useMemo(() => {
		const map = new Map<string, SystemColumnMetadata>();
		for (const col of activeColumns) {
			if (col.category === 'CORE') {
				map.set(col.column_key, col);
			}
		}
		return map;
	}, [activeColumns]);

	const requiredDomainColumns = useMemo(
		() => activeColumns.filter((c) => c.category === 'DOMAIN' && c.is_required && c.is_active),
		[activeColumns]
	);

	const optionalDomainColumns = useMemo(
		() => activeColumns.filter((c) => c.category === 'DOMAIN' && !c.is_required && c.is_active),
		[activeColumns]
	);

	// Available raw columns from schema_snapshot or fallback
	const rawColumns = useMemo<string[]>(() => {
		if (rawArtifact?.schema_snapshot) {
			return Object.keys(rawArtifact.schema_snapshot);
		}
		return [
			'trans_id',
			'trans_date_time',
			'amt',
			'cc_num',
			'is_fraud',
			'merch_name',
			'category',
			'city_pop',
			'job',
			'unix_time',
		];
	}, [rawArtifact]);

	const [eventIdCol, setEventIdCol] = useState<string>('');
	const [timeCol, setTimeCol] = useState<string>('');
	const [timeFormat, setTimeFormat] = useState<'auto' | 'iso' | 'epoch_s' | 'epoch_ms'>('auto');
	const [amountCol, setAmountCol] = useState<string>('');
	const [userIdCol, setUserIdCol] = useState<string>('');
	const [targetCol, setTargetCol] = useState<string>('');
	const [requiredDomainMap, setRequiredDomainMap] = useState<Record<string, string>>({});
	const [optionalMappings, setOptionalMappings] = useState<Array<{ raw: string; target: string }>>([]);

	const metadataSignature = useMemo(
		() =>
			activeColumns
				.map((c) => `${c.column_key}:${c.is_required}:${(c.aliases || []).join('|')}`)
				.join(';'),
		[activeColumns]
	);
	const rawSignature = useMemo(() => rawColumns.join('|'), [rawColumns]);
	const lastAppliedSigRef = useRef<string>('');

	// Re-run auto-match whenever active metadata or raw columns change
	useEffect(() => {
		const sig = `${rawArtifact?.artifact_id || 'fallback'}::${rawSignature}::${metadataSignature}`;
		if (lastAppliedSigRef.current === sig) {
			return;
		}
		lastAppliedSigRef.current = sig;

		const used = new Set<string>();
		const resolveCore = (key: string, fallbackIndex: number) => {
			const meta = coreMetaByKey.get(key);
			const matched = matchRawColumnByAliases(rawColumns, [key, ...(meta?.aliases || [])], used);
			const chosen = matched || rawColumns[fallbackIndex] || rawColumns[0] || '';
			if (chosen) {
				used.add(chosen);
			}
			return chosen;
		};

		setEventIdCol(resolveCore('event_id', 0));
		setTimeCol(resolveCore('timestamp', 1));
		setAmountCol(resolveCore('amount', 2));
		setUserIdCol(resolveCore('user_id', 3));
		setTargetCol(resolveCore('label', 4));

		const nextReqDomain: Record<string, string> = {};
		for (const col of requiredDomainColumns) {
			const matched = matchRawColumnByAliases(rawColumns, [col.column_key, ...(col.aliases || [])], used);
			nextReqDomain[col.column_key] = matched;
			if (matched) {
				used.add(matched);
			}
		}
		setRequiredDomainMap(nextReqDomain);

		const nextOptional: Array<{ raw: string; target: string }> = [];
		for (const col of optionalDomainColumns) {
			const matched = matchRawColumnByAliases(rawColumns, [col.column_key, ...(col.aliases || [])], used);
			if (matched) {
				nextOptional.push({ raw: matched, target: col.column_key });
				used.add(matched);
			}
		}
		setOptionalMappings(nextOptional);
	}, [
		rawArtifact?.artifact_id,
		rawColumns,
		rawSignature,
		metadataSignature,
		coreMetaByKey,
		requiredDomainColumns,
		optionalDomainColumns,
	]);

	const displayError = externalSaveError;
	const schemaDriftWarnings = useMemo(
		() => detectSchemaDrift(mappedArtifact, activeColumns),
		[mappedArtifact, activeColumns]
	);

	// Mandatory slot satisfaction: 5 CORE + all active required DOMAIN columns
	const coreSatisfiedCount = [eventIdCol, timeCol, amountCol, userIdCol, targetCol].filter(Boolean).length;
	const requiredDomainSatisfiedCount = requiredDomainColumns.filter(
		(col) => Boolean(requiredDomainMap[col.column_key])
	).length;
	const totalMandatorySlots = 5 + requiredDomainColumns.length;
	const mandatoryCount = coreSatisfiedCount + requiredDomainSatisfiedCount;
	const isAllMandatorySatisfied = mandatoryCount === totalMandatorySlots;

	const handleAddOptional = () => {
		const usedRaw = new Set<string>([
			eventIdCol,
			timeCol,
			amountCol,
			userIdCol,
			targetCol,
			...Object.values(requiredDomainMap),
			...optionalMappings.map((m) => m.raw),
		]);
		const unmapped = rawColumns.find((c) => !usedRaw.has(c));
		if (unmapped) {
			setOptionalMappings([...optionalMappings, { raw: unmapped, target: unmapped.toLowerCase() }]);
		} else {
			setOptionalMappings([...optionalMappings, { raw: rawColumns[0] || '', target: 'custom_field' }]);
		}
	};

	const handleRemoveOptional = (index: number) => {
		setOptionalMappings(optionalMappings.filter((_, i) => i !== index));
	};

	const handleUpdateOptional = (index: number, key: 'raw' | 'target', value: string) => {
		const copy = [...optionalMappings];
		copy[index] = { ...copy[index], [key]: value };
		setOptionalMappings(copy);
	};

	const onConfigChangeRef = useRef(onConfigChange);
	useEffect(() => {
		onConfigChangeRef.current = onConfigChange;
	}, [onConfigChange]);

	// Notify parent container of configuration changes
	useEffect(() => {
		const optionalObj: Record<string, string> = {};
		for (const col of requiredDomainColumns) {
			const raw = requiredDomainMap[col.column_key];
			if (raw) {
				optionalObj[raw] = col.column_key;
			}
		}
		optionalMappings.forEach((m) => {
			if (m.raw && m.target) {
				optionalObj[m.raw] = m.target;
			}
		});

		const payload: DataMappingConfig = {
			event_id_column: eventIdCol,
			time_column: timeCol,
			amount_column: amountCol,
			user_id_column: userIdCol,
			target_column: targetCol,
			optional_columns: optionalObj,
			time_format: timeFormat,
		};

		onConfigChangeRef.current?.(payload, isAllMandatorySatisfied);
	}, [
		eventIdCol,
		timeCol,
		amountCol,
		userIdCol,
		targetCol,
		requiredDomainColumns,
		requiredDomainMap,
		optionalMappings,
		timeFormat,
		isAllMandatorySatisfied,
	]);

	const getMetaDescription = (key: string, fallback: string) =>
		coreMetaByKey.get(key)?.description || fallback;

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			{/* Main Workspace Body */}
			<div className="flex-1 overflow-y-auto p-6 space-y-6">
				{displayError && (
					<div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center justify-between">
						<div className="flex items-center gap-2">
							<AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
							<span>{displayError}</span>
						</div>
					</div>
				)}

				{schemaDriftWarnings.length > 0 && (
					<div
						role="status"
						className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 space-y-1.5"
					>
						<div className="flex items-center gap-2 font-semibold text-amber-300">
							<AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
							<span>Cảnh báo lệch siêu dữ liệu lược đồ (Schema Drift)</span>
						</div>
						<ul className="list-disc list-inside text-[11px] text-amber-200/90 space-y-0.5">
							{schemaDriftWarnings.map((warn, i) => (
								<li key={i}>{warn}</li>
							))}
						</ul>
						<p className="text-[11px] text-amber-300/80">
							Artifact cũ vẫn chạy bình thường. Nhấn &ldquo;Kiểm định dữ liệu&rdquo; để tạo nhánh ánh xạ mới theo cấu hình hiện hành.
						</p>
					</div>
				)}

				{/* Lineage Branching Information */}
				<div className="p-3 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between text-xs">
					<div className="flex items-center gap-2 text-slate-300">
						<Layers className="w-4 h-4 text-brand-400 shrink-0" />
						<span>
							{mappedArtifact ? (
								<>
									<span className="text-slate-400">Phiên bản hiện tại:</span>{' '}
									<code className="text-brand-300 font-mono bg-dark-950 px-1.5 py-0.5 rounded border border-dark-800">
										{mappedArtifact.artifact_id}
									</code>
									. Bạn có thể điều chỉnh cấu hình và nhấn &ldquo;Kiểm định dữ liệu&rdquo; trên thanh tiêu đề để xác thực và tạo artifact mới.
								</>
							) : (
								<>
									<span className="text-emerald-400 font-medium">Nhánh ánh xạ mới:</span>{' '}
									Đang khởi tạo cấu hình từ Raw dataset{' '}
									<code className="text-slate-300 font-mono bg-dark-950 px-1.5 py-0.5 rounded border border-dark-800">
										{rawArtifact?.artifact_id || 'Đầu vào thô'}
									</code>
									. Nhấn nút &ldquo;Kiểm định dữ liệu&rdquo; trên thanh tiêu đề để xác thực và chuyển sang bước báo cáo kiểm định.
								</>
							)}
						</span>
					</div>
				</div>

				{/* UNIFIED SCHEMA MAPPING TABLE */}
				<div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-5">
					<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-800 pb-3">
						<div>
							<h2 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
								Ánh xạ trường lược đồ
								<span className="text-[10px] font-normal normal-case text-slate-500">
									(Ánh xạ trường giao dịch thô tới trường đích chuẩn và tín hiệu nghiệp vụ tùy chọn)
								</span>
							</h2>
						</div>
						<div className="flex items-center gap-3">
							<div
								className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-medium border flex items-center gap-1.5 ${
									isAllMandatorySatisfied
										? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
										: 'bg-amber-500/15 text-amber-300 border-amber-500/40'
								}`}
							>
								<CheckCircle2 className="w-3 h-3" />
								<span>
									{mandatoryCount} / {totalMandatorySlots} Trường bắt buộc
								</span>
							</div>
							<button
								type="button"
								onClick={handleAddOptional}
								className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 text-xs font-medium transition flex items-center gap-1.5"
							>
								<Plus className="w-3.5 h-3.5 text-brand-400" />
								<span>Thêm thuộc tính tùy chọn</span>
							</button>
						</div>
					</div>

					{/* Unified Table */}
					<div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/70">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
										<th className="py-3 px-4 font-semibold w-1/4">Trường đích chuẩn</th>
										<th className="py-3 px-4 font-semibold w-1/4">Cột nguồn</th>
										<th className="py-3 px-4 font-semibold w-1/4">Phân tích / cấu hình</th>
										<th className="py-3 px-4 font-semibold w-1/6">Giá trị mẫu</th>
										<th className="py-3 px-4 font-semibold text-center w-12">Thao tác</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-850">
									{/* SECTION HEADER: MANDATORY */}
									<tr className="bg-dark-900/60 text-slate-400">
										<td colSpan={5} className="py-2 px-4 text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
											Vị trí bắt buộc ({totalMandatorySlots} trường yêu cầu)
										</td>
									</tr>

									{/* Row 1: event_id */}
									<tr className="hover:bg-dark-900/40 transition">
										<td className="py-3.5 px-4">
											<div className="flex items-start gap-3">
												<div className="p-1.5 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 shrink-0 mt-0.5">
													<Hash className="w-3.5 h-3.5" />
												</div>
												<div>
													<div className="flex items-center gap-1.5">
														<span className="font-mono text-xs font-bold text-slate-100">event_id</span>
														<span className="text-rose-400 font-bold">*</span>
														<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
															STRING
														</span>
													</div>
													<p className="text-[11px] text-slate-500 mt-0.5">
														{getMetaDescription('event_id', 'Mã định danh giao dịch duy nhất')}
													</p>
												</div>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<div className="flex items-center gap-2">
												<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
												<select
													aria-label="Cột nguồn cho event_id"
													value={eventIdCol}
													onChange={(e) => setEventIdCol(e.target.value)}
													className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
												>
													{rawColumns.map((col) => (
														<option key={col} value={col}>
															{col}
														</option>
													))}
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4 font-mono text-slate-300">
											<span className="text-slate-500">Ràng buộc:</span> Khóa chính duy nhất (Phi-ML)
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
												&quot;TX_98201&quot;
											</span>
										</td>
										<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
									</tr>

									{/* Row 2: timestamp */}
									<tr className="hover:bg-dark-900/40 transition">
										<td className="py-3.5 px-4">
											<div className="flex items-start gap-3">
												<div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0 mt-0.5">
													<Clock className="w-3.5 h-3.5" />
												</div>
												<div>
													<div className="flex items-center gap-1.5">
														<span className="font-mono text-xs font-bold text-slate-100">timestamp</span>
														<span className="text-rose-400 font-bold">*</span>
														<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
															DATETIME
														</span>
													</div>
													<p className="text-[11px] text-slate-500 mt-0.5">
														{getMetaDescription('timestamp', 'Dấu thời gian sự kiện giao dịch')}
													</p>
												</div>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<div className="flex items-center gap-2">
												<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
												<select
													aria-label="Cột nguồn cho timestamp"
													value={timeCol}
													onChange={(e) => setTimeCol(e.target.value)}
													className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
												>
													{rawColumns.map((col) => (
														<option key={col} value={col}>
															{col}
														</option>
													))}
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4 font-mono text-slate-300">
											<div className="flex items-center gap-2">
												<span className="text-slate-500">Định dạng:</span>
												<select
													value={timeFormat}
													onChange={(e) =>
														setTimeFormat(e.target.value as 'auto' | 'iso' | 'epoch_s' | 'epoch_ms')
													}
													className="px-2 py-1 bg-dark-900 border border-dark-700 rounded text-xs font-mono text-amber-300 focus:outline-none"
												>
													<option value="auto">Tự động phân tích</option>
													<option value="iso">ISO-8601 UTC</option>
													<option value="epoch_s">Epoch giây</option>
													<option value="epoch_ms">Epoch mili giây</option>
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono text-xs text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
												&quot;2026-09-15&quot;
											</span>
										</td>
										<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
									</tr>

									{/* Row 3: amount */}
									<tr className="hover:bg-dark-900/40 transition">
										<td className="py-3.5 px-4">
											<div className="flex items-start gap-3">
												<div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0 mt-0.5">
													<DollarSign className="w-3.5 h-3.5" />
												</div>
												<div>
													<div className="flex items-center gap-1.5">
														<span className="font-mono text-xs font-bold text-slate-100">amount</span>
														<span className="text-rose-400 font-bold">*</span>
														<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
															NUMERIC
														</span>
													</div>
													<p className="text-[11px] text-slate-500 mt-0.5">
														{getMetaDescription('amount', 'Giá trị tiền tệ / thanh toán')}
													</p>
												</div>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<div className="flex items-center gap-2">
												<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
												<select
													aria-label="Cột nguồn cho amount"
													value={amountCol}
													onChange={(e) => setAmountCol(e.target.value)}
													className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
												>
													{rawColumns.map((col) => (
														<option key={col} value={col}>
															{col}
														</option>
													))}
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4 font-mono text-slate-300">
											<span className="text-slate-500">Đặc trưng ML:</span> float64 ($ &gt; 0)
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
												&quot;$12.50&quot;
											</span>
										</td>
										<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
									</tr>

									{/* Row 4: user_id */}
									<tr className="hover:bg-dark-900/40 transition">
										<td className="py-3.5 px-4">
											<div className="flex items-start gap-3">
												<div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5">
													<User className="w-3.5 h-3.5" />
												</div>
												<div>
													<div className="flex items-center gap-1.5">
														<span className="font-mono text-xs font-bold text-slate-100">user_id</span>
														<span className="text-rose-400 font-bold">*</span>
														<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
															STRING
														</span>
													</div>
													<p className="text-[11px] text-slate-500 mt-0.5">
														{getMetaDescription('user_id', 'Mã token tài khoản / thẻ')}
													</p>
												</div>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<div className="flex items-center gap-2">
												<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
												<select
													aria-label="Cột nguồn cho user_id"
													value={userIdCol}
													onChange={(e) => setUserIdCol(e.target.value)}
													className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
												>
													{rawColumns.map((col) => (
														<option key={col} value={col}>
															{col}
														</option>
													))}
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4 font-mono text-slate-300">
											<span className="text-slate-500">Bảo mật:</span> Định danh (Phi-ML)
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono text-xs text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
												&quot;4000-xxxx-1204&quot;
											</span>
										</td>
										<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
									</tr>

									{/* Row 5: label */}
									<tr className="hover:bg-dark-900/40 transition">
										<td className="py-3.5 px-4">
											<div className="flex items-start gap-3">
												<div className="p-1.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 shrink-0 mt-0.5">
													<Flame className="w-3.5 h-3.5" />
												</div>
												<div>
													<div className="flex items-center gap-1.5">
														<span className="font-mono text-xs font-bold text-slate-100">label</span>
														<span className="text-rose-400 font-bold">*</span>
														<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
															NUMERIC (0/1)
														</span>
													</div>
													<p className="text-[11px] text-slate-500 mt-0.5">
														{getMetaDescription('label', 'Nhãn gian lận thực tế')}
													</p>
												</div>
											</div>
										</td>
										<td className="py-3.5 px-4">
											<div className="flex items-center gap-2">
												<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
												<select
													aria-label="Cột nguồn cho label"
													value={targetCol}
													onChange={(e) => setTargetCol(e.target.value)}
													className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
												>
													{rawColumns.map((col) => (
														<option key={col} value={col}>
															{col}
														</option>
													))}
												</select>
											</div>
										</td>
										<td className="py-3.5 px-4 font-mono text-slate-300">
											<span className="text-slate-500">Nhãn mục tiêu:</span> 0 = Hợp lệ, 1 = Gian lận
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono text-xs text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
												&quot;0 / 1&quot;
											</span>
										</td>
										<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
									</tr>

									{/* Dynamic Required DOMAIN columns */}
									{requiredDomainColumns.map((col) => (
										<tr key={col.metadata_id} className="hover:bg-dark-900/40 transition">
											<td className="py-3.5 px-4">
												<div className="flex items-start gap-3">
													<div className="p-1.5 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 shrink-0 mt-0.5">
														<Database className="w-3.5 h-3.5" />
													</div>
													<div>
														<div className="flex items-center gap-1.5">
															<span className="font-mono text-xs font-bold text-slate-100">{col.column_key}</span>
															<span className="text-rose-400 font-bold">*</span>
															<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">
																{col.logical_type}
															</span>
														</div>
														<p className="text-[11px] text-slate-500 mt-0.5">
															{col.description || col.display_name}
														</p>
													</div>
												</div>
											</td>
											<td className="py-3.5 px-4">
												<div className="flex items-center gap-2">
													<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
													<select
														aria-label={`Cột nguồn cho ${col.column_key}`}
														value={requiredDomainMap[col.column_key] || ''}
														onChange={(e) =>
															setRequiredDomainMap((prev) => ({
																...prev,
																[col.column_key]: e.target.value,
															}))
														}
														className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
													>
														<option value="">-- Chọn cột nguồn bắt buộc --</option>
														{rawColumns.map((raw) => (
															<option key={raw} value={raw}>
																{raw}
															</option>
														))}
													</select>
												</div>
											</td>
											<td className="py-3.5 px-4 font-mono text-slate-300">
												<span className="text-slate-500">Vai trò ML:</span>{' '}
												{col.ml_role === 'FEATURE' ? 'Đặc trưng ML' : `${col.ml_role} (Phi-ML)`}
											</td>
											<td className="py-3.5 px-4">
												<span className="font-mono text-xs text-brand-300 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
													DOMAIN bắt buộc
												</span>
											</td>
											<td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">—</td>
										</tr>
									))}

									{/* SECTION HEADER: OPTIONAL DOMAIN ATTRIBUTES */}
									<tr className="bg-dark-900/60 text-slate-400">
										<td colSpan={5} className="py-2.5 px-4">
											<div className="flex items-center justify-between">
												<span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
													Thuộc tính nghiệp vụ tùy chọn ({optionalMappings.length} đã cấu hình)
												</span>
												<span className="text-[11px] text-slate-500 normal-case">
													Giữ các tín hiệu ngữ cảnh trong tệp parquet đã chuẩn hóa.
												</span>
											</div>
										</td>
									</tr>

									{/* OPTIONAL ROWS */}
									{optionalMappings.length === 0 ? (
										<tr>
											<td colSpan={5} className="py-6 px-4 text-center text-xs text-slate-500 font-mono">
												Chưa có thuộc tính tùy chọn nào. Nhấn &quot;Thêm thuộc tính tùy chọn&quot; để giữ các tín hiệu ngữ cảnh.
											</td>
										</tr>
									) : (
										optionalMappings.map((m, idx) => {
											const matchedMeta = optionalDomainColumns.find(
												(c) => c.column_key === m.target
											);
											return (
												<tr key={idx} className="hover:bg-dark-900/40 transition">
													<td className="py-3 px-4">
														<div className="flex items-center gap-3">
															<div className="p-1.5 rounded-lg bg-dark-800 border border-dark-700 text-slate-400 shrink-0">
																<Layers className="w-3.5 h-3.5" />
															</div>
															<div className="flex-1">
																<div className="flex items-center gap-1.5">
																	<input
																		type="text"
																		value={m.target}
																		onChange={(e) => handleUpdateOptional(idx, 'target', e.target.value)}
																		placeholder="target_column_name"
																		className="w-full px-2 py-1 bg-dark-900 border border-dark-700 rounded text-xs font-mono text-brand-300 focus:outline-none focus:border-brand-500"
																	/>
																</div>
																<span className="text-[10px] text-slate-500 mt-0.5 block">
																	{matchedMeta?.display_name || 'Tín hiệu ngữ cảnh'}
																</span>
															</div>
														</div>
													</td>
													<td className="py-3 px-4">
														<div className="flex items-center gap-2">
															<ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
															<select
																value={m.raw}
																onChange={(e) => handleUpdateOptional(idx, 'raw', e.target.value)}
																className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
															>
																{rawColumns.map((col) => (
																	<option key={col} value={col}>
																		{col}
																	</option>
																))}
															</select>
														</div>
													</td>
													<td className="py-3 px-4 font-mono text-xs text-slate-400">
														<span className="text-slate-500">Biến đổi:</span>{' '}
														{matchedMeta
															? `${matchedMeta.logical_type} / ${matchedMeta.ml_role}`
															: 'Giữ nguyên / Kiểu suy luận'}
													</td>
													<td className="py-3 px-4 font-mono text-xs text-slate-300">
														<span className="px-2 py-0.5 rounded bg-dark-800 border border-dark-750 text-slate-400">
															{matchedMeta ? matchedMeta.logical_type : 'Tự suy luận'}
														</span>
													</td>
													<td className="py-3 px-4 text-center">
														<button
															type="button"
															onClick={() => handleRemoveOptional(idx)}
															className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition"
															title="Xóa thuộc tính"
														>
															<Trash2 className="w-3.5 h-3.5" />
														</button>
													</td>
												</tr>
											);
										})
									)}
								</tbody>
							</table>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default SchemaMappingWorkspace;
