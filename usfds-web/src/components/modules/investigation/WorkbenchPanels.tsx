import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Clock, Search, User } from 'lucide-react';
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	ResponsiveContainer,
	Scatter,
	ScatterChart,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import type { Workbench } from '../../../types/investigation';
import { useTheme } from '../../../hooks/useTheme';
import {
	FormField,
	INPUT_CLASS,
	ScoreBar,
	SectionCard,
	StatusBadge,
	formatCurrencyAmount,
	formatDateTime,
	formatLabel,
	formatNumber,
} from './investigationShared';

export function SubjectAndBaselineColumn({
	data,
	days,
	onChangeDays,
}: {
	data: Workbench;
	days: 30 | 90;
	onChangeDays: (days: 30 | 90) => void;
}) {
	const { case: item, profile, related_cases: related } = data;

	return (
		<div className="min-w-0 space-y-4">
			<SectionCard
				title="Hồ sơ người liên quan"
				subtitle="Chủ thẻ chính & siêu dữ liệu sự kiện bị gắn cờ"
				badge={<StatusBadge value={data.subject_status} />}
			>
				<div className="flex items-center gap-2.5 rounded-lg border border-dark-700/80 bg-dark-950 p-3">
					<span className="rounded-lg bg-brand-500/10 p-2 text-brand-400">
						<User size={16} aria-hidden="true" />
					</span>
					<div className="min-w-0">
						<p className="text-[11px] text-slate-400">ID người dùng liên quan</p>
						<p className="break-all font-mono text-sm font-bold text-slate-100">
							{item.user_id}
						</p>
					</div>
				</div>

				<dl className="grid grid-cols-2 gap-3 text-xs">
					<div className="col-span-2 rounded-lg border border-dark-800 bg-dark-950/50 p-2.5">
						<dt className="text-[11px] text-slate-400">ID sự kiện bị gắn cờ</dt>
						<dd className="mt-0.5 break-all font-mono font-medium text-slate-100">
							{item.event_id}
						</dd>
					</div>
					<div className="rounded-lg border border-dark-800 bg-dark-950/50 p-2.5">
						<dt className="text-[11px] text-slate-400">Số tiền giao dịch</dt>
						<dd className="mt-0.5 font-mono text-sm font-bold tabular-nums text-slate-100">
							{formatCurrencyAmount(item.amount)}
						</dd>
					</div>
					<div className="rounded-lg border border-dark-800 bg-dark-950/50 p-2.5">
						<dt className="text-[11px] text-slate-400">Điểm ưu tiên</dt>
						<dd className="mt-0.5 font-mono text-sm font-bold tabular-nums text-slate-100">
							{formatNumber(item.priority_score, 1)} / 100
						</dd>
					</div>
					<div className="col-span-2 rounded-lg border border-dark-800 bg-dark-950/50 p-2.5">
						<dt className="text-[11px] text-slate-400">Thời điểm giao dịch</dt>
						<dd className="mt-0.5 font-mono text-slate-200">
							{formatDateTime(item.tx_timestamp)}
						</dd>
					</div>
					<div className="col-span-2 rounded-lg border border-dark-800 bg-dark-950/50 p-2.5">
						<dt className="text-[11px] text-slate-400">Chuyên viên được giao</dt>
						<dd className="mt-0.5 font-mono text-slate-200">
							{item.assigned_to || 'Chưa giao'}
						</dd>
					</div>
				</dl>
			</SectionCard>

			<SectionCard
				title="Đường cơ sở lịch sử"
				subtitle={`Khoảng nhìn lại trước giao dịch (${days} ngày)`}
				actions={
					<FormField name="Khoảng thời gian">
						<select
							aria-label="Khoảng thời gian đường cơ sở"
							className={INPUT_CLASS}
							value={days}
							onChange={(event) => onChangeDays(Number(event.target.value) as 30 | 90)}
						>
							<option value={30}>30 days</option>
							<option value={90}>90 days</option>
						</select>
					</FormField>
				}
			>
				{profile.cold_start && (
					<div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-950/30 p-2.5 text-xs text-amber-200">
						<AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" />
						<div>
							<p className="font-semibold">New / Cold-Start Account</p>
							<p className="text-[11px] text-amber-300/90">
								Không có lịch sử người dùng trong khoảng thời gian này. Đang so sánh với đường cơ sở toàn quần thể.
							</p>
						</div>
					</div>
				)}

				{!profile.available ? (
					<p className="text-xs text-slate-400">
						{profile.message || 'Chưa có đường cơ sở lịch sử cho nguồn này.'}
					</p>
				) : (
					<>
						<dl className="grid grid-cols-2 gap-2.5 text-xs">
							<div className="rounded-lg border border-dark-800 bg-dark-950/60 p-2.5">
								<dt className="text-[11px] text-slate-400">Số tiền trung bình</dt>
								<dd className="mt-1 font-mono font-semibold tabular-nums text-slate-100">
									{formatCurrencyAmount(profile.avg_amount)}
								</dd>
							</div>
							<div className="rounded-lg border border-dark-800 bg-dark-950/60 p-2.5">
								<dt className="text-[11px] text-slate-400">Số tiền tối đa</dt>
								<dd className="mt-1 font-mono font-semibold tabular-nums text-slate-100">
									{formatCurrencyAmount(profile.max_amount)}
								</dd>
							</div>
							<div className="rounded-lg border border-dark-800 bg-dark-950/60 p-2.5">
								<dt className="text-[11px] text-slate-400">Số giao dịch trước đó</dt>
								<dd className="mt-1 font-mono font-semibold tabular-nums text-slate-100">
									{formatNumber(profile.history_count, 0)}
								</dd>
							</div>
							<div className="rounded-lg border border-dark-800 bg-dark-950/60 p-2.5">
								<dt className="text-[11px] text-slate-400">Avg Tx / Day</dt>
								<dd className="mt-1 font-mono font-semibold tabular-nums text-slate-100">
									{formatNumber(profile.transactions_per_day, 2)}
								</dd>
							</div>
						</dl>

						<div className="rounded-lg border border-dark-800 bg-dark-950/60 p-2.5 text-xs">
							<div className="flex items-center gap-1.5 text-[11px] text-slate-400">
								<Clock size={12} aria-hidden="true" />
								<span>Khung giờ hoạt động phổ biến (UTC)</span>
							</div>
							<div className="mt-1.5 flex flex-wrap gap-1.5">
								{profile.common_hours_utc && profile.common_hours_utc.length > 0 ? (
									profile.common_hours_utc.map((hour) => (
										<span
											key={hour}
											className="rounded border border-dark-700 bg-dark-900 px-2 py-0.5 font-mono text-[11px] text-slate-200"
										>
											{String(hour).padStart(2, '0')}:00 UTC
										</span>
									))
								) : (
									<span className="text-slate-500">--</span>
								)}
							</div>
						</div>
					</>
				)}
			</SectionCard>

			<SectionCard
				title={`Hồ sơ liên quan (${data.related_total})`}
				subtitle="Các hồ sơ bị gắn cờ khác của cùng người dùng"
			>
				<div className="space-y-2.5">
					{related.map((entry) => (
						<div
							key={entry.case_id}
							className="rounded-lg border border-dark-800 bg-dark-950/60 p-3 text-xs"
						>
							<div className="flex items-center justify-between gap-2">
								<Link
									className="break-all font-mono font-semibold text-brand-400 hover:underline"
									to={`/investigation/cases/${entry.case_id}`}
								>
									{entry.case_code}
								</Link>
								<StatusBadge value={entry.status} />
							</div>
							<p className="mt-1 break-all font-mono text-[11px] text-slate-400">
								Event: {entry.event_id}
							</p>
							<div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-300">
								<span className="font-mono tabular-nums">
									{formatCurrencyAmount(entry.amount)}
								</span>
								<span>{entry.assigned_to || 'Chưa giao'}</span>
							</div>
						</div>
					))}
					{!related.length && (
						<p className="text-xs text-slate-400">No other cases for this user.</p>
					)}
					{data.related_total > related.length && (
						<Link
							to={`/investigation?user=${encodeURIComponent(item.user_id)}`}
							className="inline-block text-xs font-medium text-brand-400 hover:underline"
						>
							Xem tất cả {data.related_total} hồ sơ liên quan trong hàng đợi &rarr;
						</Link>
					)}
				</div>
			</SectionCard>
		</div>
	);
}

export function EvidenceAndTimelineColumn({ data }: { data: Workbench }) {
	const { case: item, profile } = data;
	const [attrSearch, setAttrSearch] = useState('');

	const contributions = item.feature_contributions.map((feature) => ({
		...feature,
		display_name:
			feature.feature_name.length > 24
				? `${feature.feature_name.slice(0, 21)}...`
				: feature.feature_name,
		formatted_label: `${feature.feature_name} = ${String(feature.feature_value ?? 'null')}`,
	}));

	const points = profile.timeline.map((point) => ({
		...point,
		time: new Date(point.timestamp).getTime(),
	}));
	const { chartTokens } = useTheme();

	const filteredAttributes = Object.entries(item.attributes).filter(([key, value]) =>
		`${key} ${String(value)}`.toLowerCase().includes(attrSearch.toLowerCase())
	);

	const formatComparisonValue = (field: string, value: unknown): string => {
		if (value == null) {
			return '--';
		}
		if (field === 'amount' && typeof value === 'number') {
			return formatCurrencyAmount(value);
		}
		if (field === 'hour_utc') {
			if (Array.isArray(value)) {
				return value.map((h) => `${String(h).padStart(2, '0')}:00`).join(', ') || '--';
			}
			return `${String(value).padStart(2, '0')}:00 UTC`;
		}
		if (Array.isArray(value)) {
			return value.join(', ') || '--';
		}
		return String(value);
	};

	return (
		<div className="min-w-0 space-y-4">
			<SectionCard
				title="Bằng chứng kích hoạt (mô hình AI & động cơ luật)"
				subtitle="Giải thích đặc trưng cục bộ SHAP & ảnh chụp các luật nghiệp vụ bị vi phạm"
				badge={<StatusBadge value={item.final_action} />}
			>
				<div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-dark-800 bg-dark-950/60 p-3">
					<div>
						<p className="text-[11px] text-slate-400">Xác suất gian lận của mô hình AI</p>
						<p className="mt-0.5 text-xs text-slate-300">
							{item.model_version_id
								? `Phiên bản mô hình: ${item.model_version_id.slice(0, 8)}...`
								: 'Chỉ phát hiện bằng luật'}
						</p>
					</div>
					<div className="w-48">
						<ScoreBar score={item.model_score} />
					</div>
				</div>

				{contributions.length > 0 ? (
					<div className="space-y-1.5">
						<p className="text-xs font-medium text-slate-300">
							Đóng góp đặc trưng cục bộ hàng đầu (SHAP)
						</p>
						<div
							className="h-60 min-w-0 rounded-lg border border-dark-800 bg-dark-950/40 p-2"
							role="img"
							aria-label="Đóng góp đặc trưng cục bộ"
						>
							<ResponsiveContainer width="100%" height="100%">
								<BarChart
									data={contributions}
									layout="vertical"
									margin={{ left: 4, right: 20, top: 4, bottom: 4 }}
								>
									<CartesianGrid stroke={chartTokens.gridStroke} horizontal={false} />
									<XAxis
										type="number"
										tick={{ fill: chartTokens.axisTick, fontSize: 11 }}
									/>
									<YAxis
										type="category"
										dataKey="display_name"
										width={145}
										tick={{ fill: chartTokens.axisTick, fontSize: 11 }}
									/>
									<Tooltip
										formatter={(value, _name, itemPayload) => [
											`${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(4)}`,
											itemPayload?.payload?.formatted_label || 'Đóng góp',
										]}
										contentStyle={{
											background: chartTokens.tooltipBg,
											borderColor: chartTokens.tooltipBorder,
											color: chartTokens.tooltipText,
											fontSize: '12px',
										}}
									/>
									<Bar dataKey="contribution" isAnimationActive={false}>
										{contributions.map((feature, index) => (
											<Cell
												key={index}
												fill={feature.contribution > 0 ? '#f87171' : '#34d399'}
											/>
										))}
									</Bar>
								</BarChart>
							</ResponsiveContainer>
						</div>
					</div>
				) : (
					<p className="rounded-lg border border-dark-800 bg-dark-950/40 p-3 text-xs text-slate-400">
						Chưa có giải thích mô hình cục bộ (SHAP) cho giao dịch này.
					</p>
				)}

				<div className="space-y-2.5 pt-1">
					<p className="text-xs font-medium text-slate-300">
						Luật phát hiện đã kích hoạt ({item.triggered_rules.length})
					</p>
					{item.triggered_rules.map((rule) => (
						<div
							key={rule.rule_version_id}
							className="rounded-lg border border-dark-700/80 bg-dark-950/70 p-3 text-xs"
						>
							<div className="flex flex-wrap items-center justify-between gap-2">
								<div>
									<span className="font-mono font-bold text-brand-300">
										{rule.rule_code}
									</span>
									<span className="ml-2 font-mono text-[11px] text-slate-400">
										v{rule.version_number}
									</span>
									{rule.rule_name && (
										<span className="ml-2 text-slate-200">— {rule.rule_name}</span>
									)}
								</div>
								<StatusBadge value={rule.action} />
							</div>
							<p className="mt-1.5 break-words text-slate-300">{rule.trigger_reason}</p>
							{rule.matched_clauses?.length > 0 && (
								<div className="mt-2 space-y-1 rounded border border-dark-800 bg-dark-900 p-2">
									{rule.matched_clauses.map((clause, index) => (
										<p
											key={index}
											className="break-all font-mono text-[11px] text-amber-200"
										>
											{clause}
										</p>
									))}
								</div>
							)}
						</div>
					))}
					{!item.triggered_rules.length && (
						<p className="text-xs text-slate-400">No triggered rules in snapshot.</p>
					)}
				</div>
			</SectionCard>

			<SectionCard
				title="Dòng thời gian hành vi tương tác"
				subtitle="Chuỗi thời gian giao dịch của người dùng liên quan (Xám: lịch sử, Đỏ: hồ sơ hiện tại)"
			>
				<div
					className="h-60 min-w-0 rounded-lg border border-dark-800 bg-dark-950/40 p-2"
					role="img"
					aria-label="Giao dịch lịch sử và giao dịch bị gắn cờ hiện tại"
				>
					{points.length > 0 ? (
						<ResponsiveContainer width="100%" height="100%">
							<ScatterChart margin={{ right: 16, left: 0, bottom: 10, top: 8 }}>
								<CartesianGrid stroke={chartTokens.gridStroke} />
								<XAxis
									type="number"
									dataKey="time"
									domain={['dataMin', 'dataMax']}
									tickFormatter={(value) => new Date(value).toLocaleDateString()}
									tick={{ fill: chartTokens.axisTick, fontSize: 10 }}
								/>
								<YAxis
									type="number"
									dataKey="amount"
									width={72}
									tick={{ fill: chartTokens.axisTick, fontSize: 10 }}
								/>
								<Tooltip
									cursor={{ strokeDasharray: '3 3' }}
									labelFormatter={(value) => new Date(Number(value)).toLocaleString()}
									contentStyle={{
										background: chartTokens.tooltipBg,
										borderColor: chartTokens.tooltipBorder,
										color: chartTokens.tooltipText,
										fontSize: '12px',
									}}
								/>
								<Scatter
									data={points.filter((point) => !point.is_current)}
									fill="#94a3b8"
									name="Lịch sử"
									isAnimationActive={false}
								/>
								<Scatter
									data={points.filter((point) => point.is_current)}
									fill="#f87171"
									name="Hồ sơ hiện tại"
									isAnimationActive={false}
								/>
							</ScatterChart>
						</ResponsiveContainer>
					) : (
						<p className="p-4 text-xs text-slate-400">
							Chưa có lịch sử giao dịch để hiển thị dòng thời gian.
						</p>
					)}
				</div>
				{profile.timeline_truncated && (
					<p className="text-xs text-amber-300">
						Đang hiển thị 500 giao dịch gần nhất trong khoảng thời gian đã chọn.
					</p>
				)}
			</SectionCard>

			<SectionCard
				title="Chênh lệch hiện tại so với đường cơ sở"
				subtitle="Đối chiếu thuộc tính hành vi với hồ sơ lịch sử"
			>
				<div className="overflow-x-auto">
					<table className="w-full text-left text-xs">
						<caption className="sr-only">Behavioral comparison</caption>
						<thead className="border-b border-dark-700/80 text-[11px] uppercase text-slate-400">
							<tr>
								<th scope="col" className="py-2 pr-3">Attribute</th>
								<th scope="col" className="py-2 pr-3">Current Value</th>
								<th scope="col" className="py-2 pr-3">Đường cơ sở lịch sử</th>
								<th scope="col" className="py-2 text-right">Trạng thái</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-dark-800">
							{profile.comparison.map((row) => {
								const amountRatio =
									row.field === 'amount' &&
									typeof row.current === 'number' &&
									typeof row.baseline === 'number' &&
									row.baseline > 0
										? `${(row.current / row.baseline).toFixed(1)}x avg`
										: null;
								return (
									<tr key={row.field} className={row.is_anomalous ? 'bg-rose-950/20' : ''}>
										<td className="py-2.5 pr-3 font-medium text-slate-200">
											{formatLabel(row.field)}
										</td>
										<td
											className={`max-w-44 break-all py-2.5 pr-3 font-mono ${
												row.is_anomalous ? 'font-semibold text-rose-300' : 'text-slate-100'
											}`}
										>
											{formatComparisonValue(row.field, row.current)}
											{amountRatio && (
												<span className="ml-1.5 rounded bg-dark-800 px-1.5 py-0.5 text-[10px] text-amber-300">
													{amountRatio}
												</span>
											)}
										</td>
										<td className="max-w-48 break-words py-2.5 pr-3 font-mono text-slate-400">
											{formatComparisonValue(row.field, row.baseline)}
										</td>
										<td className="py-2.5 text-right">
											{row.is_anomalous ? (
												<span className="inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-rose-300">
													<AlertTriangle size={11} aria-label="Bất thường" />
													<span>Bất thường</span>
												</span>
											) : (
												<span className="text-[11px] text-slate-400">Normal</span>
											)}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			</SectionCard>

			<SectionCard
				title="Ảnh chụp thuộc tính giao dịch"
				subtitle={`${Object.keys(item.attributes).length} captured attributes at detection time`}
				actions={
					<div className="relative w-44">
						<Search
							size={13}
							className="pointer-events-none absolute left-2.5 top-2.5 text-slate-500"
						/>
						<input
							aria-label="Lọc thuộc tính giao dịch"
							placeholder="Lọc thuộc tính..."
							className={`${INPUT_CLASS} pl-7 py-1 text-xs`}
							value={attrSearch}
							onChange={(event) => setAttrSearch(event.target.value)}
						/>
					</div>
				}
			>
				{filteredAttributes.length > 0 ? (
					<dl className="grid max-h-64 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
						{filteredAttributes.map(([key, value]) => (
							<div
								key={key}
								className="rounded-lg border border-dark-800 bg-dark-950/60 px-3 py-2 text-xs"
							>
								<dt className="break-all font-mono text-[11px] text-slate-400">{key}</dt>
								<dd className="mt-0.5 break-all font-mono font-medium text-slate-100">
									{value == null ? 'null' : String(value)}
								</dd>
							</div>
						))}
					</dl>
				) : (
					<p className="text-xs text-slate-400">No matching attributes found.</p>
				)}
			</SectionCard>
		</div>
	);
}

