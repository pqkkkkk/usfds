import { useEffect, useRef } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { Expand, Maximize2, Minimize2, RotateCcw } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import type { EntityType, NetworkEdge, NetworkNode } from '@/types/investigation';
import { BUTTON_SECONDARY_CLASS, formatCurrencyAmount, formatNumber } from './investigationShared';

interface CytoscapeCanvasProps {
	nodes: NetworkNode[];
	edges: NetworkEdge[];
	selectedNodeIds: string[];
	focusedNodeId: string | null;
	selectedEdgeId: string | null;
	onToggleNodeSelect: (nodeId: string) => void;
	onFocusNode: (nodeId: string) => void;
	onExpandNode: (node: NetworkNode) => void;
	onSelectEdge: (edge: NetworkEdge) => void;
	compact?: boolean;
}

const ENTITY_SHAPES: Record<EntityType, string> = {
	USER_ID: 'ellipse',
	DEVICE_ID: 'round-rectangle',
	IP_ADDRESS: 'diamond',
	CARD_ID: 'tag',
	MERCHANT_ID: 'hexagon',
};

const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
	USER_ID: 'Người dùng',
	DEVICE_ID: 'Thiết bị',
	IP_ADDRESS: 'IP',
	CARD_ID: 'Thẻ',
	MERCHANT_ID: 'ĐV chấp nhận',
};

function riskColors(status: NetworkNode['risk_status'], isLight: boolean): { bg: string; border: string } {
	if (status === 'CRITICAL') {
		return { bg: '#e11d48', border: '#fda4af' };
	}
	if (status === 'WARNING') {
		return { bg: '#d97706', border: '#fcd34d' };
	}
	return isLight
		? { bg: '#334155', border: '#94a3b8' }
		: { bg: '#1e293b', border: '#64748b' };
}

export function CytoscapeCanvas({
	nodes,
	edges,
	selectedNodeIds,
	focusedNodeId,
	selectedEdgeId,
	onToggleNodeSelect,
	onFocusNode,
	onExpandNode,
	onSelectEdge,
	compact = false,
}: CytoscapeCanvasProps) {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const cyRef = useRef<Core | null>(null);
	const { isLight, chartTokens } = useTheme();

	useEffect(() => {
		const container = containerRef.current;
		if (!container || nodes.length === 0) {
			if (cyRef.current) {
				cyRef.current.destroy();
				cyRef.current = null;
			}
			return;
		}
		// Skip WebGL/Canvas mounting inside headless jsdom environments with zero layout box
		if (container.clientWidth === 0 || container.clientHeight === 0) {
			return;
		}

		const selectedSet = new Set(selectedNodeIds);
		const elements: ElementDefinition[] = [
			...nodes.map((node) => {
				const palette = riskColors(node.risk_status, isLight);
				return {
					data: {
						id: node.id,
						label: node.label,
						entityType: node.entity_type,
						shape: ENTITY_SHAPES[node.entity_type],
						bgColor: palette.bg,
						borderColor: selectedSet.has(node.id)
							? '#38bdf8'
							: node.pattern_tags.length > 0
								? '#f43f5e'
								: palette.border,
						borderWidth: selectedSet.has(node.id) || node.is_seed ? 3 : 1.5,
						size: node.is_seed ? 44 : node.pattern_tags.length > 0 ? 40 : 32,
					},
				};
			}),
			...edges.map((edge) => ({
				data: {
					id: edge.id,
					source: edge.source,
					target: edge.target,
					label: `${edge.tx_count} GD`,
					lineColor:
						edge.id === selectedEdgeId
							? '#38bdf8'
							: edge.flagged_tx_count > 0
								? '#f59e0b'
								: chartTokens.axisStroke,
					width: Math.min(6, 1.5 + Math.log2(edge.tx_count + 1)),
				},
			})),
		];

		const cy = cytoscape({
			container,
			elements,
			boxSelectionEnabled: true,
			style: [
				{
					selector: 'node',
					style: {
						label: 'data(label)',
						shape: 'data(shape)' as never,
						'background-color': 'data(bgColor)',
						'border-color': 'data(borderColor)',
						'border-width': 'data(borderWidth)',
						width: 'data(size)',
						height: 'data(size)',
						color: isLight ? '#0f172a' : '#f1f5f9',
						'font-size': '10px',
						'text-valign': 'bottom',
						'text-margin-y': 4,
					},
				},
				{
					selector: 'edge',
					style: {
						label: 'data(label)',
						width: 'data(width)',
						'line-color': 'data(lineColor)',
						'target-arrow-color': 'data(lineColor)',
						'target-arrow-shape': 'triangle',
						'curve-style': 'bezier',
						'font-size': '9px',
						color: chartTokens.axisTick,
					},
				},
			],
			layout: {
				name: 'cose',
				animate: false,
				fit: true,
				padding: 24,
			},
		});

		cy.on('tap', 'node', (evt) => {
			const id = String(evt.target.id());
			onFocusNode(id);
		});
		cy.on('dbltap', 'node', (evt) => {
			const id = String(evt.target.id());
			const found = nodes.find((n) => n.id === id);
			if (found) {
				onExpandNode(found);
			}
		});
		cy.on('tap', 'edge', (evt) => {
			const id = String(evt.target.id());
			const found = edges.find((e) => e.id === id);
			if (found) {
				onSelectEdge(found);
			}
		});
		cy.on('boxselect', 'node', () => {
			const selected = cy.$('node:selected').map((n) => String(n.id()));
			for (const id of selected) {
				onToggleNodeSelect(id);
			}
		});

		cyRef.current = cy;
		return () => {
			cy.destroy();
			cyRef.current = null;
		};
	}, [
		nodes,
		edges,
		selectedNodeIds,
		selectedEdgeId,
		isLight,
		chartTokens,
		onFocusNode,
		onExpandNode,
		onSelectEdge,
		onToggleNodeSelect,
	]);

	const handleZoom = (factor: number) => {
		const cy = cyRef.current;
		if (!cy) {
			return;
		}
		cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
	};

	const handleFit = () => {
		cyRef.current?.fit(undefined, 24);
	};

	return (
		<div className="space-y-3">
			<div className="relative overflow-hidden rounded-xl border border-dark-700/80 bg-dark-950">
				<div className="flex flex-wrap items-center justify-between gap-2 border-b border-dark-800 bg-dark-900/80 px-3 py-2 text-[11px] text-slate-300">
					<div className="flex flex-wrap items-center gap-3">
						<span className="inline-flex items-center gap-1.5">
							<span className="h-2.5 w-2.5 rounded-full bg-rose-500" aria-hidden="true" />
							<span>Nguy hiểm (Chặn / Gian lận)</span>
						</span>
						<span className="inline-flex items-center gap-1.5">
							<span className="h-2.5 w-2.5 rounded-full bg-amber-500" aria-hidden="true" />
							<span>Cảnh báo (Mở / Gắn cờ)</span>
						</span>
						<span className="inline-flex items-center gap-1.5">
							<span className="h-2.5 w-2.5 rounded-full bg-slate-500" aria-hidden="true" />
							<span>Bình thường</span>
						</span>
					</div>
					<div className="flex items-center gap-1.5">
						<button type="button" onClick={() => handleZoom(1.2)} className={BUTTON_SECONDARY_CLASS} aria-label="Phóng to đồ thị">
							<Maximize2 size={12} aria-hidden="true" />
						</button>
						<button type="button" onClick={() => handleZoom(0.8)} className={BUTTON_SECONDARY_CLASS} aria-label="Thu nhỏ đồ thị">
							<Minimize2 size={12} aria-hidden="true" />
						</button>
						<button type="button" onClick={handleFit} className={BUTTON_SECONDARY_CLASS} aria-label="Căn giữa đồ thị">
							<RotateCcw size={12} aria-hidden="true" />
						</button>
					</div>
				</div>

				<div
					ref={containerRef}
					aria-label="Khung vẽ đồ thị mạng lưới liên kết"
					className={compact ? 'h-72 w-full' : 'h-96 w-full'}
				/>
			</div>

			{/* Accessible keyboard & inspection directory synced with the Cytoscape graph */}
			<div className="grid gap-3 md:grid-cols-2">
				<div className="rounded-xl border border-dark-700/80 bg-dark-950/60 p-3">
					<p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
						Nút trên đồ thị ({nodes.length})
					</p>
					<ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1 text-xs">
						{nodes.map((node) => {
							const isSelected = selectedNodeIds.includes(node.id);
							const isFocused = focusedNodeId === node.id;
							return (
								<li
									key={node.id}
									className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 ${
										isFocused
											? 'border-brand-500/60 bg-brand-950/20'
											: 'border-dark-800 bg-dark-900/70'
									}`}
								>
									<label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
										<input
											type="checkbox"
											checked={isSelected}
											onChange={() => onToggleNodeSelect(node.id)}
											aria-label={`Chọn nút ${node.id}`}
										/>
										<button
											type="button"
											onClick={() => onFocusNode(node.id)}
											className="min-w-0 truncate text-left font-mono text-slate-100 hover:text-brand-300"
										>
											<span className="mr-1.5 rounded bg-dark-800 px-1.5 py-0.5 text-[10px] text-slate-300">
												{ENTITY_TYPE_LABELS[node.entity_type]}
											</span>
											<span>{node.label}</span>
										</button>
									</label>
									<div className="flex shrink-0 items-center gap-1.5">
										<span className="font-mono text-[10px] text-slate-400">
											{node.flagged_tx_count}/{node.tx_count}
										</span>
										<button
											type="button"
											onClick={() => onExpandNode(node)}
											aria-label={`Mở rộng ${node.id}`}
											className="inline-flex items-center gap-1 rounded border border-dark-700 bg-dark-850 px-2 py-0.5 text-[11px] text-slate-200 hover:bg-dark-800"
										>
											<Expand size={11} aria-hidden="true" />
											<span>+1 hop</span>
										</button>
									</div>
								</li>
							);
						})}
					</ul>
				</div>

				<div className="rounded-xl border border-dark-700/80 bg-dark-950/60 p-3">
					<p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
						Cạnh liên kết ({edges.length})
					</p>
					<ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1 text-xs">
						{edges.map((edge) => (
							<li key={edge.id}>
								<button
									type="button"
									onClick={() => onSelectEdge(edge)}
									aria-label={`Xem cạnh ${edge.user_id} -> ${edge.entity_value}`}
									className={`flex w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 text-left transition-colors ${
										selectedEdgeId === edge.id
											? 'border-brand-500/60 bg-brand-950/20 text-brand-200'
											: 'border-dark-800 bg-dark-900/70 text-slate-200 hover:bg-dark-800'
									}`}
								>
									<span className="truncate font-mono">
										{edge.user_id} → {edge.entity_value}
									</span>
									<span className="shrink-0 font-mono text-[11px] text-slate-400">
										{formatNumber(edge.tx_count, 0)} GD &bull; {formatCurrencyAmount(edge.total_amount)}
									</span>
								</button>
							</li>
						))}
					</ul>
				</div>
			</div>
		</div>
	);
}
