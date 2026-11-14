import type { ReactNode } from 'react';
import {
	AlertTriangle,
	CheckCircle2,
	ClipboardCheck,
	Clock,
	ShieldAlert,
	ShieldCheck,
} from 'lucide-react';
import type { CaseStatus, EntityType } from '../../../types/investigation';

export const INPUT_CLASS =
	'w-full min-w-0 rounded-lg border border-dark-700 bg-dark-950 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition-colors';

export const BUTTON_SECONDARY_CLASS =
	'inline-flex min-h-8 items-center justify-center gap-1.5 rounded-lg border border-dark-700 bg-dark-850 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-dark-800 hover:text-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer';

export const BUTTON_PRIMARY_CLASS =
	'inline-flex min-h-8 items-center justify-center gap-1.5 rounded-lg border border-brand-500/40 bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer';

export const BUTTON_DANGER_CLASS =
	'inline-flex min-h-8 items-center justify-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-600/90 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer';

export const CASE_STATUSES: CaseStatus[] = [
	'OPEN',
	'IN_PROGRESS',
	'PENDING_CUSTOMER',
	'RESOLVED_FRAUD',
	'RESOLVED_LEGITIMATE',
];

export const ENTITY_TYPES: EntityType[] = [
	'USER_ID',
	'CARD_ID',
	'DEVICE_ID',
	'IP_ADDRESS',
	'MERCHANT_ID',
];

export const FRAUD_REASONS = [
	'CARD_TESTING',
	'VELOCITY_ATTACK',
	'ACCOUNT_TAKEOVER',
	'DEVICE_SHARING_RING',
	'COLLUSIVE_MERCHANT',
	'OTHER_FRAUD',
];

export const LEGITIMATE_REASONS = [
	'LEGITIMATE_UNUSUAL_SPENDING',
	'CUSTOMER_CONFIRMED',
	'OVERLY_STRICT_RULE',
	'MODEL_FALSE_ALARM',
	'OTHER_LEGITIMATE',
];

export function formatNumber(value: number | null | undefined, digits = 2): string {
	if (value == null || Number.isNaN(value)) {
		return '--';
	}
	return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function formatCurrencyAmount(value: number | null | undefined): string {
	if (value == null || Number.isNaN(value)) {
		return '--';
	}
	return value.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
}

export function formatPercent(value: number | null | undefined): string {
	if (value == null || Number.isNaN(value)) {
		return '--';
	}
	return `${(value * 100).toFixed(1)}%`;
}

export function formatLabel(value: string): string {
	return value.replaceAll('_', ' ');
}

export function formatDateTime(value: string | null | undefined): string {
	if (!value) {
		return '--';
	}
	return new Date(value).toLocaleString();
}

export function FormField({
	name,
	hint,
	children,
}: {
	name: string;
	hint?: string;
	children: ReactNode;
}) {
	return (
		<label className="flex min-w-0 flex-col gap-1.5 text-xs font-medium text-slate-300">
			<span className="flex items-center justify-between gap-2">
				<span>{name}</span>
				{hint && <span className="text-[11px] font-normal text-slate-400">{hint}</span>}
			</span>
			{children}
		</label>
	);
}

export function StatusBadge({ value }: { value: string }) {
	const isDanger = ['CRITICAL', 'HIGH', 'REJECT', 'BLOCKED', 'RESOLVED_FRAUD'].includes(value);
	const isSuccess = ['RESOLVED_LEGITIMATE', 'ALLOW', 'ACTIVE'].includes(value);
	const isMuted = ['LOW', 'REMOVED'].includes(value);

	const styleClass = isDanger
		? 'bg-rose-500/12 text-rose-300 border-rose-500/30'
		: isSuccess
			? 'bg-emerald-500/12 text-emerald-300 border-emerald-500/30'
			: isMuted
				? 'bg-dark-800 text-slate-300 border-dark-700'
				: 'bg-amber-500/12 text-amber-300 border-amber-500/30';

	const Icon = isDanger
		? ShieldAlert
		: isSuccess
			? CheckCircle2
			: value === 'PENDING_CUSTOMER'
				? Clock
				: value === 'LOW'
					? ShieldCheck
					: ClipboardCheck;

	return (
		<span
			className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-mono font-medium uppercase tracking-wide ${styleClass}`}
		>
			<Icon size={12} aria-hidden="true" className="shrink-0" />
			<span>{formatLabel(value)}</span>
		</span>
	);
}

export function ScoreBar({
	score,
	max = 1,
	showPercent = true,
}: {
	score: number | null | undefined;
	max?: number;
	showPercent?: boolean;
}) {
	if (score == null || Number.isNaN(score)) {
		return <span className="font-mono text-xs text-slate-400">Không có</span>;
	}
	const ratio = Math.max(0, Math.min(1, score / max));
	const percentValue = Math.round(ratio * 100);
	const barColor =
		ratio >= 0.75
			? 'bg-rose-500'
			: ratio >= 0.5
				? 'bg-amber-500'
				: 'bg-emerald-500';

	return (
		<div className="flex min-w-[96px] flex-col gap-1">
			<div className="flex items-center justify-between gap-2 font-mono text-xs tabular-nums text-slate-200">
				<span>{showPercent ? formatPercent(score) : formatNumber(score, 1)}</span>
			</div>
			<div
				className="h-1.5 w-full overflow-hidden rounded-full bg-dark-800"
				role="progressbar"
				aria-valuenow={percentValue}
				aria-valuemin={0}
				aria-valuemax={100}
			>
				<div
					className={`h-full rounded-full ${barColor}`}
					style={{ width: `${percentValue}%` }}
				/>
			</div>
		</div>
	);
}

export function ErrorNotice({ error }: { error: Error | null | undefined }) {
	if (!error) {
		return null;
	}
	return (
		<div
			role="alert"
			className="flex items-start gap-2.5 rounded-xl border border-rose-500/40 bg-rose-950/30 p-3.5 text-xs text-rose-200"
		>
			<AlertTriangle size={16} className="mt-0.5 shrink-0 text-rose-400" />
			<span className="break-words">{error.message}</span>
		</div>
	);
}

export function SectionCard({
	title,
	subtitle,
	badge,
	actions,
	children,
}: {
	title: string;
	subtitle?: string;
	badge?: ReactNode;
	actions?: ReactNode;
	children: ReactNode;
}) {
	return (
		<section className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-dark-700/80 bg-dark-900 shadow-sm">
			<div className="flex flex-wrap items-center justify-between gap-2 border-b border-dark-700/80 bg-dark-850/50 px-4 py-3">
				<div className="min-w-0">
					<div className="flex flex-wrap items-center gap-2">
						<h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
							{title}
						</h2>
						{badge}
					</div>
					{subtitle && <p className="mt-0.5 text-[11px] text-slate-400">{subtitle}</p>}
				</div>
				{actions && <div className="flex items-center gap-2">{actions}</div>}
			</div>
			<div className="min-w-0 space-y-3 p-4">{children}</div>
		</section>
	);
}

