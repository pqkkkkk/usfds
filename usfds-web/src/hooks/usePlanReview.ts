import { useEffect, useRef, useState, type FormEvent } from 'react';
import { docsDashboardApi, type ParsedPlan } from '@/api/docsDashboardApi';

type PlanViewTab = 'review' | 'spec' | 'full' | 'editor';

export function usePlanReview(
	plan: ParsedPlan,
	onPlanUpdated: (plan: ParsedPlan) => void,
	onRefreshOverview: () => Promise<void>,
	onDirtyChange?: (dirty: boolean) => void,
	onSavingChange?: (saving: boolean) => void,
	externalEditLocked = false,
) {
	const [activeTab, setActiveTab] = useState<PlanViewTab>(
		plan.validation.status === 'legacy' ? 'full' : 'review',
	);
	const [selectedMilestoneFilter, setSelectedMilestoneFilter] = useState('ALL');
	const [testMilestoneFilter, setTestMilestoneFilter] = useState('ALL');
	const [rawBuffer, setRawBuffer] = useState(plan.raw);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [newQuestion, setNewQuestion] = useState('');
	const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
	const [collapsedMilestones, setCollapsedMilestones] = useState<Record<number, boolean>>({});
	const previousPlan = useRef({ slug: plan.slug, raw: plan.raw });

	useEffect(() => {
		const previous = previousPlan.current;
		setRawBuffer((buffer) => previous.slug !== plan.slug || buffer === previous.raw ? plan.raw : buffer);
		previousPlan.current = { slug: plan.slug, raw: plan.raw };
	}, [plan.slug, plan.raw]);

	useEffect(() => {
		onDirtyChange?.(rawBuffer !== plan.raw);
	}, [onDirtyChange, rawBuffer, plan.raw]);

	useEffect(() => {
		setSelectedMilestoneFilter('ALL');
		setTestMilestoneFilter('ALL');
		setOpenSections({});
		setCollapsedMilestones({});
		setActiveTab(plan.validation.status === 'legacy' ? 'full' : 'review');
		setError(null);
	}, [plan.slug, plan.validation.status]);

	const run = async (action: () => Promise<void>) => {
		setSaving(true);
		onSavingChange?.(true);
		setError(null);
		try {
			await action();
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSaving(false);
			onSavingChange?.(false);
		}
	};

	const handleStatusChange = (status: string) => run(async () => {
		onPlanUpdated(await docsDashboardApi.updatePlanStatus(plan.slug, status));
		await onRefreshOverview();
	});

	const handleToggleCheckbox = (lineNumber: number, currentChecked: boolean) => run(async () => {
		onPlanUpdated(await docsDashboardApi.togglePlanCheckbox(plan.slug, lineNumber, !currentChecked));
		await onRefreshOverview();
	});

	const handleAddQuestion = (event: FormEvent) => {
		event.preventDefault();
		if (!newQuestion.trim() || saving || externalEditLocked || rawBuffer !== plan.raw) return;
		void run(async () => {
			const updated = await docsDashboardApi.appendPlanQuestion(plan.slug, newQuestion.trim());
			setNewQuestion('');
			onPlanUpdated(updated);
			await onRefreshOverview();
		});
	};

	const handleSaveRaw = () => run(async () => {
		await docsDashboardApi.saveFile(plan.filePath, rawBuffer);
		await onRefreshOverview();
		setActiveTab('review');
	});

	return {
		dirty: rawBuffer !== plan.raw, activeTab, setActiveTab, selectedMilestoneFilter, setSelectedMilestoneFilter,
		testMilestoneFilter, setTestMilestoneFilter, rawBuffer, setRawBuffer, saving, error,
		newQuestion, setNewQuestion, openSections, collapsedMilestones, setCollapsedMilestones,
		toggleSection: (id: string) => setOpenSections((prev) => ({ ...prev, [id]: !prev[id] })),
		handleStatusChange, handleToggleCheckbox, handleAddQuestion, handleSaveRaw,
	};
}
