import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { API, server } from '@/test/server';
import type {
	EffectivenessAnalysisData,
	ExecutiveAuditReportData,
	ExecutiveOverviewData,
	TypologiesPatternsData,
} from '@/types';
import { ComplianceReportCenterTab } from './ComplianceReportCenterTab';
import { EffectivenessTab } from './EffectivenessTab';
import { ExecutiveOverviewTab } from './ExecutiveOverviewTab';
import { TypologiesPatternsTab } from './TypologiesPatternsTab';

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';

beforeAll(() => {
	if (typeof globalThis.ResizeObserver === 'undefined') {
		globalThis.ResizeObserver = class ResizeObserver {
			observe() {}
			unobserve() {}
			disconnect() {}
		};
	}
});

function makeOverviewPayload(verifiedOnly = false): ExecutiveOverviewData {
	return {
		kpis: {
			gross_scanned_volume: 18000,
			gross_scanned_count: 100,
			amount_at_risk: 10000,
			flagged_tx_count: 35,
			flagged_rate: 0.35,
			reject_count: 15,
			review_count: 20,
			confirmed_fraud_loss_prevented: 8000,
			confirmed_fraud_count: 20,
			missed_fraud_amount: verifiedOnly ? null : 2000,
			missed_fraud_count: verifiedOnly ? null : 5,
			value_detection_rate: verifiedOnly ? null : 0.8,
			net_fraud_loss_bps: verifiedOnly ? null : 1111.11,
			false_positive_friction_volume: 2000,
			false_positive_count: 15,
			hard_false_decline_amount: 1000,
			hard_false_decline_count: 5,
			soft_review_friction_amount: 1000,
			soft_review_friction_count: 10,
			customer_insult_rate: verifiedOnly ? null : 0.2,
			insult_rate: verifiedOnly ? 0 : 0.2,
			volume_insult_rate: verifiedOnly ? null : 0.25,
			hard_insult_rate: verifiedOnly ? null : 0.0667,
			soft_insult_rate: verifiedOnly ? null : 0.1333,
			verified_precision: 0.5714,
			alert_to_fraud_ratio: 1.75,
			alert_to_fraud_label: '1.8 : 1',
			case_resolution_rate: 0.5,
			total_cases: 4,
			resolved_cases: 2,
			open_cases: 2,
			in_progress_cases: 0,
			pending_customer_cases: 0,
			critical_high_backlog: 1,
			mttr_p50_hours: 18.0,
			mttr_p90_hours: 72.0,
			sla_breach_count: 1,
			sla_breach_rate: 0.25,
			label_source: verifiedOnly ? 'VERIFIED_ONLY' : 'VERIFIED_WITH_DATASET_FALLBACK',
			ground_truth_coverage: verifiedOnly ? 'FLAGGED_ONLY' : 'FULL',
			has_dataset_labels: true,
		},
		funnel: [
			{ stage: 'SCANNED', label: '1. Tổng giao dịch quét', tx_count: 100, amount: 18000, conversion_rate: 1.0 },
			{ stage: 'FLAGGED', label: '2. Bị gắn cờ (REJECT / REVIEW)', tx_count: 35, amount: 10000, conversion_rate: 0.35 },
			{ stage: 'DISPATCHED', label: '3. Chuyển hồ sơ điều tra', tx_count: 4, amount: 2000, conversion_rate: 0.04 },
			{ stage: 'RESOLVED', label: '4. Đã xử lý & kết luận', tx_count: 2, amount: 1200, conversion_rate: 0.02 },
		],
		financial_trends: [
			{
				date: '2026-11-01',
				label: '2026-11-01',
				granularity: 'DAY',
				job_id: '2026-11-01',
				job_name: '2026-11-01',
				created_at: '2026-11-01T00:00:00Z',
				scanned_count: 100,
				scanned_amount: 18000,
				flagged_count: 35,
				confirmed_fraud_amount: 8000,
				missed_fraud_amount: verifiedOnly ? null : 2000,
				false_positive_amount: 2000,
				pending_review_amount: 0,
				flagged_rate: 0.35,
				fraud_rate: 0.2,
			},
		],
		financial_trends_granularity: 'DAY',
		case_sla: {
			mttr_p50_hours: 18.0,
			mttr_p90_hours: 72.0,
			resolved_with_duration_count: 2,
			sla_breach_count: 1,
			eligible_sla_cases: 4,
			sla_breach_rate: 0.25,
			sla_thresholds_hours: { CRITICAL: 4, HIGH: 24, MEDIUM: 72 },
			aging_buckets: [
				{ bucket: 'LT_4H', label: '< 4 giờ', count: 1, amount: 500 },
				{ bucket: '4H_24H', label: '4–24 giờ', count: 1, amount: 300 },
				{ bucket: '1D_3D', label: '1–3 ngày', count: 0, amount: 0 },
				{ bucket: 'GT_3D', label: '> 3 ngày', count: 0, amount: 0 },
			],
			analyst_stats: [
				{
					analyst: 'analyst_a',
					resolved_count: 2,
					fraud_count: 1,
					legit_count: 1,
					fraud_rate: 0.5,
					avg_mttr_hours: 18.0,
					median_mttr_hours: 18.0,
					sla_breach_count: 1,
				},
			],
		},
		queue_breakdown: {
			by_status: [{ status: 'OPEN', label: 'Mới mở', count: 2, amount: 800 }],
			by_priority: [
				{
					priority: 'CRITICAL',
					open_count: 1,
					in_progress_count: 0,
					resolved_fraud_count: 1,
					resolved_legitimate_count: 0,
					total_count: 2,
					total_amount: 1000,
				},
			],
		},
		available_jobs: [],
	};
}

function makeEffectivenessPayload(): EffectivenessAnalysisData {
	const curve = Array.from({ length: 19 }, (_, idx) => {
		const t = Number(((idx + 1) * 0.05).toFixed(2));
		const scale = Math.max(1, Math.round(20 - idx));
		return {
			threshold: t,
			review_queue_volume: scale * 2,
			hybrid_queue_volume: scale * 2 + 5,
			caught_fraud_count: Math.max(1, Math.round(scale * 0.8)),
			caught_fraud_amount: scale * 400,
			false_positive_count: Math.max(0, scale - 1),
			false_positive_amount: scale * 50,
			estimated_recall: 0.75,
			estimated_precision: 0.55,
			fp_reduction_pct: 0.25,
			model_only: {
				flagged_count: scale * 2,
				flagged_tp_count: Math.max(1, Math.round(scale * 0.7)),
				flagged_tp_amount: scale * 350,
				flagged_fp_count: scale,
				flagged_fp_amount: scale * 50,
				reject_count: Math.max(1, Math.round(scale * 0.5)),
				reject_tp_count: Math.max(1, Math.round(scale * 0.4)),
				reject_tp_amount: scale * 200,
				reject_fp_count: Math.max(0, Math.round(scale * 0.2)),
				reject_fp_amount: scale * 20,
			},
			hybrid: {
				flagged_count: scale * 2 + 5,
				flagged_tp_count: Math.max(1, Math.round(scale * 0.8)),
				flagged_tp_amount: scale * 420,
				flagged_fp_count: scale + 2,
				flagged_fp_amount: scale * 60,
				reject_count: Math.max(1, Math.round(scale * 0.6)) + 2,
				reject_tp_count: Math.max(1, Math.round(scale * 0.5)) + 1,
				reject_tp_amount: scale * 260,
				reject_fp_count: Math.max(0, Math.round(scale * 0.3)),
				reject_fp_amount: scale * 30,
			},
		};
	});

	return {
		attribution: {
			total_caught_fraud_count: 20,
			total_caught_fraud_amount: 8000,
			ai_exclusive_catch_rate: 0.4,
			rule_exclusive_catch_rate: 0.2,
			consensus_overlap_rate: 0.4,
			segments: [
				{ segment: 'AI_EXCLUSIVE', label: 'Chỉ mô hình AI bắt', fraud_count: 8, count_pct: 0.4, fraud_amount: 3200, amount_pct: 0.4 },
				{ segment: 'CONSENSUS_OVERLAP', label: 'Đồng thuận kết hợp (AI + Luật)', fraud_count: 8, count_pct: 0.4, fraud_amount: 3200, amount_pct: 0.4 },
				{ segment: 'RULE_EXCLUSIVE', label: 'Chỉ luật nghiệp vụ bắt', fraud_count: 4, count_pct: 0.2, fraud_amount: 1600, amount_pct: 0.2 },
			],
		},
		rule_leaderboard: [
			{
				rule_id: 'r1',
				rule_code: 'R_UNIQUE_VEL',
				rule_name: 'Tốc độ bất thường',
				status: 'ACTIVE',
				action: 'REJECT',
				version_number: 1,
				total_hits: 10,
				verified_cases: 10,
				verified_tp: 8,
				verified_fp: 2,
				pending_cases: 0,
				fraud_value_caught: 3000,
				false_positive_value: 200,
				unique_catch_count: 2,
				unique_catch_amount: 950,
				hit_rate: 0.1,
				verified_precision: 0.8,
				false_alert_rate: 0.2,
				verified_fpr: 0.2,
				is_small_sample: true,
				fp_samples: [
					{
						event_id: 'FP-S1',
						user_id: 'U-FP-1',
						amount: 120,
						model_score: 0.25,
						final_action: 'REJECT',
						tx_timestamp: '2026-11-01 10:00:00',
						case_id: null,
					},
				],
				policy_health_tag: 'HIGH_VALUE',
			},
		],
		fn_samples: [
			{
				event_id: 'FN-S1',
				user_id: 'U-FN-1',
				amount: 1500,
				model_score: 0.18,
				final_action: 'ALLOW',
				tx_timestamp: '2026-11-01 11:00:00',
				case_id: null,
			},
		],
		score_calibration: [
			{
				bin: '0.0-0.1',
				lower: 0,
				upper: 0.1,
				total_count: 40,
				verified_count: 40,
				confirmed_fraud_count: 1,
				legit_count: 39,
				false_positive_count: 0,
				unverified_count: 0,
				fraud_amount: 100,
				false_positive_amount: 0,
				mean_predicted_score: 0.05,
				observed_fraud_rate: 0.025,
			},
			{
				bin: '0.9-1.0',
				lower: 0.9,
				upper: 1.0,
				total_count: 20,
				verified_count: 20,
				confirmed_fraud_count: 18,
				legit_count: 2,
				false_positive_count: 2,
				unverified_count: 0,
				fraud_amount: 6000,
				false_positive_amount: 200,
				mean_predicted_score: 0.94,
				observed_fraud_rate: 0.9,
			},
		],
		score_calibration_modes: {
			equal_width: [
				{
					bin: '0.0-0.1',
					lower: 0,
					upper: 0.1,
					total_count: 40,
					verified_count: 40,
					confirmed_fraud_count: 1,
					legit_count: 39,
					false_positive_count: 0,
					unverified_count: 0,
					fraud_amount: 100,
					false_positive_amount: 0,
					mean_predicted_score: 0.05,
					observed_fraud_rate: 0.025,
				},
			],
			equal_count: [
				{
					bin: 'D1 (0.01–0.10)',
					lower: 0.01,
					upper: 0.1,
					total_count: 30,
					verified_count: 30,
					confirmed_fraud_count: 1,
					legit_count: 29,
					false_positive_count: 0,
					unverified_count: 0,
					fraud_amount: 100,
					false_positive_amount: 0,
					mean_predicted_score: 0.05,
					observed_fraud_rate: 0.033,
				},
			],
		},
		model_health: {
			brier_score: 0.042,
			ece: 0.031,
			ks_statistic: 0.68,
			evaluated_count: 100,
			psi: 0.31,
			psi_status: 'SIGNIFICANT_SHIFT',
		},
		lift_gain_curve: [
			{ top_pct: 1, label: 'Top 1%', tx_count: 1, fraud_count_caught: 1, fraud_amount_caught: 1000, gain_count_pct: 0.05, gain_amount_pct: 0.1, lift: 5.0, precision: 1.0 },
			{ top_pct: 5, label: 'Top 5%', tx_count: 5, fraud_count_caught: 5, fraud_amount_caught: 4000, gain_count_pct: 0.25, gain_amount_pct: 0.4, lift: 5.0, precision: 1.0 },
			{ top_pct: 10, label: 'Top 10%', tx_count: 10, fraud_count_caught: 10, fraud_amount_caught: 6500, gain_count_pct: 0.5, gain_amount_pct: 0.65, lift: 5.0, precision: 1.0 },
		],
		score_drift: {
			psi: 0.31,
			status: 'SIGNIFICANT_SHIFT',
			baseline_count: 50,
			current_count: 50,
			bins: [
				{ bin: '0.0-0.1', baseline_count: 25, current_count: 5, baseline_pct: 0.5, current_pct: 0.1, psi_contribution: 0.15 },
			],
		},
		threshold_simulator: {
			total_known_fraud_count: 25,
			total_known_fraud_amount: 10000,
			baseline_fp_count: 15,
			default_review_cost: 5,
			default_false_decline_cost_ratio: 0.15,
			curve,
			recommendations: {
				hybrid: {
					max_net_savings: { tau_review: 0.45, tau_reject: 0.8, caught_fraud_count: 18, caught_fraud_amount: 7500, vdr: 0.75, precision: 0.7, review_queue_count: 12, reject_count: 8, hard_false_decline_count: 1, hard_false_decline_amount: 100, soft_review_fp_count: 2, net_savings: 7425 },
					capacity_top_k: { tau_review: 0.6, tau_reject: 0.85, caught_fraud_count: 14, caught_fraud_amount: 6200, vdr: 0.62, precision: 0.8, review_queue_count: 8, reject_count: 6, hard_false_decline_count: 0, hard_false_decline_amount: 0, soft_review_fp_count: 1, net_savings: 6160 },
					target_precision: { tau_review: 0.55, tau_reject: 0.85, caught_fraud_count: 16, caught_fraud_amount: 6800, vdr: 0.68, precision: 0.75, review_queue_count: 10, reject_count: 6, hard_false_decline_count: 1, hard_false_decline_amount: 100, soft_review_fp_count: 1, net_savings: 6735 },
				},
				model_only: {
					max_net_savings: { tau_review: 0.5, tau_reject: 0.85, caught_fraud_count: 16, caught_fraud_amount: 6500, vdr: 0.65, precision: 0.72, review_queue_count: 10, reject_count: 6, hard_false_decline_count: 1, hard_false_decline_amount: 80, soft_review_fp_count: 2, net_savings: 6438 },
					capacity_top_k: { tau_review: 0.65, tau_reject: 0.9, caught_fraud_count: 12, caught_fraud_amount: 5400, vdr: 0.54, precision: 0.82, review_queue_count: 6, reject_count: 5, hard_false_decline_count: 0, hard_false_decline_amount: 0, soft_review_fp_count: 1, net_savings: 5370 },
					target_precision: { tau_review: 0.6, tau_reject: 0.9, caught_fraud_count: 14, caught_fraud_amount: 5900, vdr: 0.59, precision: 0.78, review_queue_count: 8, reject_count: 5, hard_false_decline_count: 1, hard_false_decline_amount: 80, soft_review_fp_count: 1, net_savings: 5848 },
				},
			},
		},
		model_comparison: [
			{
				model_version_id: 'mv-1',
				model_name: 'FraudNet GBDT',
				semver: 'v1.2.0',
				display_label: 'FraudNet GBDT v1.2.0',
				tx_count: 100,
				flagged_count: 35,
				verified_tp: 20,
				verified_fp: 15,
				verified_fn: 5,
				verified_precision: 0.5714,
				vdr: 0.8,
				brier_score: 0.042,
				ks_statistic: 0.68,
			},
		],
		label_source: 'VERIFIED_WITH_DATASET_FALLBACK',
		ground_truth_coverage: 'FULL',
	};
}

function makePatternsPayload(): TypologiesPatternsData {
	return {
		typology_breakdown: [
			{ code: 'ACCOUNT_TAKEOVER', label: 'Account Takeover (ATO)', case_count: 5, total_amount: 3500, pct: 1.0 },
		],
		fp_reason_breakdown: [
			{ code: 'OVERLY_STRICT_RULE', label: 'Overly Strict Rule Threshold', case_count: 2, total_amount: 250, pct: 1.0 },
		],
		hourly_distribution: Array.from({ length: 24 }, (_, hour) => ({
			hour,
			label: `${String(hour).padStart(2, '0')}:00`,
			total_tx_count: hour === 2 ? 12 : 4,
			flagged_tx_count: hour === 2 ? 4 : 1,
			confirmed_fraud_count: hour === 2 ? 3 : 0,
			total_amount: 1000,
			at_risk_amount: 400,
			confirmed_fraud_rate: hour === 2 ? 0.25 : 0,
			flagged_rate: hour === 2 ? 0.3333 : 0.25,
			fraud_rate: hour === 2 ? 0.25 : 0,
			is_peak_risk: hour === 2,
		})),
		amount_brackets: [
			{
				bracket_id: 'HIGH_VALUE',
				label: 'High-Value (> $2,000)',
				total_count: 10,
				flagged_count: 8,
				confirmed_fraud_count: 7,
				false_positive_count: 1,
				total_amount: 25000,
				amount_at_risk: 20000,
				confirmed_fraud_amount: 18000,
				flag_rate: 0.8,
			},
		],
		segment_analytics: {
			amount_brackets: {
				dimension: 'amount_brackets',
				label: 'Khoảng số tiền',
				available: true,
				items: [
					{
						segment_value: 'HIGH_VALUE',
						label: 'Giá trị cao (> $2,000)',
						total_count: 10,
						flagged_count: 8,
						confirmed_fraud_count: 7,
						false_positive_count: 1,
						missed_fraud_count: 0,
						missed_fraud_amount: 0,
						total_amount: 25000,
						amount_at_risk: 20000,
						confirmed_fraud_amount: 18000,
						prevented_fraud_amount: 18000,
						alert_rate: 0.8,
						hit_rate: 0.875,
						detection_rate: 1.0,
						lift: 3.2,
						is_small_sample: true,
					},
				],
			},
			merchant_category: {
				dimension: 'merchant_category',
				label: 'Ngành hàng (MCC)',
				available: true,
				items: [
					{
						segment_value: 'GAMBLING',
						label: 'GAMBLING',
						total_count: 12,
						flagged_count: 9,
						confirmed_fraud_count: 8,
						false_positive_count: 1,
						missed_fraud_count: 1,
						missed_fraud_amount: 400,
						total_amount: 8000,
						amount_at_risk: 6000,
						confirmed_fraud_amount: 5400,
						prevented_fraud_amount: 5000,
						alert_rate: 0.75,
						hit_rate: 0.8889,
						detection_rate: 0.8889,
						lift: 3.6,
						is_small_sample: true,
					},
				],
			},
			merchant_id: { dimension: 'merchant_id', label: 'Merchant', available: false, items: [] },
			device_id: { dimension: 'device_id', label: 'Thiết bị', available: true, items: [] },
			ip_address: { dimension: 'ip_address', label: 'Địa chỉ IP', available: false, items: [] },
			card_id: { dimension: 'card_id', label: 'Thẻ thanh toán', available: false, items: [] },
		},
		top_flagged_subjects: [
			{
				user_id: 'U-TARGET-1',
				total_tx_count: 14,
				flagged_tx_count: 5,
				confirmed_fraud_count: 4,
				false_positive_count: 1,
				amount_at_risk: 4500,
				confirmed_fraud_amount: 4000,
				max_model_score: 0.96,
				is_blacklisted: true,
			},
		],
		watchlist_summary: {
			active_blacklist_count: 2,
			removed_blacklist_count: 1,
			matched_tx_count: 17,
			matched_flagged_count: 5,
			matched_amount: 5100,
			by_entity_type: [{ entity_type: 'USER_ID', active_count: 2, removed_count: 1 }],
			recent_active_entries: [],
		},
		label_source: 'VERIFIED_WITH_DATASET_FALLBACK',
		ground_truth_coverage: 'FULL',
	};
}

function makeExecutiveReportPayload(): ExecutiveAuditReportData {
	const ov = makeOverviewPayload(false);
	const eff = makeEffectivenessPayload();
	const pat = makePatternsPayload();
	return {
		report_type: 'EXECUTIVE_AUDIT_REPORT',
		report_id: 'EXEC-AUDIT-TEST-01',
		generated_at: '2026-11-28T09:00:00Z',
		project_id: PROJECT_ID,
		project_name: 'FDS Test Project',
		prepared_by: 'analyst_lead',
		reviewer_notes: '',
		section_1_financial_kpis: ov.kpis,
		section_2_operations_funnel: {
			funnel: ov.funnel,
			queue_breakdown: ov.queue_breakdown,
			financial_trends: ov.financial_trends,
			case_sla: ov.case_sla,
		},
		section_3_policy_and_model_effectiveness: {
			attribution: eff.attribution,
			rule_leaderboard: eff.rule_leaderboard,
			model_health: eff.model_health,
			score_drift: eff.score_drift,
			lift_gain_curve: eff.lift_gain_curve,
			model_comparison: eff.model_comparison,
		},
		section_4_typologies_and_patterns: {
			typology_breakdown: pat.typology_breakdown,
			fp_reason_breakdown: pat.fp_reason_breakdown,
			peak_risk_hours: pat.hourly_distribution.filter((h) => h.is_peak_risk),
			amount_brackets: pat.amount_brackets,
			segment_analytics: pat.segment_analytics,
		},
		section_5_watchlist_and_governance: {
			top_flagged_subjects: pat.top_flagged_subjects,
			watchlist_summary: pat.watchlist_summary,
		},
	};
}

describe('InsightReportTabs', () => {
	it('test_report_tabs_render_metrics_tooltips_and_verified_only_guard', async () => {
		// 1. Tab 1: Executive Overview (FULL vs VERIFIED_ONLY null guard)
		const fullOverview = makeOverviewPayload(false);
		const ovFullRender = renderWithProviders(<ExecutiveOverviewTab data={fullOverview} isLoading={false} />);
		expect(screen.getByText(/80\.0% VDR/i)).toBeInTheDocument();
		expect(screen.getByText(/1111\.1 bps/i)).toBeInTheDocument();
		expect(screen.getByText(/20\.00%/)).toBeInTheDocument();
		expect(screen.getAllByText(/18\.0h/).length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('analyst_a')).toBeInTheDocument();

		// Tooltip button opens metric explanation
		const tooltipButtons = screen.getAllByRole('button', { name: /Giải thích chỉ số/i });
		expect(tooltipButtons.length).toBeGreaterThanOrEqual(4);
		fireEvent.click(tooltipButtons[0]);
		expect(screen.getByRole('tooltip')).toBeInTheDocument();
		ovFullRender.unmount();

		const verifiedOnlyOverview = makeOverviewPayload(true);
		const ovVerifiedRender = renderWithProviders(<ExecutiveOverviewTab data={verifiedOnlyOverview} isLoading={false} />);
		expect(screen.getByText(/Chỉ hồ sơ đã xác minh/i)).toBeInTheDocument();
		expect(screen.queryByText(/80\.0% VDR/i)).not.toBeInTheDocument();
		ovVerifiedRender.unmount();

		// 2. Tab 2: Effectiveness (Model Health, Unique Catch, Small Sample, Dual-Threshold Hybrid vs Model-only, no XGBoost)
		const effData = makeEffectivenessPayload();
		const effRender = renderWithProviders(<EffectivenessTab data={effData} isLoading={false} />);
		expect(screen.queryByText(/XGBoost/i)).not.toBeInTheDocument();
		expect(screen.getAllByText('0.680').length).toBeGreaterThanOrEqual(1);
		expect(screen.getAllByText('0.0420').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText(/Cần retrain/i)).toBeInTheDocument();
		expect(screen.getByText('R_UNIQUE_VEL')).toBeInTheDocument();
		expect(screen.getByText(/Mẫu nhỏ/i)).toBeInTheDocument();
		expect(screen.getByText('FraudNet GBDT v1.2.0')).toBeInTheDocument();

		// Parallel Hybrid and Model-only panels in Dual-Threshold Simulator
		expect(screen.getByText(/Kết hợp AI \+ Luật \(Hybrid\)/i)).toBeInTheDocument();
		expect(screen.getByText(/Chỉ AI \(Model-only\)/i)).toBeInTheDocument();

		// Toggle Calibration to Equal-Count
		fireEvent.click(screen.getByRole('button', { name: /Phân vị đều/i }));
		expect(screen.getByRole('button', { name: /Phân vị đều/i })).toHaveAttribute('aria-pressed', 'true');
		effRender.unmount();

		// 3. Tab 3: Typologies & Patterns (Segment switch, true user total_tx_count, Watchlist impact)
		const patData = makePatternsPayload();
		const patRender = renderWithProviders(<TypologiesPatternsTab data={patData} isLoading={false} />);
		expect(screen.getByText('U-TARGET-1')).toBeInTheDocument();
		expect(screen.getByText('14 GD')).toBeInTheDocument();
		expect(screen.getByText('17 GD')).toBeInTheDocument();
		expect(screen.getByText('$5,100.00')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Ngành hàng \(MCC\)/i }));
		expect(screen.getByText('GAMBLING')).toBeInTheDocument();
		expect(screen.getByText(/3\.6×/)).toBeInTheDocument();
		patRender.unmount();

		// 4. Tab 4: Compliance Report Center (MSW loaded state + no XGBoost)
		server.use(
			http.get(`${API}/v1/cases`, () =>
				HttpResponse.json({
					success: true,
					data: { items: [], total: 0, page: 1, page_size: 100 },
				})
			),
			http.get(`${API}/v1/reports/executive-summary`, () =>
				HttpResponse.json({
					success: true,
					data: makeExecutiveReportPayload(),
				})
			)
		);
		const compRender = renderWithProviders(<ComplianceReportCenterTab projectId={PROJECT_ID} scope={{}} />);
		await waitFor(() => expect(screen.getByText(/EXEC-AUDIT-TEST-01/)).toBeInTheDocument());
		expect(screen.queryByText(/XGBoost/i)).not.toBeInTheDocument();
		expect(screen.getAllByText(/80\.0%/).length).toBeGreaterThanOrEqual(1);
		compRender.unmount();
	});

	it('renders error alert when executive summary API fails', async () => {
		server.use(
			http.get(`${API}/v1/cases`, () =>
				HttpResponse.json({
					success: true,
					data: { items: [], total: 0, page: 1, page_size: 100 },
				})
			),
			http.get(`${API}/v1/reports/executive-summary`, () =>
				HttpResponse.json({ success: false, error: 'Lỗi tải báo cáo kiểm toán' }, { status: 500 })
			)
		);
		renderWithProviders(<ComplianceReportCenterTab projectId={PROJECT_ID} scope={{}} />);
		await waitFor(() =>
			expect(screen.getByText(/Không thể tải báo cáo kiểm toán điều hành/i)).toBeInTheDocument()
		);
	});
});
