import { useCallback, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { investigationApi } from '@/api/investigationApi';
import type {
	EdgeTransaction,
	EntityType,
	NetworkEdge,
	NetworkNode,
	NetworkPattern,
} from '@/types/investigation';

export const NETWORK_GRAPH_QUERY_KEY = ['investigation', 'network'] as const;

const SECONDARY_TYPES: EntityType[] = ['DEVICE_ID', 'IP_ADDRESS', 'CARD_ID', 'MERCHANT_ID'];

export interface UseNetworkGraphOptions {
	projectId: string;
	initialSeedType?: EntityType;
	initialSeedValue?: string;
	caseId?: string | null;
}

export function useNetworkGraph({
	projectId,
	initialSeedType = 'USER_ID',
	initialSeedValue = '',
	caseId = null,
}: UseNetworkGraphOptions) {
	const queryClient = useQueryClient();

	const [seedType, setSeedType] = useState<EntityType>(initialSeedType);
	const [seedValue, setSeedValue] = useState<string>(initialSeedValue);
	const [activeSeed, setActiveSeed] = useState<{ type: EntityType; value: string } | null>(
		initialSeedValue.trim()
			? { type: initialSeedType, value: initialSeedValue.trim() }
			: null
	);
	const [hops, setHops] = useState<1 | 2>(2);
	const [days, setDays] = useState<number>(90);
	const [entityTypes, setEntityTypes] = useState<EntityType[]>(SECONDARY_TYPES);
	const [hideSuperNodes, setHideSuperNodes] = useState<boolean>(false);

	const [nodes, setNodes] = useState<NetworkNode[]>([]);
	const [edges, setEdges] = useState<NetworkEdge[]>([]);
	const [patterns, setPatterns] = useState<NetworkPattern[]>([]);
	const [notice, setNotice] = useState<string | null>(null);
	const [actionFeedback, setActionFeedback] = useState<string | null>(null);
	const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
	const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
	const [selectedEdge, setSelectedEdge] = useState<NetworkEdge | null>(null);
	const [selectedEdgeTxKeys, setSelectedEdgeTxKeys] = useState<string[]>([]);

	const hubsQuery = useQuery({
		queryKey: [...NETWORK_GRAPH_QUERY_KEY, projectId, 'hubs', days, caseId],
		queryFn: () => investigationApi.networkHubs(projectId, days, 20, caseId),
		enabled: Boolean(projectId),
	});

	const subgraphQuery = useQuery({
		queryKey: [
			...NETWORK_GRAPH_QUERY_KEY,
			projectId,
			'subgraph',
			activeSeed?.type ?? null,
			activeSeed?.value ?? null,
			hops,
			days,
			entityTypes,
			hideSuperNodes,
			caseId,
		],
		queryFn: () =>
			investigationApi.networkSubgraph(projectId, {
				seedType: activeSeed!.type,
				seedValue: activeSeed!.value,
				hops,
				days,
				entityTypes,
				hideSuperNodes,
				caseId,
			}),
		enabled: Boolean(projectId && activeSeed?.value),
	});

	useEffect(() => {
		const data = subgraphQuery.data;
		if (!data) {
			return;
		}
		setNodes(data.nodes);
		setEdges(data.edges);
		setPatterns(data.patterns);
		setNotice(data.notice ?? data.message ?? null);
		setSelectedNodeIds([]);
		setSelectedEdge(null);
		setSelectedEdgeTxKeys([]);
		setFocusedNodeId(data.nodes[0]?.id ?? null);
	}, [subgraphQuery.data]);

	const edgeTransactionsQuery = useQuery({
		queryKey: [
			...NETWORK_GRAPH_QUERY_KEY,
			projectId,
			'edge-transactions',
			selectedEdge?.user_id ?? null,
			selectedEdge?.entity_type ?? null,
			selectedEdge?.entity_value ?? null,
			days,
			caseId,
		],
		queryFn: () =>
			investigationApi.networkEdgeTransactions(projectId, {
				userId: selectedEdge!.user_id,
				entityType: selectedEdge!.entity_type,
				entityValue: selectedEdge!.entity_value,
				days,
				limit: 100,
				caseId,
			}),
		enabled: Boolean(projectId && selectedEdge),
	});

	const expandMutation = useMutation({
		mutationFn: (node: { entity_type: EntityType; entity_value: string }) =>
			investigationApi.networkExpand({
				project_id: projectId,
				entity_type: node.entity_type,
				entity_value: node.entity_value,
				existing_node_ids: nodes.map((n) => n.id),
				days,
				entity_types: entityTypes,
				hide_super_nodes: hideSuperNodes,
				case_id: caseId,
			}),
		onSuccess: (data) => {
			if (data.added_nodes.length > 0) {
				setNodes((prev) => {
					const existing = new Set(prev.map((n) => n.id));
					return [...prev, ...data.added_nodes.filter((n) => !existing.has(n.id))];
				});
			}
			if (data.added_edges.length > 0) {
				setEdges((prev) => {
					const existing = new Set(prev.map((e) => e.id));
					return [...prev, ...data.added_edges.filter((e) => !existing.has(e.id))];
				});
			}
			if (data.patterns.length > 0) {
				setPatterns((prev) => {
					const map = new Map(prev.map((p) => [`${p.pattern_type}:${p.node_id}`, p]));
					for (const p of data.patterns) {
						map.set(`${p.pattern_type}:${p.node_id}`, p);
					}
					return Array.from(map.values());
				});
			}
			setNotice(data.notice ?? data.message ?? null);
		},
	});

	const bulkBlacklistMutation = useMutation({
		mutationFn: ({
			entities,
			reason,
		}: {
			entities: { entity_type: EntityType; entity_value: string }[];
			reason: string;
		}) => investigationApi.bulkBlacklist(projectId, entities, reason, caseId),
		onSuccess: async (res) => {
			setActionFeedback(
				`Đã chặn ${res.added_count} thực thể (bỏ qua ${res.skipped_count} thực thể đã có trong danh sách chặn).`
			);
			await queryClient.invalidateQueries({ queryKey: ['investigation', projectId] });
			await queryClient.invalidateQueries({ queryKey: NETWORK_GRAPH_QUERY_KEY });
		},
	});

	const bulkCaseIntakeMutation = useMutation({
		mutationFn: ({
			items,
			analystNotes,
		}: {
			items: { detection_job_id: string; event_id: string }[];
			analystNotes?: string;
		}) => investigationApi.bulkCaseIntake(projectId, items, analystNotes),
		onSuccess: async (res) => {
			setActionFeedback(
				`Đã tạo ${res.accepted_count} hồ sơ điều tra mới (bỏ qua ${res.skipped_event_ids.length} giao dịch đã có hồ sơ).`
			);
			setSelectedEdgeTxKeys([]);
			await queryClient.invalidateQueries({ queryKey: ['investigation', projectId] });
			await queryClient.invalidateQueries({ queryKey: NETWORK_GRAPH_QUERY_KEY });
		},
	});

	const searchSeed = useCallback(
		(nextType?: EntityType, nextValue?: string) => {
			const finalType = nextType ?? seedType;
			const finalValue = (nextValue ?? seedValue).trim();
			if (!finalValue) {
				return;
			}
			setSeedType(finalType);
			setSeedValue(finalValue);
			setActionFeedback(null);
			setActiveSeed({ type: finalType, value: finalValue });
		},
		[seedType, seedValue]
	);

	const toggleEntityType = useCallback((etype: EntityType) => {
		setEntityTypes((prev) => {
			if (prev.includes(etype)) {
				return prev.length > 1 ? prev.filter((item) => item !== etype) : prev;
			}
			return [...prev, etype];
		});
	}, []);

	const toggleNodeSelection = useCallback((nodeId: string) => {
		setSelectedNodeIds((prev) =>
			prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId]
		);
	}, []);

	const toggleEdgeTransaction = useCallback((tx: EdgeTransaction) => {
		if (!tx.job_id || tx.case_id || !tx.is_flagged) {
			return;
		}
		const key = `${tx.job_id}::${tx.event_id}`;
		setSelectedEdgeTxKeys((prev) =>
			prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
		);
	}, []);

	const selectEdge = useCallback((edge: NetworkEdge | null) => {
		setSelectedEdge(edge);
		setSelectedEdgeTxKeys([]);
	}, []);

	return {
		seedType,
		setSeedType,
		seedValue,
		setSeedValue,
		activeSeed,
		searchSeed,
		hops,
		setHops,
		days,
		setDays,
		entityTypes,
		toggleEntityType,
		hideSuperNodes,
		setHideSuperNodes,
		hubsQuery,
		subgraphQuery,
		edgeTransactionsQuery,
		nodes,
		edges,
		patterns,
		notice,
		actionFeedback,
		selectedNodeIds,
		setSelectedNodeIds,
		toggleNodeSelection,
		focusedNodeId,
		setFocusedNodeId,
		selectedEdge,
		selectEdge,
		selectedEdgeTxKeys,
		toggleEdgeTransaction,
		expandNode: expandMutation.mutate,
		isExpanding: expandMutation.isPending,
		expandError: expandMutation.error,
		bulkBlacklist: bulkBlacklistMutation.mutateAsync,
		isBulkBlacklisting: bulkBlacklistMutation.isPending,
		bulkBlacklistError: bulkBlacklistMutation.error,
		bulkCaseIntake: bulkCaseIntakeMutation.mutateAsync,
		isBulkIntaking: bulkCaseIntakeMutation.isPending,
		bulkCaseIntakeError: bulkCaseIntakeMutation.error,
	};
}
