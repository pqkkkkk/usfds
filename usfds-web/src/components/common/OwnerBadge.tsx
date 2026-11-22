import React from 'react';
import { User as UserIcon, Cpu } from 'lucide-react';
import type { ResourceOwner } from '@/types';

interface OwnerBadgeProps {
	owner?: ResourceOwner | null;
	userId?: string | null;
	className?: string;
}

export const OwnerBadge: React.FC<OwnerBadgeProps> = ({
	owner,
	userId,
	className = '',
}) => {
	const resolvedUserId = owner?.user_id ?? userId ?? null;
	if (!resolvedUserId && !owner) {
		return (
			<span
				className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-dark-800 border border-dark-700 text-slate-300 ${className}`}
				title="Tài nguyên tích hợp sẵn của hệ thống"
			>
				<Cpu className="w-3 h-3 text-brand-400" />
				<span>Hệ thống</span>
			</span>
		);
	}

	const primaryLabel = owner?.full_name?.trim() || owner?.username || `${resolvedUserId?.slice(0, 8)}…`;
	const tooltipParts = [
		owner?.full_name ? `Họ tên: ${owner.full_name}` : null,
		owner?.username ? `Username: @${owner.username}` : null,
		resolvedUserId ? `ID: ${resolvedUserId}` : null,
	].filter(Boolean);

	return (
		<span
			className={`inline-flex items-center gap-1.5 text-xs text-slate-200 ${className}`}
			title={tooltipParts.join(' • ')}
		>
			<UserIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
			<span className="truncate max-w-[160px]">{primaryLabel}</span>
		</span>
	);
};
