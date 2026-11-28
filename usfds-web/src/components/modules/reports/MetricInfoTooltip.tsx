import React, { useState } from 'react';
import { Info } from 'lucide-react';

interface MetricInfoTooltipProps {
	title: string;
	formula: string;
	meaning: string;
	benchmark?: string;
}

export const MetricInfoTooltip: React.FC<MetricInfoTooltipProps> = ({
	title,
	formula,
	meaning,
	benchmark,
}) => {
	const [open, setOpen] = useState(false);

	return (
		<span className="relative inline-flex items-center">
			<button
				type="button"
				aria-label={`Giải thích chỉ số ${title}`}
				aria-expanded={open}
				onClick={() => setOpen((prev) => !prev)}
				onBlur={() => setOpen(false)}
				className="p-0.5 rounded-full text-slate-400 hover:text-brand-300 focus:outline-none focus:ring-1 focus:ring-brand-500 cursor-pointer transition-colors"
			>
				<Info size={13} aria-hidden="true" />
			</button>
			{open && (
				<div
					role="tooltip"
					className="absolute left-0 top-full mt-1.5 z-40 w-72 rounded-lg border border-dark-700 bg-dark-950 p-3 text-left shadow-xl"
				>
					<div className="text-xs font-semibold text-slate-100">{title}</div>
					<div className="mt-1 rounded bg-dark-900 px-2 py-1 font-mono text-[11px] text-cyan-300 border border-dark-800">
						{formula}
					</div>
					<p className="mt-1.5 text-[11px] leading-relaxed text-slate-300">{meaning}</p>
					{benchmark && (
						<div className="mt-1.5 text-[11px] font-mono text-emerald-300">
							Ngưỡng tham khảo: {benchmark}
						</div>
					)}
				</div>
			)}
		</span>
	);
};
