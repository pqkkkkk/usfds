import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { docsDashboardApi, type DocsOverviewResponse, type ParsedPlan } from '@/api/docsDashboardApi';
import type { InspectorTarget } from '@/components/modules/docs_dashboard/ContextInspectorPane';

type DashboardSection = 'board' | 'plan-detail' | 'issues' | 'specs' | 'architecture';

export function useDocsDashboard() {
	const [activeSection, setActiveSection] = useState<DashboardSection>('board');
	const [selectedPlanSlug, setSelectedPlanSlug] = useState('user_management_rbac');
	const [selectedArchitectureId, setSelectedArchitectureId] = useState<string | undefined>();
	const [inspectorTarget, setInspectorTarget] = useState<InspectorTarget>(null);
	const [planDirty, setPlanDirty] = useState(false);
	const [inspectorDirty, setInspectorDirty] = useState(false);
	const [planSaving, setPlanSaving] = useState(false);
	const [inspectorSaving, setInspectorSaving] = useState(false);
	const [issueSearch, setIssueSearch] = useState('');
	const [priorityFilter, setPriorityFilter] = useState('ALL');
	const [statusFilter, setStatusFilter] = useState('ALL');
	const [areaFilter, setAreaFilter] = useState('ALL');
	const [showLegacyPlans, setShowLegacyPlans] = useState(false);
	const [isPlanSidebarCollapsed, setIsPlanSidebarCollapsed] = useState(false);
	const [overview, setOverview] = useState<DocsOverviewResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [refreshVersion, setRefreshVersion] = useState(0);
	const [error, setError] = useState<string | null>(null);
	const [selectedSpecPath, setSelectedSpecPath] = useState('docs/arch/README.md');
	const [specContent, setSpecContent] = useState('');
	const [isEditingSpec, setIsEditingSpec] = useState(false);
	const [savingSpec, setSavingSpec] = useState(false);
	const [specError, setSpecError] = useState<string | null>(null);
	const [specLoading, setSpecLoading] = useState(false);
	const [specDirty, setSpecDirty] = useState(false);
	const specContext = useRef({ section: activeSection, path: selectedSpecPath, version: 0 });
	if (specContext.current.section !== activeSection || specContext.current.path !== selectedSpecPath) {
		specContext.current = { section: activeSection, path: selectedSpecPath, version: specContext.current.version + 1 };
	}

	const fetchOverview = useCallback(async () => {
		setRefreshVersion((version) => version + 1);
		setLoading(true);
		setError(null);
		try {
			setOverview(await docsDashboardApi.getOverview());
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => { void fetchOverview(); }, [fetchOverview]);

	useEffect(() => {
		if (activeSection !== 'specs' || !selectedSpecPath) return;
		let cancelled = false;
		setIsEditingSpec(false);
		setSpecError(null);
		setSpecLoading(true);
		setSpecContent('');
		docsDashboardApi.getFile(selectedSpecPath).then((file) => {
			if (!cancelled) setSpecContent(file.content);
		}).catch((err: unknown) => {
			if (!cancelled) setSpecError(`Không thể tải tài liệu: ${err instanceof Error ? err.message : String(err)}`);
		}).finally(() => {
			if (!cancelled) setSpecLoading(false);
		});
		return () => { cancelled = true; };
	}, [activeSection, selectedSpecPath, refreshVersion]);

	const handlePlanUpdated = (updated: ParsedPlan) => {
		setOverview((current) => current && {
			...current,
			plans: current.plans.map((plan) => plan.slug === updated.slug ? updated : plan),
		});
	};

	const handleSaveSpec = async () => {
		const version = specContext.current.version;
		setSavingSpec(true);
		setSpecError(null);
		try {
			await docsDashboardApi.saveFile(selectedSpecPath, specContent);
			if (version === specContext.current.version) {
				setSpecDirty(false);
				setIsEditingSpec(false);
			}
			await fetchOverview();
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			if (version === specContext.current.version) setSpecError(message);
			else setError(`Không thể lưu ${selectedSpecPath}: ${message}`);
		} finally {
			setSavingSpec(false);
		}
	};

	const confirmDiscard = (dirty: boolean) =>
		!dirty || window.confirm('Có bản nháp chưa lưu. Bạn có muốn bỏ các thay đổi này?');
	const selectSection = (section: DashboardSection) => {
		if (section === activeSection) return;
		if (!confirmDiscard((activeSection === 'plan-detail' && planDirty) || (activeSection === 'specs' && specDirty))) return;
		setPlanDirty(false);
		setSpecDirty(false);
		setActiveSection(section);
	};
	const openArchitectureDiagram = (id: string) => {
		if (!confirmDiscard(planDirty || specDirty || inspectorDirty)) return;
		setPlanDirty(false);
		setSpecDirty(false);
		setInspectorDirty(false);
		setInspectorTarget(null);
		setSelectedArchitectureId(id);
		setActiveSection('architecture');
	};
	const handleSelectIssue = useCallback((issueId: string) => {
		if (inspectorDirty && !window.confirm('Có bản nháp chưa lưu. Bạn có muốn bỏ các thay đổi này?')) return;
		setInspectorTarget({ type: 'issue', issueId });
		setInspectorDirty(false);
	}, [inspectorDirty]);
	const handleSelectFileRef = useCallback((fileRef: string) => {
		if (inspectorDirty && !window.confirm('Có bản nháp chưa lưu. Bạn có muốn bỏ các thay đổi này?')) return;
		setInspectorTarget({ type: 'file', fileRef });
		setInspectorDirty(false);
	}, [inspectorDirty]);
	const handleSelectPlan = useCallback((slug: string) => {
		const cleanSlug = slug.replace(/^\[`?([^\]]+?)`?\]\([^)]+\)$/, '$1')
			.replace(/`/g, '').replace(/^\.plan\//, '').replace(/\.md$/, '').trim();
		if (activeSection === 'plan-detail' && cleanSlug === selectedPlanSlug) return;
		if ((planDirty || specDirty) && !window.confirm('Có bản nháp chưa lưu. Bạn có muốn bỏ các thay đổi này?')) return;
		setPlanDirty(false);
		setSpecDirty(false);
		setSelectedPlanSlug(cleanSlug);
		setActiveSection('plan-detail');
	}, [activeSection, selectedPlanSlug, planDirty, specDirty]);
	const selectedPlan = useMemo(() => overview?.plans.find((p) => p.slug === selectedPlanSlug), [overview, selectedPlanSlug]);
	const allAreas = useMemo(() => Array.from(new Set(overview?.issues.flatMap((i) => i.area) ?? [])).sort(), [overview]);
	const filteredIssues = useMemo(() => (overview?.issues ?? []).filter((issue) => {
		if (priorityFilter !== 'ALL' && issue.priority !== priorityFilter) return false;
		const status = issue.status.toLowerCase();
		if (statusFilter === 'OPEN' && !status.startsWith('open')) return false;
		if (statusFilter === 'NEEDS_SPEC' && !status.includes('needs spec')) return false;
		if (statusFilter === 'PLANNED' && !status.includes('planned') && !status.includes('in progress')) return false;
		if (statusFilter === 'RESOLVED' && !status.startsWith('resolved')) return false;
		if (areaFilter !== 'ALL' && !issue.area.includes(areaFilter)) return false;
		if (issueSearch.trim()) {
			const query = issueSearch.toLowerCase();
			return issue.id.toLowerCase().includes(query) || issue.title.toLowerCase().includes(query) || issue.bodyMarkdown.toLowerCase().includes(query);
		}
		return true;
	}), [overview, priorityFilter, statusFilter, areaFilter, issueSearch]);
	const boardTaskSlugs = useMemo(() => {
		const slugs = new Set<string>();
		for (const row of overview?.board.activeTaskRows ?? []) {
			const match = (row[0] || '').match(/\[`?([^\]]+?)`?\]/);
			if (match) slugs.add(match[1].trim());
		}
		return slugs;
	}, [overview]);
	const sidebarPlans = useMemo(() => (overview?.plans ?? []).filter(
		(plan) => showLegacyPlans || boardTaskSlugs.has(plan.slug) || plan.validation.status === 'valid',
	), [overview, showLegacyPlans, boardTaskSlugs]);
	const boardPlans = useMemo(() => Array.from(boardTaskSlugs).flatMap((slug) => {
		const found = overview?.plans.find((plan) => plan.slug === slug);
		return found ? [found] : [];
	}), [overview, boardTaskSlugs]);
	const schemaWarningCount = useMemo(() => overview
		? overview.plans.filter((plan) => boardTaskSlugs.has(plan.slug) && plan.validation.status === 'warning').length + overview.issueLinterWarnings.length
		: 0, [overview, boardTaskSlugs]);

	return {
		overview, loading, error, fetchOverview, handlePlanUpdated, refreshVersion,
		selectedSpecPath, setSelectedSpecPath, specContent, setSpecContent,
		isEditingSpec, setIsEditingSpec, savingSpec, specError, specLoading, specDirty, setSpecDirty,
		handleSaveSpec,
		activeSection, selectedPlanSlug, inspectorTarget, setInspectorTarget, planDirty, setPlanDirty,
		planSaving, setPlanSaving, inspectorDirty, setInspectorDirty, inspectorSaving, setInspectorSaving,
		confirmDiscard, selectSection, issueSearch, setIssueSearch,
		priorityFilter, setPriorityFilter, statusFilter, setStatusFilter, areaFilter, setAreaFilter,
		showLegacyPlans, setShowLegacyPlans, isPlanSidebarCollapsed, setIsPlanSidebarCollapsed,
		handleSelectIssue, handleSelectFileRef, handleSelectPlan, selectedPlan, allAreas, filteredIssues,
		sidebarPlans, boardPlans, schemaWarningCount,
		selectedArchitectureId, openArchitectureDiagram,
	};
}
