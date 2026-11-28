import React, { useState } from 'react';
import {
	AlertOctagon,
	Clock,
	Fingerprint,
	Grid3X3,
	Layers,
	ShieldAlert,
	UserX,
} from 'lucide-react';
import {
	Bar,
	CartesianGrid,
	Cell,
	ComposedChart,
	Legend,
	Line,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import { useTheme } from '@/hooks';
import type { TypologiesPatternsData } from '@/types';
import { MetricInfoTooltip } from './MetricInfoTooltip';

interface TypologiesPatternsTabProps {
	data?: TypologiesPatternsData;
	isLoading: boolean;
}

const TYPOLOGY_LABELS_VI: Record<string, string> = {
	CARD_TESTING: 'Thử thẻ / Dò giao dịch nhỏ (Card Testing)',
	VELOCITY_ATTACK: 'Tấn công tần suất cao (Velocity Attack)',
	ACCOUNT_TAKEOVER: 'Chiếm đoạt tài khoản (ATO)',
	DEVICE_SHARING_RING: 'Nhóm dùng chung thiết bị gian lận',
	COLLUSIVE_MERCHANT: 'Đơn vị chấp nhận thẻ thông đồng',
	OTHER_FRAUD: 'Gian lận giá trị cao / Bất thường khác',
	LEGITIMATE_UNUSUAL_SPENDING: 'Chi tiêu hợp lệ bất thường / Du lịch',
	CUSTOMER_CONFIRMED: 'Khách hàng xác nhận giao dịch hợp lệ',
	OVERLY_STRICT_RULE: 'Ngưỡng luật quá chặt',
	MODEL_FALSE_ALARM: 'Cảnh báo nhầm từ mô hình AI',
	OTHER_LEGITIMATE: 'Hoạt động hợp lệ khác',
};

const SEGMENT_PILLS: { key: string; label: string }[] = [
	{ key: 'amount_brackets', label: 'Khoảng số tiền' },
	{ key: 'merchant_category', label: 'Ngành hàng (MCC)' },
	{ key: 'merchant_id', label: 'Merchant' },
	{ key: 'device_id', label: 'Thiết bị' },
	{ key: 'ip_address', label: 'Địa chỉ IP' },
	{ key: 'card_id', label: 'Thẻ' },
];

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const TypologiesPatternsTab: React.FC<TypologiesPatternsTabProps> = ({ data, isLoading }) => {
	const { chartTokens } = useTheme();
	const [activeDimension, setActiveDimension] = useState<string>('amount_brackets');

	if (isLoading) {
		return (
			<div className="space-y-4 animate-pulse">
				<div className="h-56 bg-dark-900 border border-dark-700/80 rounded-xl" />
				<div className="h-72 bg-dark-900 border border-dark-700/80 rounded-xl" />
			</div>
		);
	}

	if (!data) {
		return null;
	}

	const fraudTypologies = (data.typology_breakdown || []).filter((i) => i.case_count > 0);
	const fpReasons = (data.fp_reason_breakdown || []).filter((i) => i.case_count > 0);
	const hourlyProfile = (data.hourly_distribution || []).map((h) => ({
		...h,
		confirmed_fraud_pct: Number(((h.confirmed_fraud_rate ?? h.fraud_rate ?? 0) * 100).toFixed(2)),
		flagged_rate_pct: Number(((h.flagged_rate ?? 0) * 100).toFixed(2)),
	}));
	const peakHours = hourlyProfile.filter((h) => h.is_peak_risk);
	const segmentAnalytics = data.segment_analytics || {};
	const currentDim = segmentAnalytics[activeDimension] || segmentAnalytics.amount_brackets;
	const topSubjects = data.top_flagged_subjects || [];
	const watchlistSummary = data.watchlist_summary;

	return (
		<div className="space-y-6">
			{/* Hàng 1: Loại hình gian lận vs Nguyên nhân gốc dương tính giả */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<AlertOctagon size={15} className="text-emerald-400" aria-hidden="true" />
							<span>Loại hình gian lận đã xác nhận</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Phân bổ các vụ việc đã kết luận gian lận theo mã kịch bản nghiệp vụ
						</p>
					</div>

					{fraudTypologies.length === 0 ? (
						<div className="py-10 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Chưa ghi nhận hồ sơ gian lận đã xử lý.
						</div>
					) : (
						<div className="space-y-3">
							{fraudTypologies.map((item) => {
								const pct = (item.pct ?? 0) * 100;
								return (
									<div key={item.code} className="bg-dark-950 border border-dark-800 rounded-lg p-3">
										<div className="flex items-center justify-between text-xs mb-1.5">
											<span className="font-semibold text-slate-200">
												{TYPOLOGY_LABELS_VI[item.code] || item.label}
											</span>
											<div className="flex items-center gap-3 font-mono tabular-nums">
												<span className="text-slate-300">{item.case_count} hồ sơ</span>
												<span className="text-emerald-400 font-semibold">{formatCurrency(item.total_amount)}</span>
												<span className="text-slate-400 w-12 text-right">{pct.toFixed(1)}%</span>
											</div>
										</div>
										<div className="w-full h-2 bg-dark-800 rounded-full overflow-hidden">
											<div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
										</div>
									</div>
								);
							})}
						</div>
					)}
				</div>

				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Layers size={15} className="text-rose-400" aria-hidden="true" />
							<span>Nguyên nhân gốc dương tính giả (FP)</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Phân bố hồ sơ hợp lệ theo nguyên nhân gây báo động nhầm
						</p>
					</div>

					{fpReasons.length === 0 ? (
						<div className="py-10 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Chưa ghi nhận hồ sơ dương tính giả đã xử lý.
						</div>
					) : (
						<div className="space-y-3">
							{fpReasons.map((item) => {
								const pct = (item.pct ?? 0) * 100;
								return (
									<div key={item.code} className="bg-dark-950 border border-dark-800 rounded-lg p-3">
										<div className="flex items-center justify-between text-xs mb-1.5">
											<span className="font-semibold text-slate-200">
												{TYPOLOGY_LABELS_VI[item.code] || item.label}
											</span>
											<div className="flex items-center gap-3 font-mono tabular-nums">
												<span className="text-slate-300">{item.case_count} hồ sơ</span>
												<span className="text-rose-400 font-semibold">{formatCurrency(item.total_amount)}</span>
												<span className="text-slate-400 w-12 text-right">{pct.toFixed(1)}%</span>
											</div>
										</div>
										<div className="w-full h-2 bg-dark-800 rounded-full overflow-hidden">
											<div className="h-full bg-rose-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
										</div>
									</div>
								);
							})}
						</div>
					)}
				</div>
			</div>

			{/* Hàng 2: Hồ sơ rủi ro 24 giờ (UTC) tách riêng 2 đường */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex flex-wrap items-center justify-between gap-2 mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Clock size={15} className="text-amber-400" aria-hidden="true" />
							<span>Hồ sơ rủi ro 24 giờ (UTC)</span>
							<MetricInfoTooltip
								title="Tỷ lệ gian lận thực tế vs Tỷ lệ bị gắn cờ"
								formula="Fraud Rate = Confirmed Fraud / Total Tx · Flagged Rate = Flagged / Total Tx"
								meaning="Tách riêng tỷ lệ gian lận đã xác nhận (đỏ) với tỷ lệ bị gắn cờ (vàng nét đứt) để nhận biết khung giờ bị báo giả nhiều."
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Khối lượng giao dịch và tách biệt tỷ lệ gian lận thực tế so với tỷ lệ gắn cờ qua 24 khung giờ
						</p>
					</div>
					{peakHours.length > 0 && (
						<div className="flex items-center gap-2 text-xs font-mono bg-rose-500/10 border border-rose-500/30 text-rose-300 px-3 py-1 rounded-lg">
							<span>Khung rủi ro cao điểm (UTC):</span>
							<span className="font-bold">{peakHours.map((h) => h.label).join(', ')}</span>
						</div>
					)}
				</div>

				<div className="h-64 w-full">
					<ResponsiveContainer width="100%" height="100%">
						<ComposedChart data={hourlyProfile} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
							<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
							<XAxis dataKey="label" stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} interval={1} />
							<YAxis yAxisId="left" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
							<YAxis yAxisId="right" orientation="right" stroke="#F43F5E" tick={{ fontSize: 11 }} unit="%" />
							<Tooltip
								contentStyle={{
									backgroundColor: chartTokens.tooltipBg,
									borderColor: chartTokens.tooltipBorder,
									color: chartTokens.tooltipText,
									borderRadius: '0.5rem',
									fontSize: '12px',
								}}
							/>
							<Legend wrapperStyle={{ fontSize: '12px' }} />
							<Bar yAxisId="left" dataKey="total_tx_count" name="Tổng giao dịch" radius={[3, 3, 0, 0]}>
								{hourlyProfile.map((entry) => (
									<Cell key={`cell-${entry.hour}`} fill={entry.is_peak_risk ? '#F59E0B' : chartTokens.inactiveBar} />
								))}
							</Bar>
							<Line
								yAxisId="right"
								type="monotone"
								dataKey="confirmed_fraud_pct"
								name="Tỷ lệ gian lận thực tế (%)"
								stroke="#F43F5E"
								strokeWidth={2}
								dot={{ r: 2.5 }}
							/>
							<Line
								yAxisId="right"
								type="monotone"
								dataKey="flagged_rate_pct"
								name="Tỷ lệ bị gắn cờ (%)"
								stroke="#F59E0B"
								strokeDasharray="4 4"
								strokeWidth={1.8}
								dot={false}
							/>
						</ComposedChart>
					</ResponsiveContainer>
				</div>
			</div>

			{/* Hàng 3: Ma trận Rủi ro & Hiệu quả theo Phân khúc (Segment Alert Hit-Rate) */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
				<div className="flex flex-wrap items-center justify-between gap-3">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Grid3X3 size={15} className="text-emerald-400" aria-hidden="true" />
							<span>Ma trận rủi ro & hiệu quả theo phân khúc (Segment Alert Hit-Rate)</span>
							<MetricInfoTooltip
								title="Ma trận phân khúc & Lift"
								formula="Hit Rate = TP / Flagged · Detection Rate = TP / (TP + FN) · Lift = Fraud Rate phân khúc / Trung bình chung"
								meaning="Khoanh vùng ổ gian lận (Lift ≥ 2,0×) hoặc phân khúc nhiều báo động giả để viết luật riêng hoặc gắn danh sách theo dõi."
								benchmark="Lift ≥ 2,0× → Điểm nóng rủi ro"
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Phân tích 6 chiều thực thể từ kho dữ liệu dự án
						</p>
					</div>
					<div className="flex flex-wrap items-center gap-1.5">
						{SEGMENT_PILLS.map((pill) => {
							const dim = segmentAnalytics[pill.key];
							const isAvailable = dim ? dim.available : pill.key === 'amount_brackets';
							const isActive = activeDimension === pill.key;
							return (
								<button
									key={pill.key}
									type="button"
									disabled={!isAvailable}
									onClick={() => setActiveDimension(pill.key)}
									className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
										!isAvailable
											? 'bg-dark-950 border-dark-800 text-slate-600 cursor-not-allowed opacity-60'
											: isActive
												? 'bg-brand-600 border-brand-500 text-white cursor-pointer'
												: 'bg-dark-950 border-dark-700 text-slate-300 hover:bg-dark-800 cursor-pointer'
									}`}
								>
									{pill.label}
								</button>
							);
						})}
					</div>
				</div>

				{!currentDim || !currentDim.available || currentDim.items.length === 0 ? (
					<div className="py-8 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
						Chưa có dữ liệu phân khúc cho chiều đã chọn trong tập dữ liệu hiện tại.
					</div>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-left border-collapse">
							<thead>
								<tr className="border-b border-dark-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
									<th className="py-2 px-3">Phân khúc</th>
									<th className="py-2 px-3 text-right">Tổng GD</th>
									<th className="py-2 px-3 text-right">Alert Rate</th>
									<th className="py-2 px-3 text-right">Hit Rate</th>
									<th className="py-2 px-3 text-right">Detection Rate</th>
									<th className="py-2 px-3 text-right">Lọt lưới ($)</th>
									<th className="py-2 px-3 text-right">Lift</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800/60 text-xs font-mono tabular-nums">
								{currentDim.items.map((item) => (
									<tr key={item.segment_value} className="hover:bg-dark-800/40">
										<td className="py-2.5 px-3 font-semibold text-slate-100">
											<div className="flex items-center gap-2">
												<span>{item.label}</span>
												{item.is_small_sample && (
													<span className="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px]">
														Mẫu nhỏ
													</span>
												)}
											</div>
										</td>
										<td className="py-2.5 px-3 text-right text-slate-300">{item.total_count.toLocaleString()}</td>
										<td className="py-2.5 px-3 text-right text-amber-300">{(item.alert_rate * 100).toFixed(1)}%</td>
										<td className="py-2.5 px-3 text-right text-cyan-300">
											{item.hit_rate != null ? `${(item.hit_rate * 100).toFixed(1)}%` : '—'}
										</td>
										<td className="py-2.5 px-3 text-right text-emerald-400">
											{item.detection_rate != null ? `${(item.detection_rate * 100).toFixed(1)}%` : '—'}
										</td>
										<td className="py-2.5 px-3 text-right text-rose-400">
											{item.missed_fraud_amount != null ? formatCurrency(item.missed_fraud_amount) : '—'}
										</td>
										<td className="py-2.5 px-3 text-right">
											{item.lift != null ? (
												<span
													className={`px-2 py-0.5 rounded font-semibold ${
														item.lift >= 2.0
															? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
															: 'text-slate-200'
													}`}
												>
													{item.lift.toFixed(1)}×
												</span>
											) : (
												'—'
											)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</div>

			{/* Hàng 4: Top Đối tượng rủi ro (7/12) + Tác động Danh sách đen (5/12) */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<UserX size={15} className="text-rose-400" aria-hidden="true" />
							<span>Top đối tượng rủi ro (user_id)</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Đếm đầy đủ tổng giao dịch thật của từng người dùng kèm số giao dịch bị gắn cờ
						</p>
					</div>

					{topSubjects.length === 0 ? (
						<div className="py-8 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Không có đối tượng bị gắn cờ trong phạm vi đã chọn.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<thead>
									<tr className="border-b border-dark-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
										<th className="py-2 px-2.5">Người dùng</th>
										<th className="py-2 px-2.5 text-right">Tổng GD</th>
										<th className="py-2 px-2.5 text-right">Bị gắn cờ</th>
										<th className="py-2 px-2.5 text-right">Gian lận</th>
										<th className="py-2 px-2.5 text-right">Phơi nhiễm ($)</th>
										<th className="py-2 px-2.5 text-right">Điểm cao nhất</th>
										<th className="py-2 px-2.5 text-center">Danh sách đen</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/60 text-xs font-mono tabular-nums">
									{topSubjects.map((sub) => (
										<tr key={sub.user_id} className="hover:bg-dark-800/40">
											<td className="py-2 px-2.5 font-semibold text-slate-100">{sub.user_id}</td>
											<td className="py-2 px-2.5 text-right text-slate-300">{sub.total_tx_count} GD</td>
											<td className="py-2 px-2.5 text-right text-amber-300">{sub.flagged_tx_count}</td>
											<td className="py-2 px-2.5 text-right text-emerald-400 font-semibold">{sub.confirmed_fraud_count}</td>
											<td className="py-2 px-2.5 text-right text-amber-300">{formatCurrency(sub.amount_at_risk)}</td>
											<td className="py-2 px-2.5 text-right text-slate-200">{(sub.max_model_score ?? 0).toFixed(3)}</td>
											<td className="py-2 px-2.5 text-center">
												{sub.is_blacklisted ? (
													<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[10px]">
														<ShieldAlert size={10} aria-hidden="true" />
														<span>ĐANG CHẶN</span>
													</span>
												) : (
													<span className="text-slate-500 text-[11px]">—</span>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</div>

				{/* Tác động Danh sách đen (Watchlist Impact) */}
				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<ShieldAlert size={15} className="text-amber-400" aria-hidden="true" />
							<span>Tác động danh sách đen (Watchlist Impact)</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Mức độ phủ của thực thể trong EntityBlacklist lên các giao dịch quét
						</p>
					</div>

					<div className="grid grid-cols-2 gap-3 font-mono tabular-nums">
						<div className="bg-dark-950 border border-rose-500/30 rounded-lg p-3">
							<div className="text-[11px] text-slate-400">Đang chặn / Đã gỡ</div>
							<div className="text-xl font-bold text-rose-300 mt-1">
								{watchlistSummary?.active_blacklist_count ?? 0}
								<span className="text-xs text-slate-400 font-normal ml-1.5">
									/ {watchlistSummary?.removed_blacklist_count ?? 0} đã gỡ
								</span>
							</div>
						</div>
						<div className="bg-dark-950 border border-amber-500/30 rounded-lg p-3">
							<div className="text-[11px] text-slate-400">Giao dịch liên quan</div>
							<div className="text-xl font-bold text-amber-300 mt-1">
								{(watchlistSummary?.matched_tx_count ?? 0).toLocaleString()} GD
							</div>
							<div className="text-[11px] text-slate-400">
								{formatCurrency(watchlistSummary?.matched_amount)}
							</div>
						</div>
					</div>

					{watchlistSummary?.by_entity_type && watchlistSummary.by_entity_type.length > 0 && (
						<div className="flex flex-wrap items-center gap-2">
							{watchlistSummary.by_entity_type.map((item) => (
								<div
									key={item.entity_type}
									className="px-2.5 py-1 rounded-lg bg-dark-950 border border-dark-800 text-xs font-mono flex items-center gap-2"
								>
									<Fingerprint size={12} className="text-brand-400" aria-hidden="true" />
									<span className="text-slate-300">{item.entity_type}:</span>
									<span className="text-slate-100 font-bold">{item.active_count}</span>
								</div>
							))}
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
