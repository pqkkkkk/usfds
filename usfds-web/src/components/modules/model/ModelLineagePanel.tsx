import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ExternalLink, GitBranch, Loader2, RefreshCw } from 'lucide-react';
import { useModelLineage } from '@/hooks/useModelLineage';
import { computeCanvasLayout } from '@/utils/lineageLayout';
import { LineageCanvasView } from '../LineageCanvasView';
import type { ModelLineageNode } from '@/types/model';
import type { LineageRawNode } from '@/types/navigation';

interface ModelLineagePanelProps {
	versionId?: string;
	runId?: string;
	compact?: boolean;
}

export const ModelLineagePanel = ({
	versionId,
	runId,
	compact = false,
}: ModelLineagePanelProps) => {
	const navigate = useNavigate();
	const { lineage, isLoading, errorMessage, refetch } = useModelLineage({
		versionId,
		runId,
	});

	const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

	useEffect(() => {
		if (!lineage || lineage.nodes.length === 0) return;
		const preferredId =
			lineage.root_version_id ||
			lineage.root_run_id ||
			lineage.nodes[lineage.nodes.length - 1].id;
		setSelectedNodeId(preferredId);
	}, [lineage]);

	const layout = useMemo(() => {
		if (!lineage || lineage.nodes.length === 0) {
			return { canvasNodes: [], canvasEdges: [], width: 700, height: 320 };
		}
		const rawNodes: LineageRawNode[] = lineage.nodes.map((n) => ({
			id: n.id,
			stage: n.stage,
			created_at: n.created_at,
			parent_id: n.parent_id,
			label: n.node_type === 'DATASET_ARTIFACT' ? `${n.id.slice(0, 14)}...` : n.label,
		}));
		return computeCanvasLayout(rawNodes, lineage.edges);
	}, [lineage]);

	const selectedNode: ModelLineageNode | null = useMemo(() => {
		if (!lineage || lineage.nodes.length === 0) return null;
		return (
			lineage.nodes.find((n) => n.id === selectedNodeId) ||
			lineage.nodes[lineage.nodes.length - 1]
		);
	}, [lineage, selectedNodeId]);

	if (isLoading) {
		return (
			<div className="bg-dark-900 border border-dark-800 rounded-xl p-8 flex items-center justify-center gap-2 text-xs text-slate-400">
				<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
				<span>Đang tải sơ đồ phả hệ dữ liệu...</span>
			</div>
		);
	}

	if (errorMessage) {
		return (
			<div className="bg-dark-900 border border-rose-500/30 rounded-xl p-6 flex items-center justify-between gap-4 text-xs text-rose-300">
				<div className="flex items-center gap-2">
					<AlertCircle className="w-4 h-4 shrink-0" />
					<span>Không thể tải phả hệ: {errorMessage}</span>
				</div>
				<button
					type="button"
					onClick={() => void refetch()}
					className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-200 inline-flex items-center gap-1.5"
				>
					<RefreshCw className="w-3.5 h-3.5" />
					<span>Thử lại</span>
				</button>
			</div>
		);
	}

	if (!lineage || lineage.nodes.length === 0) {
		return (
			<div className="bg-dark-900 border border-dark-800 rounded-xl p-6 text-xs text-slate-400 text-center">
				Chưa có thông tin phả hệ dữ liệu cho phiên bản này.
			</div>
		);
	}

	const meta = selectedNode?.metadata || {};

	return (
		<div className="bg-dark-900 border border-dark-800 rounded-xl overflow-hidden">
			<div className="px-5 py-3 border-b border-dark-800 flex items-center justify-between">
				<div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
					<GitBranch className="w-4 h-4 text-brand-400" />
					<span>Phả hệ dữ liệu &amp; mô hình (Read-only)</span>
				</div>
				<span className="text-[11px] font-mono text-slate-400">
					{lineage.nodes.length} nodes · {lineage.edges.length} edges
				</span>
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-3">
				<div
					className={`lg:col-span-2 border-b lg:border-b-0 lg:border-r border-dark-800 overflow-auto ${
						compact ? 'max-h-[360px]' : 'max-h-[460px]'
					}`}
				>
					<LineageCanvasView
						canvasNodes={layout.canvasNodes}
						canvasEdges={layout.canvasEdges}
						selectedNodeId={selectedNode?.id ?? null}
						onSelectNode={(node) => setSelectedNodeId(node.id)}
						width={layout.width}
						height={Math.min(layout.height, compact ? 320 : 420)}
					/>
				</div>

				<div
					data-testid="lineage-node-inspector"
					className="p-4 space-y-3 bg-dark-950/60 text-xs"
				>
					<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
						Chi tiết Node
					</div>
					{selectedNode && (
						<div className="space-y-2">
							<div className="flex justify-between gap-2">
								<span className="text-slate-400">Giai đoạn:</span>
								<span className="font-mono font-bold text-slate-100">
									{selectedNode.stage}
								</span>
							</div>
							<div className="flex justify-between gap-2">
								<span className="text-slate-400">ID:</span>
								<span className="font-mono text-slate-200 break-all text-right">
									{selectedNode.id}
								</span>
							</div>
							<div className="flex justify-between gap-2">
								<span className="text-slate-400">Thời gian:</span>
								<span className="font-mono text-slate-300">
									{new Date(selectedNode.created_at).toLocaleString('vi-VN')}
								</span>
							</div>

							{meta.row_count !== undefined && meta.row_count !== null && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">Số dòng:</span>
									<span className="font-mono text-slate-200">
										{Number(meta.row_count).toLocaleString('vi-VN')}
									</span>
								</div>
							)}
							{meta.column_count !== undefined && meta.column_count !== null && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">Số cột:</span>
									<span className="font-mono text-slate-200">
										{String(meta.column_count)}
									</span>
								</div>
							)}
							{typeof meta.status === 'string' && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">Trạng thái:</span>
									<span className="font-mono text-emerald-300">
										{meta.status}
									</span>
								</div>
							)}
							{typeof meta.semver === 'string' && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">Phiên bản:</span>
									<span className="font-mono text-cyan-300">v{meta.semver}</span>
								</div>
							)}
							{typeof meta.framework === 'string' && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">Framework:</span>
									<span className="font-mono text-slate-200">{meta.framework}</span>
								</div>
							)}
							{typeof meta.checksum_sha256 === 'string' && (
								<div className="flex justify-between gap-2">
									<span className="text-slate-400">SHA-256:</span>
									<span className="font-mono text-emerald-400 text-[11px]">
										{meta.checksum_sha256.slice(0, 12)}...
									</span>
								</div>
							)}

							{selectedNode.node_type === 'DATASET_ARTIFACT' &&
								selectedNode.dataset_id && (
									<div className="pt-2 border-t border-dark-800">
										<button
											type="button"
											onClick={() =>
												navigate(`/datasets/${selectedNode.dataset_id}`)
											}
											className="w-full px-3 py-1.5 rounded-lg bg-brand-500/15 hover:bg-brand-500/25 border border-brand-500/30 text-brand-300 font-medium inline-flex items-center justify-center gap-1.5 transition"
										>
											<ExternalLink className="w-3.5 h-3.5" />
											<span>Xem phả hệ Dataset</span>
										</button>
									</div>
								)}
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
