import React, { useEffect, useId, useRef, useState } from 'react';
import {
	AlertTriangle,
	Check,
	Code2,
	Copy,
	Eye,
	Maximize2,
	Minus,
	Plus,
	X,
} from 'lucide-react';

interface MermaidDiagramProps {
	code: string;
	isLight?: boolean;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({
	code,
	isLight = false,
}) => {
	const rawId = useId();
	const baseId = `mermaid-${rawId.replace(/[^a-zA-Z0-9_-]/g, '')}`;
	const renderSeqRef = useRef(0);
	const openButtonRef = useRef<HTMLButtonElement>(null);
	const closeButtonRef = useRef<HTMLButtonElement>(null);
	const dialogRef = useRef<HTMLDivElement>(null);

	const [svg, setSvg] = useState<string>('');
	const [renderError, setRenderError] = useState<string | null>(null);
	const [showSource, setShowSource] = useState(false);
	const [copied, setCopied] = useState(false);
	const [isFullscreen, setIsFullscreen] = useState(false);
	const [zoom, setZoom] = useState(100);

	const trimmedCode = code.trim();
	const effectiveError = !trimmedCode
		? 'Sơ đồ Mermaid trống.'
		: renderError;

	useEffect(() => {
		if (!trimmedCode) {
			return;
		}
		let cancelled = false;

		const renderDiagram = async () => {
			try {
				const mermaidMod = await import('mermaid');
				const mermaid = mermaidMod.default;
				mermaid.initialize({
					startOnLoad: false,
					securityLevel: 'strict',
					theme: isLight ? 'default' : 'dark',
				});
				renderSeqRef.current += 1;
				const renderId = `${baseId}-${renderSeqRef.current}`;
				const result = await mermaid.render(renderId, trimmedCode);
				if (!cancelled) {
					setSvg(result.svg);
					setRenderError(null);
				}
			} catch (err) {
				if (!cancelled) {
					setSvg('');
					setRenderError(
						err instanceof Error ? err.message : String(err)
					);
				}
			}
		};

		void renderDiagram();

		return () => {
			cancelled = true;
		};
	}, [trimmedCode, isLight, baseId]);

	useEffect(() => {
		if (!isFullscreen) {
			return;
		}
		const openButton = openButtonRef.current;
		closeButtonRef.current?.focus();
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				setIsFullscreen(false);
			} else if (e.key === 'Tab') {
				const elements = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), [tabindex="0"]');
				if (!elements?.length) return;
				const first = elements[0];
				const last = elements[elements.length - 1];
				if (e.shiftKey && document.activeElement === first) {
					e.preventDefault();
					last.focus();
				} else if (!e.shiftKey && document.activeElement === last) {
					e.preventDefault();
					first.focus();
				}
			}
		};
		window.addEventListener('keydown', handleKeyDown);
		return () => {
			window.removeEventListener('keydown', handleKeyDown);
			openButton?.focus();
		};
	}, [isFullscreen]);

	const handleCopy = async () => {
		try {
			if (navigator.clipboard?.writeText) {
				await navigator.clipboard.writeText(code);
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1800);
			}
		} catch {
			// Ignore clipboard permission errors in restricted contexts
		}
	};

	const btnClass = `inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-mono transition ${
		isLight
			? 'bg-white hover:bg-zinc-100 border-zinc-200 text-zinc-700'
			: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-700/80 text-zinc-300'
	}`;

	return (
		<>
			<div
				className={`my-4 rounded-xl border overflow-hidden ${
					isLight
						? 'bg-zinc-50 border-zinc-200'
						: 'bg-zinc-950 border-zinc-800'
				}`}
			>
				{/* Toolbar */}
				<div
					className={`px-4 py-2 border-b flex flex-wrap items-center justify-between gap-2 ${
						isLight
							? 'bg-zinc-100/90 border-zinc-200 text-zinc-600'
							: 'bg-zinc-900 border-zinc-800 text-zinc-400'
					}`}
				>
					<span className="text-[11px] font-mono uppercase font-semibold tracking-wide">
						MERMAID
					</span>

					<div className="flex items-center gap-1.5">
						{!effectiveError && (
							<button
								type="button"
								onClick={() => setShowSource((prev) => !prev)}
								className={btnClass}
							>
								{showSource ? (
									<>
										<Eye className="w-3 h-3" />
										<span>Xem sơ đồ</span>
									</>
								) : (
									<>
										<Code2 className="w-3 h-3" />
										<span>Xem mã</span>
									</>
								)}
							</button>
						)}

						<button
							type="button"
							onClick={() => void handleCopy()}
							className={btnClass}
						>
							{copied ? (
								<>
									<Check className="w-3 h-3 text-emerald-500" />
									<span>Đã copy</span>
								</>
							) : (
								<>
									<Copy className="w-3 h-3" />
									<span>Copy</span>
								</>
							)}
						</button>

						{!effectiveError && svg && (
							<button
								type="button"
								ref={openButtonRef}
								onClick={() => setIsFullscreen(true)}
								className={btnClass}
							>
								<Maximize2 className="w-3 h-3" />
								<span>Phóng to</span>
							</button>
						)}
					</div>
				</div>

				{/* Error fallback */}
				{effectiveError && (
					<div className="p-4 space-y-3">
						<div className="flex items-start gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400">
							<AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
							<div>
								<div className="font-semibold">
									Lỗi cú pháp Mermaid: {effectiveError}
								</div>
							</div>
						</div>
						<pre
							className={`p-3 rounded-lg border text-xs font-mono overflow-x-auto leading-6 ${
								isLight
									? 'bg-white border-zinc-200 text-zinc-800'
									: 'bg-zinc-900 border-zinc-800 text-zinc-200'
							}`}
						>
							{code}
						</pre>
					</div>
				)}

				{/* Raw code view */}
				{!effectiveError && showSource && (
					<pre
						className={`p-4 text-xs font-mono overflow-x-auto leading-6 ${
							isLight ? 'text-zinc-800' : 'text-zinc-200'
						}`}
					>
						{code}
					</pre>
				)}

				{/* Rendered SVG */}
				{!effectiveError && !showSource && (
					<div
						className={`p-4 overflow-x-auto flex justify-center [&_svg]:max-w-full [&_svg]:h-auto ${
							isLight ? 'bg-white' : 'bg-[#0b0b0e]'
						}`}
					>
						{svg ? (
							<div
								className="w-full flex justify-center"
								dangerouslySetInnerHTML={{ __html: svg }}
							/>
						) : (
							<span className="text-xs font-mono text-zinc-500 py-4">
								Đang render sơ đồ Mermaid...
							</span>
						)}
					</div>
				)}
			</div>

			{/* Fullscreen modal */}
			{isFullscreen && svg && (
				<div
					ref={dialogRef}
					role="dialog"
					aria-modal="true"
					aria-label="Xem sơ đồ Mermaid toàn màn hình"
					onClick={() => setIsFullscreen(false)}
					className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-6"
				>
					<div
						onClick={(e) => e.stopPropagation()}
						className={`w-full max-w-6xl max-h-[90vh] rounded-2xl border flex flex-col overflow-hidden shadow-2xl ${
							isLight
								? 'bg-white border-zinc-200'
								: 'bg-[#0f0f13] border-zinc-800'
						}`}
					>
						<div
							className={`px-5 py-3 border-b flex items-center justify-between ${
								isLight
									? 'bg-zinc-50 border-zinc-200 text-zinc-700'
									: 'bg-zinc-900 border-zinc-800 text-zinc-200'
							}`}
						>
							<span className="text-xs font-mono font-semibold uppercase">
								Sơ đồ Mermaid (Toàn màn hình)
							</span>
							<div className="flex items-center gap-2">
								<button type="button" className={btnClass} aria-label="Giảm mức thu phóng" disabled={zoom <= 50} onClick={() => setZoom((value) => Math.max(50, value - 25))}><Minus className="w-3 h-3" aria-hidden="true" /></button>
								<button type="button" className={btnClass} aria-label="Đặt lại mức thu phóng" onClick={() => setZoom(100)}>{zoom}%</button>
								<button type="button" className={btnClass} aria-label="Tăng mức thu phóng" disabled={zoom >= 300} onClick={() => setZoom((value) => Math.min(300, value + 25))}><Plus className="w-3 h-3" aria-hidden="true" /></button>
								<button
									type="button"
									ref={closeButtonRef}
									onClick={() => setIsFullscreen(false)}
									aria-label="Đóng"
									className={`p-1.5 rounded-lg border transition ${
										isLight
											? 'bg-white hover:bg-zinc-100 border-zinc-200 text-zinc-700'
											: 'bg-zinc-800 hover:bg-zinc-700 border-zinc-700 text-zinc-200'
									}`}
								>
									<X className="w-4 h-4" />
								</button>
							</div>
						</div>
						<div
							role="region"
							aria-label="Cuộn sơ đồ"
							tabIndex={0}
							className={`flex-1 overflow-auto p-6 ${
								isLight ? 'bg-white' : 'bg-[#0b0b0e]'
							}`}
						>
							<div
								role="img"
								aria-label="Vùng sơ đồ"
								style={{ width: `${zoom}%` }}
								className="mx-auto [&_svg]:w-full [&_svg]:!max-w-none [&_svg]:h-auto"
								dangerouslySetInnerHTML={{ __html: svg }}
							/>
						</div>
					</div>
				</div>
			)}
		</>
	);
};
