import React from 'react';
import {
	CheckCircle2,
	AlertTriangle,
	ShieldCheck,
	FileCode2,
	CheckSquare,
	Square,
	Flame,
	Beaker,
	Target,
	GitMerge,
	GitBranch,
	HelpCircle,
	Edit3,
	Save,
	Plus,
	Layers,
	FileText,
	ChevronDown,
	ChevronRight,
	BookOpen,
	ClipboardCheck,
} from 'lucide-react';
import type { ParsedPlan } from '@/api/docsDashboardApi';
import { usePlanReview } from '@/hooks/usePlanReview';
import { usePlanArchitectureLinks } from '@/hooks/usePlanArchitectureLinks';
import { ARCHITECTURE_DIAGRAMS } from '@/utils/docsArchitecture';
import type { InspectorTarget } from './ContextInspectorPane';
import {
	RichDocRenderer,
	InlineSmartText,
	cleanMarkdownPlain,
	formatShortFileRef,
} from './RichDocRenderer';

interface PlanReviewViewProps {
	plan: ParsedPlan;
	isLight?: boolean;
	wideLayout?: boolean;
	onSelectIssue: (issueId: string) => void;
	onSelectFileRef: (fileRef: string) => void;
	onSelectPlan: (slug: string) => void;
	onPlanUpdated: (updated: ParsedPlan) => void;
	onRefreshOverview: () => Promise<void>;
	onDirtyChange?: (dirty: boolean) => void;
	onSelectDiagram?: (diagramId: string) => void;
	inspectorSelection?: InspectorTarget;
	externalEditLocked?: boolean;
	onSavingChange?: (saving: boolean) => void;
}

interface CollapsibleCardProps {
	id: string;
	icon: React.ReactNode;
	title: string;
	badge?: React.ReactNode;
	isOpen: boolean;
	isLight: boolean;
	accentBorder?: string;
	onToggle: (id: string) => void;
	children: React.ReactNode;
}

const CollapsibleCard: React.FC<CollapsibleCardProps> = ({
	id,
	icon,
	title,
	badge,
	isOpen,
	isLight,
	accentBorder,
	onToggle,
	children,
}) => {
	const baseBorder =
		accentBorder || (isLight ? 'border-zinc-200/90' : 'border-zinc-800/90');
	const surface = isLight ? 'bg-white shadow-sm' : 'bg-[#121215]';
	const headerHover = isLight ? 'hover:bg-zinc-50' : 'hover:bg-zinc-900/60';

	return (
		<section
			className={`rounded-2xl border overflow-hidden transition ${surface} ${baseBorder}`}
		>
			<button
				type="button"
				onClick={() => onToggle(id)}
				aria-expanded={isOpen}
				className={`w-full px-5 py-4 flex flex-wrap items-center justify-between gap-4 text-left transition ${headerHover}`}
			>
				<div className="flex flex-1 basis-64 items-center gap-3 min-w-0">
					<span className={isLight ? 'text-zinc-400' : 'text-zinc-500'}>
						{isOpen ? (
							<ChevronDown className="w-4 h-4" />
						) : (
							<ChevronRight className="w-4 h-4" />
						)}
					</span>
					<span className="shrink-0">{icon}</span>
					<span
						className={`min-w-0 break-words text-sm font-bold ${
							isLight ? 'text-zinc-900' : 'text-zinc-100'
						}`}
					>
						{title}
					</span>
				</div>
				{badge && <div className="min-w-0 max-w-full flex items-center gap-2 break-words">{badge}</div>}
			</button>

			{isOpen && (
				<div
					className={`px-6 pb-6 pt-2 border-t ${
						isLight ? 'border-zinc-100' : 'border-zinc-800/60'
					}`}
				>
					{children}
				</div>
			)}
		</section>
	);
};

export const PlanReviewView: React.FC<PlanReviewViewProps> = ({
	plan,
	isLight = false,
	wideLayout = false,
	onSelectIssue,
	onSelectFileRef,
	onSelectPlan,
	onPlanUpdated,
	onRefreshOverview,
	onDirtyChange,
	onSelectDiagram,
	inspectorSelection,
	externalEditLocked = false,
	onSavingChange,
}) => {
	const containerWidthClass = wideLayout ? 'max-w-6xl' : 'max-w-5xl';
	const isDoneOrInProgress =
		plan.status.toLowerCase().includes('done') ||
		plan.status.toLowerCase().includes('in progress') ||
		plan.status.toLowerCase().includes('review') ||
		plan.hotspots.length > 0;

	const {
		dirty, activeTab, setActiveTab, selectedMilestoneFilter, setSelectedMilestoneFilter,
		testMilestoneFilter, setTestMilestoneFilter, rawBuffer, setRawBuffer, saving, error,
		newQuestion, setNewQuestion, openSections, collapsedMilestones, setCollapsedMilestones,
		toggleSection, handleStatusChange, handleToggleCheckbox, handleAddQuestion, handleSaveRaw,
	} = usePlanReview(plan, onPlanUpdated, onRefreshOverview, onDirtyChange, onSavingChange, externalEditLocked);
	const architecture = usePlanArchitectureLinks(plan, onSelectFileRef, inspectorSelection);
	const scopeText = cleanMarkdownPlain(plan.scopeVerdict);
	const scopeLabel = scopeText.match(/^(?:OK|TOO-BROAD|TOO-SMALL)\b/i)?.[0] ?? scopeText;

	const todayShort = new Date().toISOString().slice(2, 10);

	const quickStatuses = [
		{ label: 'Draft', value: 'Draft' },
		{ label: `Approve (${todayShort})`, value: `Approved (${todayShort})` },
		{ label: 'In progress (M1)', value: 'In progress (M1)' },
		{ label: 'Review', value: 'Review' },
		{ label: `Done (${todayShort})`, value: `Done (${todayShort})` },
	];

	// Compute milestone & manual E2E completion stats
	const totalCheckItems = plan.milestones.reduce(
		(acc, m) => acc + m.items.length,
		0
	);
	const doneCheckItems = plan.milestones.reduce(
		(acc, m) => acc + m.items.filter((i) => i.checked).length,
		0
	);
	const doneMilestones = plan.milestones.filter((m) => m.checked).length;
	const doneE2eItems = plan.manualE2eItems.filter((i) => i.checked).length;

	const conflictBadgeColor = plan.conflictVerdict
		.toUpperCase()
		.includes('PARALLEL-SAFE')
		? isLight
			? 'bg-emerald-50 text-emerald-700 border-emerald-300'
			: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
		: plan.conflictVerdict.toUpperCase().includes('BLOCKED')
			? isLight
				? 'bg-rose-50 text-rose-700 border-rose-300'
				: 'bg-rose-500/20 text-rose-300 border-rose-500/40'
			: plan.conflictVerdict
				? isLight
					? 'bg-amber-50 text-amber-700 border-amber-300'
					: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
				: isLight
					? 'bg-zinc-100 text-zinc-600 border-zinc-300'
					: 'bg-zinc-800 text-zinc-400 border-zinc-700';

	const tagColorMap: Record<string, string> = {
		tests: isLight
			? 'bg-purple-50 text-purple-700 border-purple-200'
			: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
		core: isLight
			? 'bg-blue-50 text-blue-700 border-blue-200'
			: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
		infra: isLight
			? 'bg-amber-50 text-amber-700 border-amber-200'
			: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
		server: isLight
			? 'bg-emerald-50 text-emerald-700 border-emerald-200'
			: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
		worker: isLight
			? 'bg-orange-50 text-orange-700 border-orange-200'
			: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
		web: isLight
			? 'bg-sky-50 text-sky-700 border-sky-200'
			: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
		verify: isLight
			? 'bg-teal-50 text-teal-700 border-teal-200'
			: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
		e2e: isLight
			? 'bg-indigo-50 text-indigo-700 border-indigo-200'
			: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
	};

	const findSectionContent = (prefix: string): string => {
		for (const [k, v] of Object.entries(plan.sections)) {
			if (prefix === '2.5') {
				if (/^2\.5(?:\.|\s|$)/i.test(k)) {
					return v;
				}
				continue;
			}
			const intMatch = prefix.match(/^(\d+)\.$/);
			if (intMatch) {
				const numRegex = new RegExp(`^${intMatch[1]}\\.(?!\\d)`);
				if (numRegex.test(k)) {
					return v;
				}
				continue;
			}
			if (k.startsWith(prefix)) {
				return v;
			}
		}
		return '';
	};

	const testMilestones = Array.from(
		new Set(plan.acceptanceTests.map((t) => t.milestone).filter(Boolean))
	);
	const filteredAcceptanceTests = plan.acceptanceTests.filter(
		(t) => testMilestoneFilter === 'ALL' || t.milestone === testMilestoneFilter
	);

	const showPostCodeCards =
		plan.hotspots.length > 0 ||
		plan.manualE2eItems.length > 0 ||
		isDoneOrInProgress;
	const showDesignCard =
		Boolean(plan.designApproachMarkdown) ||
		plan.validation.schemaVersion === 'v2';
	const sec9Raw = findSectionContent('9.');

	return (
		<div className="flex flex-col h-full overflow-y-auto md:overflow-hidden">
			{/* 1. Clean Top Plan Decision & Metadata Header */}
			<div
				className={`px-4 md:px-8 py-5 border-b space-y-4 shrink-0 ${
					isLight
						? 'bg-white border-zinc-200'
						: 'bg-[#0f0f12] border-zinc-800/90'
				}`}
			>
				<div className={`${containerWidthClass} mx-auto space-y-3.5`}>
					<div className="flex flex-wrap items-start justify-between gap-4">
						<div className="space-y-2 min-w-0 flex-[1_1_100%] xl:flex-[1_1_0%]">
							<div className="flex flex-wrap items-center gap-2">
								<span
									className={`px-2.5 py-0.5 rounded-md font-mono text-xs font-semibold border ${
										isLight
											? 'bg-zinc-100 border-zinc-200 text-zinc-700'
											: 'bg-zinc-900 border-zinc-800 text-zinc-300'
									}`}
								>
									.plan/{plan.slug}.md
								</span>

								{/* Schema Validation Badge */}
								{plan.validation.status === 'valid' && (
									<span
										className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono border ${
											isLight
												? 'bg-emerald-50 text-emerald-700 border-emerald-200'
												: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
										}`}
									>
										<ShieldCheck className="w-3.5 h-3.5" />
										{plan.validation.schemaVersion === 'v1'
											? 'Chuẩn v1 (§1–§8)'
											: 'Chuẩn Template v2 (§1–§9)'}
									</span>
								)}
								{plan.validation.status === 'warning' && (
									<span
										className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-rose-500/20 text-rose-400 border border-rose-500/40"
										title={plan.validation.messages.join(' | ')}
									>
										<AlertTriangle className="w-3.5 h-3.5" />
										Lỗi cấu trúc: {plan.validation.messages[0]}
									</span>
								)}
								{plan.validation.status === 'legacy' && (
									<span
										className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono border ${
											isLight
												? 'bg-zinc-100 text-zinc-600 border-zinc-300'
												: 'bg-zinc-800 text-zinc-400 border-zinc-700'
										}`}
									>
										Plan định dạng cũ (Pre-26-11-14)
									</span>
								)}

								{/* Conflict Verdict Badge */}
								{plan.conflictVerdict && (
									<span
										className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold border ${conflictBadgeColor}`}
									>
										<GitMerge className="w-3 h-3" />
										{cleanMarkdownPlain(plan.conflictVerdict.split('(')[0])}
									</span>
								)}

								{/* Issues Pills */}
								{plan.issues.map((issId) => (
									<button
										key={issId}
										type="button"
										onClick={() => onSelectIssue(issId)}
										className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-mono font-bold transition border ${
											isLight
												? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
												: 'bg-amber-500/20 text-amber-300 border-amber-500/30 hover:bg-amber-500/30'
										}`}
									>
										{issId}
									</button>
								))}
							</div>

							<h1
								className={`text-xl font-bold leading-snug ${
									isLight ? 'text-zinc-900' : 'text-zinc-100'
								}`}
							>
								{cleanMarkdownPlain(plan.title)}
							</h1>
						</div>

						{/* Clear Status Dropdown + Action Button */}
						{plan.validation.status !== 'legacy' && (
							<div className="flex items-center gap-2.5 shrink-0">
								{plan.status.toLowerCase().startsWith('draft') && (
									<button
										type="button"
										disabled={saving || dirty || externalEditLocked}
										onClick={() =>
											handleStatusChange(`Approved (${todayShort})`)
										}
										className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
									>
										<CheckCircle2 className="w-3.5 h-3.5" />
										<span>Duyệt Plan (Approve)</span>
									</button>
								)}

								<div
									className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border ${
										isLight
											? 'bg-zinc-50 border-zinc-200'
											: 'bg-[#141418] border-zinc-800'
									}`}
								>
									<span
										className={`text-[11px] font-mono ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										Đổi trạng thái:
									</span>
									<select
										disabled={saving || dirty || externalEditLocked}
										value={plan.status}
										onChange={(e) => handleStatusChange(e.target.value)}
										className={`text-xs font-mono font-bold bg-transparent focus:outline-none cursor-pointer ${
											isLight ? 'text-zinc-900' : 'text-blue-400'
										}`}
									>
										{!quickStatuses.some((st) => st.value === plan.status) && <option value={plan.status}>{plan.status}</option>}
										{quickStatuses.map((st) => (
											<option
												key={st.label}
												value={st.value}
												className={
													isLight
														? 'bg-white text-zinc-900'
														: 'bg-zinc-900 text-zinc-100'
												}
											>
												{st.value}
											</option>
										))}
									</select>
								</div>
							</div>
						)}
					</div>

					{/* Two Primary Plan Tabs + Secondary Read/Edit + Milestone Progress */}
					<div
						className={`flex flex-wrap items-center justify-between gap-4 pt-3 border-t ${
							isLight ? 'border-zinc-200/80' : 'border-zinc-800/80'
						}`}
					>
						<div className="flex flex-wrap items-center gap-2">
							<button
								type="button"
								onClick={() => setActiveTab('review')}
								className={`px-3.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-2 transition border ${
									activeTab === 'review'
										? isLight
											? 'bg-blue-50 text-blue-700 border-blue-200 font-semibold'
											: 'bg-blue-500/15 text-blue-300 border-blue-500/30 font-semibold'
										: isLight
											? 'border-transparent text-zinc-600 hover:bg-zinc-100'
											: 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
								}`}
							>
								<Beaker className="w-3.5 h-3.5" />
								<span>Review Mode</span>
								{plan.acceptanceTests.length > 0 && (
									<span
										className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
											isLight
												? 'bg-blue-100 text-blue-800'
												: 'bg-zinc-800 text-zinc-300'
										}`}
									>
										{plan.acceptanceTests.length} tests
									</span>
								)}
								{plan.mermaidBlocks.length > 0 && (
									<span
										className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
											isLight
												? 'bg-emerald-100 text-emerald-800'
												: 'bg-emerald-500/20 text-emerald-300'
										}`}
									>
										{plan.mermaidBlocks.length} sơ đồ
									</span>
								)}
							</button>

							<button
								type="button"
								onClick={() => setActiveTab('spec')}
								className={`px-3.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-2 transition border ${
									activeTab === 'spec'
										? isLight
											? 'bg-blue-50 text-blue-700 border-blue-200 font-semibold'
											: 'bg-blue-500/15 text-blue-300 border-blue-500/30 font-semibold'
										: isLight
											? 'border-transparent text-zinc-600 hover:bg-zinc-100'
											: 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
								}`}
							>
								<Layers className="w-3.5 h-3.5" />
								<span>Agent Spec</span>
								{plan.filesTable.length > 0 ? (
									<span
										className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
											isLight
												? 'bg-zinc-200 text-zinc-700'
												: 'bg-zinc-800 text-zinc-300'
										}`}
									>
										{plan.filesTable.length} files
									</span>
								) : (
									plan.milestones.length > 0 && (
										<span
											className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
												isLight
													? 'bg-zinc-200 text-zinc-700'
													: 'bg-zinc-800 text-zinc-300'
											}`}
										>
											{plan.milestones.length} M
										</span>
									)
								)}
							</button>

							<div
								className={`h-5 w-px mx-1 ${
									isLight ? 'bg-zinc-200' : 'bg-zinc-800'
								}`}
							/>

							<button
								type="button"
								onClick={() => setActiveTab('full')}
								className={`px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 transition border ${
									activeTab === 'full'
										? isLight
											? 'bg-zinc-100 text-zinc-900 border-zinc-300 font-semibold'
											: 'bg-zinc-800 text-zinc-100 border-zinc-700 font-semibold'
										: isLight
											? 'border-transparent text-zinc-600 hover:bg-zinc-100'
											: 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
								}`}
							>
								<FileText className="w-3.5 h-3.5" />
								<span>Đọc toàn văn</span>
							</button>

							<button
								type="button"
								onClick={() => setActiveTab('editor')}
								className={`px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 transition border ${
									activeTab === 'editor'
										? isLight
											? 'bg-zinc-100 text-zinc-900 border-zinc-300 font-semibold'
											: 'bg-zinc-800 text-zinc-100 border-zinc-700 font-semibold'
										: isLight
											? 'border-transparent text-zinc-600 hover:bg-zinc-100'
											: 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
								}`}
							>
								<Edit3 className="w-3.5 h-3.5" />
								<span>Sửa Markdown</span>
							</button>
						</div>

						{/* Milestone Progress Pill */}
						{plan.milestones.length > 0 && (
							<div
								className={`flex items-center gap-3 text-xs font-mono ${
									isLight ? 'text-zinc-600' : 'text-zinc-400'
								}`}
							>
								<span>
									Milestones: <strong>{doneMilestones}</strong>/
									{plan.milestones.length}
								</span>
								<span>•</span>
								<span>
									Tasks: <strong>{doneCheckItems}</strong>/{totalCheckItems}
								</span>
								<div
									className={`w-24 h-2 rounded-full overflow-hidden border ${
										isLight
											? 'bg-zinc-100 border-zinc-200'
											: 'bg-zinc-900 border-zinc-800'
									}`}
								>
									<div
										className="h-full bg-emerald-500 transition-all"
										style={{
											width: `${
												totalCheckItems > 0
													? Math.round((doneCheckItems / totalCheckItems) * 100)
													: 0
											}%`,
										}}
									/>
								</div>
							</div>
						)}
					</div>
				</div>
			</div>

			{/* 2. Centered, Breathable Main Viewport (max-w-5xl / max-w-6xl mx-auto) */}
			<div className="flex-1 md:overflow-y-auto px-4 py-6 md:px-8 md:py-8">
				<div className={`${containerWidthClass} mx-auto space-y-5`}>
					{activeTab === 'review' && (
						<section aria-labelledby="plan-review-summary" className={`rounded-xl border p-5 ${isLight ? 'border-zinc-200 bg-white' : 'border-zinc-800 bg-zinc-900'}`}>
							<h2 id="plan-review-summary" className="text-sm font-semibold">Tóm tắt review</h2>
							<p className={`mt-2 text-sm leading-6 ${isLight ? 'text-zinc-700' : 'text-zinc-300'}`}>
								{plan.goal || 'Plan chưa khai báo mục tiêu.'}
							</p>
							<div className={`mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>
								<span>{plan.mermaidBlocks.length} sơ đồ thiết kế</span>
								<span>{plan.acceptanceTests.length} kiểm thử chấp nhận</span>
								<span>{plan.openQuestions.length} câu hỏi mở</span>
							</div>
						</section>
					)}
					{activeTab !== 'editor' && (
						<section aria-labelledby="plan-architecture-links" className={`rounded-xl border p-5 ${isLight ? 'border-zinc-200 bg-white' : 'border-zinc-800 bg-zinc-900'}`}>
							<h2 id="plan-architecture-links" className="text-base font-semibold">Liên kết kiến trúc</h2>
							<p className={`mt-1 text-sm ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>Đối chiếu nguồn được nhắc đến và gợi ý theo file tác động.</p>
							{architecture.error && <p role="alert" className="mt-3 text-sm text-rose-500">{architecture.error}</p>}
							<div className="mt-4 grid gap-5 lg:grid-cols-2">
								{([
									{ title: 'Đã khai báo', items: architecture.declared },
									{ title: 'Gợi ý', items: architecture.suggested },
								]).map(({ title, items }) => (
									<div key={title}>
										<h3 className="text-sm font-semibold">{title}</h3>
										{items.length === 0 ? <p className="mt-2 text-sm text-zinc-500">Không có liên kết phù hợp.</p> : (
											<ul className="mt-2 space-y-3">
												{items.map((link) => {
													const diagram = ARCHITECTURE_DIAGRAMS.find((item) => item.id === link.diagramId);
													return <li key={`${link.label}-${link.path}`} className="text-sm">
														<button type="button" className="break-all text-left text-blue-500 underline underline-offset-2" onClick={() => void architecture.openLink(link)}>{link.label}</button>
														<p className={`mt-1 break-words text-xs ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>Nguồn: {link.evidence}</p>
														{diagram && onSelectDiagram && <button type="button" className="mt-1 text-xs text-blue-500 underline underline-offset-2" onClick={() => onSelectDiagram(diagram.id)}>Xem sơ đồ {diagram.title}</button>}
													</li>;
												})}
											</ul>
										)}
									</div>
								))}
							</div>
						</section>
					)}
					{dirty && <p role="status" className="mb-3 text-sm text-amber-600">Lưu bản nháp Markdown trước khi thay đổi trạng thái, checklist hoặc câu hỏi.</p>}
					{externalEditLocked && <p role="status" className="mb-3 text-sm text-amber-600">Lưu hoặc bỏ bản nháp trong bảng ngữ cảnh trước khi sửa plan.</p>}
					{error && (
						<div role="alert" className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500">
							{error}
						</div>
					)}
					{/* Schema Warnings Box if any */}
					{plan.validation.status === 'warning' && (
						<div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 space-y-1.5">
							<div className="flex items-center gap-2 text-xs font-bold text-rose-400">
								<AlertTriangle className="w-4 h-4" />
								<span>
									File Plan này chưa tuân thủ đúng .agents/skills/usfds-plan/template.md
								</span>
							</div>
							<ul className="list-disc list-inside text-xs text-rose-300 font-mono space-y-1">
								{plan.validation.messages.map((m, idx) => (
									<li key={idx}>{m}</li>
								))}
							</ul>
						</div>
					)}

					{/* TAB 1: REVIEW MODE */}
					{activeTab === 'review' && (
						<div className="space-y-5">
							{/* §2 Goal, Scope Verdict & Non-goals */}
							<CollapsibleCard
								id="sec2"
								icon={<Target className="w-4 h-4 text-blue-400" />}
								title="§2. Mục tiêu, Phạm vi & Giả định (Goal & Scope)"
								isOpen={!!openSections.sec2}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									plan.scopeVerdict ? (
										<span
											className={`min-w-0 px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold border ${
												isLight
													? 'bg-blue-50 text-blue-700 border-blue-200'
													: 'bg-blue-500/15 text-blue-300 border-blue-500/30'
											}`}
										>
											Scope: {scopeLabel}
										</span>
									) : null
								}
							>
								<RichDocRenderer
									markdown={findSectionContent('2.')}
									isLight={isLight}
									onSelectIssue={onSelectIssue}
									onSelectFileRef={onSelectFileRef}
									onSelectPlan={onSelectPlan}
								/>
							</CollapsibleCard>

							{/* §2.5 Design & Approach (Mermaid + Key Decisions + Edge Cases) */}
							{showDesignCard && (
								<CollapsibleCard
									id="sec2_5"
									icon={<GitBranch className="w-4 h-4 text-emerald-400" />}
									title="§2.5. Thiết kế & Hướng tiếp cận (Design & Approach)"
									isOpen={!!openSections.sec2_5}
									isLight={isLight}
									onToggle={toggleSection}
									badge={
										plan.mermaidBlocks.length > 0 ? (
											<span
												className={`px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold border ${
													isLight
														? 'bg-emerald-50 text-emerald-700 border-emerald-200'
														: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
												}`}
											>
												{plan.mermaidBlocks.length} sơ đồ Mermaid
											</span>
										) : (
											<span
												className={`text-xs font-mono ${
													isLight ? 'text-zinc-500' : 'text-zinc-400'
												}`}
											>
												{!plan.designApproachMarkdown ||
												plan.designApproachMarkdown.trim() === '—'
													? '—'
													: 'Không có sơ đồ'}
											</span>
										)
									}
								>
									<RichDocRenderer
										markdown={plan.designApproachMarkdown || '—'}
										isLight={isLight}
										onSelectIssue={onSelectIssue}
										onSelectFileRef={onSelectFileRef}
										onSelectPlan={onSelectPlan}
									/>
								</CollapsibleCard>
							)}

							{/* §5 Acceptance Tests */}
							<CollapsibleCard
								id="sec5"
								icon={<Beaker className="w-4 h-4 text-purple-400" />}
								title="§5. Kiểm thử chấp nhận (Acceptance Tests)"
								isOpen={!!openSections.sec5}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									<span
										className={`text-xs font-mono ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										{plan.acceptanceTests.length} kịch bản test
									</span>
								}
							>
								{plan.acceptanceTests.length === 0 ? (
									<div className="text-xs text-zinc-400 font-mono py-2">
										Chưa có bảng Acceptance Tests chuẩn trong mục §5.
									</div>
								) : (
									<div className="space-y-4 pt-2">
										{/* Milestone Filter Bar inside §5 */}
										{testMilestones.length > 1 && (
											<div className="flex flex-wrap items-center gap-1.5">
												<span
													className={`text-xs font-mono mr-1 ${
														isLight ? 'text-zinc-500' : 'text-zinc-400'
													}`}
												>
													Lọc theo Milestone:
												</span>
												{['ALL', ...testMilestones].map((mId) => {
													const count =
														mId === 'ALL'
															? plan.acceptanceTests.length
															: plan.acceptanceTests.filter(
																	(t) => t.milestone === mId
																).length;
													const active = testMilestoneFilter === mId;
													return (
														<button
															key={mId}
															type="button"
															onClick={() => setTestMilestoneFilter(mId)}
															className={`px-2.5 py-1 rounded-lg text-xs font-mono transition border ${
																active
																	? 'bg-purple-600 text-white border-purple-600 font-semibold'
																	: isLight
																		? 'bg-zinc-100 text-zinc-600 border-zinc-200 hover:bg-zinc-200'
																		: 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200'
															}`}
														>
															{mId === 'ALL' ? 'Tất cả' : mId} ({count})
														</button>
													);
												})}
											</div>
										)}

										<div className="space-y-4">
											{filteredAcceptanceTests.map((tc, idx) => (
												<div
													key={idx}
													className={`p-4 rounded-xl border space-y-3 transition ${
														isLight
															? 'bg-zinc-50/70 border-zinc-200 hover:border-zinc-300'
															: 'bg-[#0c0c0f] border-zinc-800/90 hover:border-zinc-700'
													}`}
												>
													<div className="flex flex-wrap items-center justify-between gap-2">
														<div className="flex items-center gap-2.5">
															<span
																className={`px-2.5 py-0.5 rounded-md text-xs font-mono font-bold border ${
																	isLight
																		? 'bg-purple-50 text-purple-700 border-purple-200'
																		: 'bg-purple-500/20 text-purple-300 border-purple-500/30'
																}`}
															>
																{tc.milestone}
															</span>
															<div
																className={`text-xs font-medium ${
																	isLight ? 'text-zinc-900' : 'text-zinc-100'
																}`}
															>
																<InlineSmartText
																	text={tc.test}
																	isLight={isLight}
																	onSelectIssue={onSelectIssue}
																	onSelectFileRef={onSelectFileRef}
																	onSelectPlan={onSelectPlan}
																/>
															</div>
														</div>
														<div className="text-xs">
															<InlineSmartText
																text={tc.covers}
																isLight={isLight}
																onSelectIssue={onSelectIssue}
																onSelectFileRef={onSelectFileRef}
																onSelectPlan={onSelectPlan}
															/>
														</div>
													</div>

													<div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
														<div
															className={`p-3.5 rounded-xl border ${
																isLight
																	? 'bg-white border-zinc-200/80'
																	: 'bg-[#121216] border-zinc-800/80'
															}`}
														>
															<div
																className={`text-[10px] font-mono uppercase font-semibold mb-1.5 ${
																	isLight ? 'text-zinc-500' : 'text-zinc-400'
																}`}
															>
																Given (Trạng thái đầu)
															</div>
															<div
																className={`leading-6 ${
																	isLight ? 'text-zinc-700' : 'text-zinc-200'
																}`}
															>
																<InlineSmartText
																	text={tc.given}
																	isLight={isLight}
																	onSelectIssue={onSelectIssue}
																	onSelectFileRef={onSelectFileRef}
																	onSelectPlan={onSelectPlan}
																/>
															</div>
														</div>

														<div
															className={`p-3.5 rounded-xl border ${
																isLight
																	? 'bg-white border-zinc-200/80'
																	: 'bg-[#121216] border-zinc-800/80'
															}`}
														>
															<div className="text-[10px] font-mono uppercase font-semibold text-blue-400 mb-1.5">
																When (Hành động)
															</div>
															<div
																className={`leading-6 ${
																	isLight ? 'text-zinc-700' : 'text-zinc-200'
																}`}
															>
																<InlineSmartText
																	text={tc.when}
																	isLight={isLight}
																	onSelectIssue={onSelectIssue}
																	onSelectFileRef={onSelectFileRef}
																	onSelectPlan={onSelectPlan}
																/>
															</div>
														</div>

														<div
															className={`p-3.5 rounded-xl border ${
																isLight
																	? 'bg-emerald-50/40 border-emerald-200'
																	: 'bg-emerald-500/5 border-emerald-500/20'
															}`}
														>
															<div className="text-[10px] font-mono uppercase font-semibold text-emerald-500 mb-1.5">
																Then (Kết quả kỳ vọng)
															</div>
															<div
																className={`leading-6 ${
																	isLight ? 'text-zinc-800' : 'text-zinc-200'
																}`}
															>
																<InlineSmartText
																	text={tc.then}
																	isLight={isLight}
																	onSelectIssue={onSelectIssue}
																	onSelectFileRef={onSelectFileRef}
																	onSelectPlan={onSelectPlan}
																/>
															</div>
														</div>
													</div>
												</div>
											))}
										</div>
									</div>
								)}
							</CollapsibleCard>

							{/* §8 Open Questions */}
							<CollapsibleCard
								id="sec8"
								icon={<HelpCircle className="w-4 h-4 text-amber-400" />}
								title="§8. Câu hỏi mở / Điểm cần chốt (Open Questions)"
								isOpen={!!openSections.sec8}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									plan.openQuestions.length === 0 ? (
										<span className="inline-flex items-center gap-1.5 text-xs font-mono text-emerald-400">
											<CheckCircle2 className="w-3.5 h-3.5" />
											<span>0 câu hỏi tồn đọng</span>
										</span>
									) : (
										<span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-amber-500/20 text-amber-400 font-semibold">
											{plan.openQuestions.length} câu hỏi cần chốt
										</span>
									)
								}
							>
								<div className="space-y-3 pt-2">
									{plan.openQuestions.length === 0 ? (
										<div className="text-xs text-emerald-400 flex items-center gap-1.5 font-mono">
											<CheckCircle2 className="w-3.5 h-3.5" />
											Không có câu hỏi mở tồn đọng.
										</div>
									) : (
										<div className="space-y-2.5">
											{plan.openQuestions.map((q, idx) => (
												<div
													key={idx}
													className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs leading-7"
												>
													<InlineSmartText
														text={q}
														isLight={isLight}
														onSelectIssue={onSelectIssue}
														onSelectFileRef={onSelectFileRef}
														onSelectPlan={onSelectPlan}
													/>
												</div>
											))}
										</div>
									)}

									<form
										onSubmit={handleAddQuestion}
										className="flex items-center gap-2.5 pt-2"
									>
										<input
											type="text"
											value={newQuestion}
											onChange={(e) => setNewQuestion(e.target.value)}
											placeholder="Ghi thêm câu hỏi hoặc quyết định review vào mục §8 của file .md..."
											className={`flex-1 px-3.5 py-2 rounded-xl border text-xs focus:outline-none focus:border-blue-500 ${
												isLight
													? 'bg-zinc-50 border-zinc-200 text-zinc-900'
													: 'bg-[#09090b] border-zinc-800 text-zinc-200'
											}`}
										/>
										<button
											type="submit"
											disabled={saving || dirty || externalEditLocked || !newQuestion.trim()}
											className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-xs font-semibold text-white flex items-center gap-1.5 transition disabled:opacity-40"
										>
											<Plus className="w-3.5 h-3.5" />
											<span>Thêm vào §8</span>
										</button>
									</form>
								</div>
							</CollapsibleCard>

							{/* Post-code review cards when applicable: §7 Hotspots & §9 Manual E2E */}
							{showPostCodeCards && (
								<>
									<CollapsibleCard
										id="sec7"
										icon={<Flame className="w-4 h-4 text-orange-400" />}
										title="§7. Điểm nóng cần Review (Review Hotspots)"
										isOpen={!!openSections.sec7}
										isLight={isLight}
										accentBorder="border-orange-500/30"
										onToggle={toggleSection}
										badge={
											<span className="px-2.5 py-0.5 rounded-md text-xs font-mono bg-orange-500/15 text-orange-400 border border-orange-500/30 font-semibold">
												{plan.hotspots.length} điểm nóng
											</span>
										}
									>
										{plan.hotspots.length === 0 ? (
											<div className="p-4 rounded-xl text-xs text-zinc-400 font-mono">
												Chưa có Review Hotspots (Mục §7 được điền sau khi agent hoàn tất code).
											</div>
										) : (
											<div className="space-y-3.5 pt-2">
												{plan.hotspots.map((hs, idx) => (
													<div
														key={idx}
														className={`p-4 rounded-xl border transition space-y-3 ${
															isLight
																? 'bg-zinc-50 border-zinc-200 hover:border-orange-300'
																: 'bg-[#0c0c0f] border-zinc-800 hover:border-orange-500/40'
														}`}
													>
														<div className="flex flex-wrap items-center gap-2">
															<span className="px-2.5 py-0.5 rounded-md text-xs font-mono font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">
																Hotspot #{idx + 1}{' '}
																{hs.milestone ? `(${hs.milestone})` : ''}
															</span>
															{hs.codeRefs.map((ref) => {
																const { shortLabel, pkgHint } =
																	formatShortFileRef(ref);
																return (
																	<button
																		key={ref}
																		type="button"
																		onClick={() => onSelectFileRef(ref)}
																		title={ref}
																		className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-semibold border transition ${
																			isLight
																				? 'bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100'
																				: 'bg-sky-500/15 text-sky-300 border-sky-500/30 hover:bg-sky-500/25'
																		}`}
																	>
																		<FileCode2 className="w-3.5 h-3.5" />
																		<span>
																			Xem code:{' '}
																			{pkgHint ? `${pkgHint}/` : ''}
																			{shortLabel}
																		</span>
																	</button>
																);
															})}
														</div>
														<div
															className={`text-[13px] leading-7 pl-1 ${
																isLight ? 'text-zinc-700' : 'text-zinc-200'
															}`}
														>
															<InlineSmartText
																text={hs.description}
																isLight={isLight}
																onSelectIssue={onSelectIssue}
																onSelectFileRef={onSelectFileRef}
																onSelectPlan={onSelectPlan}
															/>
														</div>
													</div>
												))}
											</div>
										)}
									</CollapsibleCard>

									<CollapsibleCard
										id="sec9"
										icon={<ClipboardCheck className="w-4 h-4 text-indigo-400" />}
										title="§9. Kiểm thử E2E thủ công (Manual E2E Verification)"
										isOpen={!!openSections.sec9}
										isLight={isLight}
										onToggle={toggleSection}
										badge={
											plan.manualE2eItems.length > 0 ? (
												<span
													className={`px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold border ${
														isLight
															? 'bg-indigo-50 text-indigo-700 border-indigo-200'
															: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
													}`}
												>
													{doneE2eItems}/{plan.manualE2eItems.length} kịch bản E2E
												</span>
											) : (
												<span
													className={`text-xs font-mono ${
														isLight ? 'text-zinc-500' : 'text-zinc-400'
													}`}
												>
													—
												</span>
											)
										}
									>
										{plan.manualE2eItems.length > 0 ? (
											<div className="space-y-2 pt-2">
												{plan.manualE2eItems.map((item) => (
													<div
														key={item.lineNumber}
														className={`flex items-start gap-3 py-2 px-3 rounded-xl border transition ${
															isLight
																? 'bg-zinc-50/70 border-zinc-200 hover:bg-white'
																: 'bg-[#0c0c0f] border-zinc-800/80 hover:bg-zinc-900/60'
														}`}
													>
														<button
															type="button"
															disabled={saving || dirty || externalEditLocked}
															aria-label={`Đánh dấu E2E dòng ${item.lineNumber}`}
															onClick={() =>
																handleToggleCheckbox(
																	item.lineNumber,
																	item.checked
																)
															}
															className="mt-1 shrink-0"
														>
															{item.checked ? (
																<CheckSquare className="w-4 h-4 text-emerald-400" />
															) : (
																<Square className="w-4 h-4 text-zinc-500 hover:text-zinc-300" />
															)}
														</button>
														<span
															className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border shrink-0 mt-0.5 ${tagColorMap.e2e}`}
														>
															e2e
														</span>
														<div
															className={`text-[13px] leading-6 flex-1 ${
																item.checked
																	? 'text-zinc-500 line-through'
																	: isLight
																		? 'text-zinc-800'
																		: 'text-zinc-200'
															}`}
														>
															<InlineSmartText
																text={item.text}
																isLight={isLight}
																onSelectIssue={onSelectIssue}
																onSelectFileRef={onSelectFileRef}
																onSelectPlan={onSelectPlan}
															/>
														</div>
													</div>
												))}
											</div>
										) : sec9Raw && sec9Raw.trim() !== '—' ? (
											<RichDocRenderer
												markdown={sec9Raw}
												isLight={isLight}
												onSelectIssue={onSelectIssue}
												onSelectFileRef={onSelectFileRef}
												onSelectPlan={onSelectPlan}
											/>
										) : (
											<div className="text-xs text-zinc-400 font-mono py-2">
												Không yêu cầu kiểm thử E2E thủ công bổ sung (—).
											</div>
										)}
									</CollapsibleCard>
								</>
							)}
						</div>
					)}

					{/* TAB 2: AGENT SPEC (§1 CONTEXT, §3 FILES, §4 D1-C5, §6 MILESTONES) */}
					{activeTab === 'spec' && (
						<div className="space-y-5">
							{/* §1 Context / Facts */}
							<CollapsibleCard
								id="sec1"
								icon={<BookOpen className="w-4 h-4 text-sky-400" />}
								title="§1. Hiện trạng & Nguyên nhân gốc (Context & Facts)"
								isOpen={!!openSections.sec1}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									<span
										className={`text-xs font-mono ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										Bấm để mở rộng ngữ cảnh
									</span>
								}
							>
								<RichDocRenderer
									markdown={findSectionContent('1.')}
									isLight={isLight}
									onSelectIssue={onSelectIssue}
									onSelectFileRef={onSelectFileRef}
									onSelectPlan={onSelectPlan}
								/>
							</CollapsibleCard>

							{/* §3 Files Table */}
							<CollapsibleCard
								id="sec3"
								icon={<FileCode2 className="w-4 h-4 text-sky-400" />}
								title="§3. Danh sách Files tác động"
								isOpen={!!openSections.sec3}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									<span
										className={`text-xs font-mono ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										{plan.filesTable.length} files
									</span>
								}
							>
								{plan.filesTable.length === 0 ? (
									<div className="text-xs text-zinc-400 font-mono py-2">
										Chưa có danh sách file tác động trong mục §3.
									</div>
								) : (
									<div className="space-y-3 pt-2">
										<div className="flex flex-wrap items-center gap-1.5">
											{[
												'ALL',
												...Array.from(
													new Set(
														plan.filesTable
															.map((f) => f.milestone)
															.filter(Boolean)
													)
												),
											].map((mFilter) => (
												<button
													key={mFilter}
													type="button"
													onClick={() => setSelectedMilestoneFilter(mFilter)}
													className={`px-2.5 py-1 rounded-lg text-xs font-mono transition ${
														selectedMilestoneFilter === mFilter
															? 'bg-blue-600 text-white font-semibold'
															: isLight
																? 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
																: 'bg-zinc-900 text-zinc-400 hover:text-zinc-200'
													}`}
												>
													{mFilter}
												</button>
											))}
										</div>

										<div
											className={`overflow-x-auto rounded-xl border ${
												isLight ? 'border-zinc-200' : 'border-zinc-800'
											}`}
										>
											<table className="w-full text-left border-collapse text-xs">
												<thead>
													<tr
														className={`border-b font-mono text-[11px] ${
															isLight
																? 'bg-zinc-50 border-zinc-200 text-zinc-500'
																: 'bg-zinc-900 border-zinc-800 text-zinc-400'
														}`}
													>
														<th className="px-4 py-3 w-24">Action</th>
														<th className="px-4 py-3">File (Click để xem)</th>
														<th className="px-4 py-3 w-20">Milestone</th>
														<th className="px-4 py-3">Ghi chú</th>
													</tr>
												</thead>
												<tbody
													className={`divide-y ${
														isLight ? 'divide-zinc-200' : 'divide-zinc-800/80'
													}`}
												>
													{plan.filesTable
														.filter(
															(f) =>
																selectedMilestoneFilter === 'ALL' ||
																f.milestone === selectedMilestoneFilter
														)
														.map((f, idx) => (
															<tr key={idx}>
																<td className="px-4 py-3 align-top">
																	<span
																		className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${
																			f.action === 'create'
																				? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
																				: f.action === 'migration'
																					? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
																					: 'bg-blue-500/15 text-blue-400 border-blue-500/30'
																		}`}
																	>
																		{f.action}
																	</span>
																</td>
																<td className="px-4 py-3 font-mono align-top">
																	<button
																		type="button"
																		onClick={() => onSelectFileRef(f.file)}
																		className="text-sky-400 hover:underline text-left flex items-center gap-1.5"
																	>
																		<FileCode2 className="w-3.5 h-3.5 shrink-0" />
																		<span>{f.file}</span>
																	</button>
																</td>
																<td className="px-4 py-3 font-mono align-top">
																	{f.milestone}
																</td>
																<td className="px-4 py-3 align-top leading-7">
																	<InlineSmartText
																		text={f.note}
																		isLight={isLight}
																		onSelectIssue={onSelectIssue}
																		onSelectFileRef={onSelectFileRef}
																		onSelectPlan={onSelectPlan}
																	/>
																</td>
															</tr>
														))}
												</tbody>
											</table>
										</div>
									</div>
								)}
							</CollapsibleCard>

							{/* §4 Conflict Matrix */}
							<CollapsibleCard
								id="sec4"
								icon={<GitMerge className="w-4 h-4 text-emerald-400" />}
								title="§4. Ma trận Phụ thuộc & Xung đột (D1–D2, C1–C5)"
								isOpen={!!openSections.sec4}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									plan.conflictVerdict ? (
										<span
											className={`px-2.5 py-0.5 rounded-md text-xs font-mono border ${conflictBadgeColor}`}
										>
											{cleanMarkdownPlain(plan.conflictVerdict.split('(')[0])}
										</span>
									) : null
								}
							>
								{plan.conflictsTable.length === 0 ? (
									<div className="text-xs text-zinc-400 font-mono py-2">
										Chưa có bảng kiểm tra phụ thuộc trong mục §4.
									</div>
								) : (
									<div
										className={`mt-2 overflow-x-auto rounded-xl border ${
											isLight ? 'border-zinc-200' : 'border-zinc-800'
										}`}
									>
										<table className="w-full text-left border-collapse text-xs">
											<thead>
												<tr
													className={`border-b font-mono text-[11px] ${
														isLight
															? 'bg-zinc-50 border-zinc-200 text-zinc-500'
															: 'bg-zinc-900/80 border-zinc-800 text-zinc-400'
													}`}
												>
													<th className="px-4 py-3 w-14">#</th>
													<th className="px-4 py-3 w-64">Tiêu chí</th>
													<th className="px-4 py-3">Đánh giá</th>
												</tr>
											</thead>
											<tbody
												className={`divide-y ${
													isLight ? 'divide-zinc-200' : 'divide-zinc-800/80'
												}`}
											>
												{plan.conflictsTable.map((row) => {
													const isNo =
														row.answer.toLowerCase().startsWith('no') ||
														row.answer === '—';
													return (
														<tr key={row.id}>
															<td className="px-4 py-3 font-mono font-bold">
																{row.id}
															</td>
															<td
																className={`px-4 py-3 ${
																	isLight ? 'text-zinc-700' : 'text-zinc-300'
																}`}
															>
																{row.check}
															</td>
															<td
																className={`px-4 py-3 font-medium leading-7 ${
																	isNo
																		? isLight
																			? 'text-emerald-700'
																			: 'text-emerald-400'
																		: isLight
																			? 'text-amber-800'
																			: 'text-amber-300'
																}`}
															>
																<InlineSmartText
																	text={row.answer}
																	isLight={isLight}
																	onSelectIssue={onSelectIssue}
																	onSelectFileRef={onSelectFileRef}
																	onSelectPlan={onSelectPlan}
																/>
															</td>
														</tr>
													);
												})}
											</tbody>
										</table>
									</div>
								)}
							</CollapsibleCard>

							{/* §6 Milestones & Interactive Checklist */}
							<CollapsibleCard
								id="sec6"
								icon={<Layers className="w-4 h-4 text-emerald-400" />}
								title="§6. Tiến độ Milestones & Checklist tương tác"
								isOpen={!!openSections.sec6}
								isLight={isLight}
								onToggle={toggleSection}
								badge={
									<span
										className={`text-xs font-mono ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										{doneCheckItems}/{totalCheckItems} mục đã xong
									</span>
								}
							>
								<div className="space-y-4 pt-2">
									{plan.milestones.length === 0 ? (
										<div className="text-xs text-zinc-400 font-mono">
											Không có danh sách checklist trong mục §6.
										</div>
									) : (
										plan.milestones.map((m) => {
											const mCollapsed = !!collapsedMilestones[m.lineNumber];
											const doneInM = m.items.filter((i) => i.checked).length;
											return (
												<div
													key={m.lineNumber}
													className={`rounded-xl border overflow-hidden ${
														isLight
															? 'bg-zinc-50/70 border-zinc-200'
															: 'bg-[#0c0c0f] border-zinc-800'
													}`}
												>
													<div
														className={`px-4 py-3 flex items-center justify-between gap-3 ${
															isLight
																? 'bg-zinc-100/70'
																: 'bg-zinc-900/50'
														}`}
													>
														<div className="flex items-center gap-2.5 min-w-0 flex-1">
															<button
																type="button"
																disabled={saving || dirty || externalEditLocked}
																onClick={() =>
																	handleToggleCheckbox(
																		m.lineNumber,
																		m.checked
																	)
																}
																className="shrink-0"
															>
																{m.checked ? (
																	<CheckSquare className="w-4 h-4 text-emerald-400" />
																) : (
																	<Square className="w-4 h-4 text-zinc-500 hover:text-zinc-300" />
																)}
															</button>
															<button
																type="button"
																onClick={() =>
																	setCollapsedMilestones((prev) => ({
																		...prev,
																		[m.lineNumber]: !prev[m.lineNumber],
																	}))
																}
																className={`text-xs font-bold text-left truncate flex items-center gap-1.5 ${
																	m.checked
																		? 'text-emerald-400'
																		: isLight
																			? 'text-zinc-900'
																			: 'text-zinc-100'
																}`}
															>
																<span>{cleanMarkdownPlain(m.title)}</span>
															</button>
														</div>
														<button
															type="button"
															onClick={() =>
																setCollapsedMilestones((prev) => ({
																	...prev,
																	[m.lineNumber]: !prev[m.lineNumber],
																}))
															}
															className={`text-xs font-mono flex items-center gap-1.5 shrink-0 ${
																isLight ? 'text-zinc-500' : 'text-zinc-400'
															}`}
														>
															<span>
																{doneInM}/{m.items.length}
															</span>
															{mCollapsed ? (
																<ChevronRight className="w-3.5 h-3.5" />
															) : (
																<ChevronDown className="w-3.5 h-3.5" />
															)}
														</button>
													</div>

													{!mCollapsed && (
														<div className="p-3 space-y-1.5">
															{m.items.map((item) => (
																<div
																	key={item.lineNumber}
																	className={`flex items-start gap-3 py-1.5 px-2.5 rounded-lg transition ${
																		isLight
																			? 'hover:bg-white'
																			: 'hover:bg-zinc-900/60'
																	}`}
																>
																	<button
																		type="button"
																		disabled={saving || dirty || externalEditLocked}
																		onClick={() =>
																			handleToggleCheckbox(
																				item.lineNumber,
																				item.checked
																			)
																		}
																		className="mt-1 shrink-0"
																	>
																		{item.checked ? (
																			<CheckSquare className="w-3.5 h-3.5 text-emerald-400" />
																		) : (
																			<Square className="w-3.5 h-3.5 text-zinc-500 hover:text-zinc-300" />
																		)}
																	</button>
																	<span
																		className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border shrink-0 mt-0.5 ${
																			tagColorMap[item.tag] ||
																			(isLight
																				? 'bg-zinc-100 text-zinc-700 border-zinc-200'
																				: 'bg-zinc-800 text-zinc-300 border-zinc-700')
																		}`}
																	>
																		{item.tag}
																	</span>
																	<div
																		className={`text-[13px] leading-6 flex-1 ${
																			item.checked
																				? 'text-zinc-500 line-through'
																				: isLight
																					? 'text-zinc-800'
																					: 'text-zinc-200'
																		}`}
																	>
																		<InlineSmartText
																			text={item.text}
																			isLight={isLight}
																			onSelectIssue={onSelectIssue}
																			onSelectFileRef={onSelectFileRef}
																			onSelectPlan={onSelectPlan}
																		/>
																	</div>
																</div>
															))}
														</div>
													)}
												</div>
											);
										})
									)}

									{/* Checkpoint Logs */}
									{plan.checkpointLogs.length > 0 && (
										<div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-2">
											<div className="text-xs font-mono uppercase text-emerald-400 font-semibold">
												Checkpoint Log (Kết quả chạy test qua từng Milestone)
											</div>
											{plan.checkpointLogs.map((log, idx) => (
												<div key={idx} className="text-xs font-mono leading-6">
													<InlineSmartText
														text={`• ${log}`}
														isLight={isLight}
														onSelectIssue={onSelectIssue}
														onSelectFileRef={onSelectFileRef}
														onSelectPlan={onSelectPlan}
													/>
												</div>
											))}
										</div>
									)}
								</div>
							</CollapsibleCard>
						</div>
					)}

					{/* TAB 3: FULL PLAN RENDERER */}
					{activeTab === 'full' && (
						<div
							className={`p-8 rounded-2xl border ${
								isLight
									? 'bg-white border-zinc-200 shadow-sm'
									: 'bg-[#121215] border-zinc-800'
							}`}
						>
							<RichDocRenderer
								markdown={plan.raw}
								isLight={isLight}
								onSelectIssue={onSelectIssue}
								onSelectFileRef={onSelectFileRef}
								onSelectPlan={onSelectPlan}
							/>
						</div>
					)}

					{/* TAB 4: RAW MARKDOWN EDITOR */}
					{activeTab === 'editor' && (
						<div
							className={`p-6 rounded-2xl border space-y-4 ${
								isLight
									? 'bg-white border-zinc-200 shadow-sm'
									: 'bg-[#121215] border-zinc-800'
							}`}
						>
							<div className="flex items-center justify-between">
								<span className="text-xs font-mono text-zinc-400">
									Chỉnh sửa trực tiếp .plan/{plan.slug}.md (Lưu xong sẽ tự động chạy lại Schema Linter)
								</span>
								<button
									type="button"
									disabled={saving || externalEditLocked}
									onClick={handleSaveRaw}
									className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition"
								>
									<Save className="w-3.5 h-3.5" />
									<span>{saving ? 'Đang lưu...' : 'Lưu thay đổi vào .md'}</span>
								</button>
							</div>
							<textarea
								disabled={saving || externalEditLocked}
								value={rawBuffer}
								onChange={(e) => setRawBuffer(e.target.value)}
								className={`w-full h-[68vh] p-4 rounded-xl border text-xs font-mono focus:outline-none focus:border-blue-500 leading-6 ${
									isLight
										? 'bg-zinc-50 border-zinc-200 text-zinc-900'
										: 'bg-[#09090b] border-zinc-800 text-zinc-200'
								}`}
							/>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
