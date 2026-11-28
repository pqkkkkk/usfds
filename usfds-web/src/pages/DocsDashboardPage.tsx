import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
	ArrowLeft,
	LayoutDashboard,
	FileCheck2,
	Bug,
	BookOpen,
	Search,
	ShieldCheck,
	AlertTriangle,
	RefreshCw,
	GitMerge,
	Edit3,
	Save,
	Sun,
	Moon,
	FileText,
	ArrowUpRight,
	PanelLeftClose,
	PanelLeftOpen,
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useDocsDashboard } from '@/hooks/useDocsDashboard';
import { PlanReviewView } from '@/components/modules/docs_dashboard/PlanReviewView';
import { ArchitectureReviewView } from '@/components/modules/docs_dashboard/ArchitectureReviewView';
import { ContextInspectorPane } from '@/components/modules/docs_dashboard/ContextInspectorPane';
import {
	RichDocRenderer,
	InlineSmartText,
	cleanMarkdownPlain,
	formatShortFileRef,
	splitStatusAndNote,
} from '@/components/modules/docs_dashboard/RichDocRenderer';

export const DocsDashboardPage: React.FC = () => {
	const navigate = useNavigate();
	const { isLight, toggleTheme } = useTheme();
	const {
		overview, loading, error, fetchOverview, handlePlanUpdated, refreshVersion,
		selectedSpecPath, setSelectedSpecPath, specContent, setSpecContent,
		isEditingSpec, setIsEditingSpec, savingSpec, specError, specLoading, specDirty, setSpecDirty,
		handleSaveSpec, activeSection, selectedPlanSlug, inspectorTarget, setInspectorTarget,
		planDirty, setPlanDirty, inspectorDirty, setInspectorDirty, confirmDiscard, selectSection,
		planSaving, setPlanSaving, inspectorSaving, setInspectorSaving,
		issueSearch, setIssueSearch, priorityFilter, setPriorityFilter, statusFilter, setStatusFilter,
		areaFilter, setAreaFilter, showLegacyPlans, setShowLegacyPlans, isPlanSidebarCollapsed,
		setIsPlanSidebarCollapsed, handleSelectIssue, handleSelectFileRef, handleSelectPlan,
		selectedPlan, allAreas, filteredIssues, sidebarPlans, boardPlans, schemaWarningCount,
		selectedArchitectureId, openArchitectureDiagram,
	} = useDocsDashboard();

	// True-Black (Dark) vs Clean Paper (Light) surfaces scoped to Docs Dashboard
	const rootBg = isLight
		? 'bg-[#f8fafc] text-zinc-900'
		: 'bg-[#09090b] text-zinc-100';
	const topbarBg = isLight
		? 'bg-white border-zinc-200'
		: 'bg-[#0c0c0e] border-zinc-800/90';
	const sidebarBg = isLight
		? 'bg-white border-zinc-200'
		: 'bg-[#0c0c0e] border-zinc-800/90';
	const cardBg = isLight
		? 'bg-white border-zinc-200/90 shadow-sm'
		: 'bg-[#121215] border-zinc-800/90';

	return (
		<div
			className={`h-screen w-screen overflow-hidden flex flex-col font-sans ${rootBg}`}
		>
			{/* Single Primary Navigation Topbar */}
			<header
				className={`min-h-[56px] border-b px-5 py-2 flex flex-wrap items-center justify-between gap-2 shrink-0 ${topbarBg}`}
			>
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={() => { if (confirmDiscard(planDirty || specDirty || inspectorDirty)) navigate('/projects'); }}
						className={`px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
							isLight
								? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
								: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-300'
						}`}
						title="Quay lại ứng dụng USFDS"
					>
						<ArrowLeft className="w-3.5 h-3.5" />
						<span>USFDS App</span>
					</button>

					<div
						className={`h-5 w-px ${isLight ? 'bg-zinc-200' : 'bg-zinc-800'}`}
					/>

					<div className="flex items-center gap-2.5">
						<span className="font-mono font-bold text-sm tracking-tight">
							DOCS & PLAN HUB
						</span>
						{schemaWarningCount === 0 ? (
							<span
								className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono border ${
									isLight
										? 'bg-emerald-50 text-emerald-700 border-emerald-200'
										: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
								}`}
							>
								<ShieldCheck className="w-3.5 h-3.5" />
								Schema OK
							</span>
						) : (
							<span
								className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono border ${
									isLight
										? 'bg-amber-50 text-amber-700 border-amber-200'
										: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
								}`}
							>
								<AlertTriangle className="w-3.5 h-3.5" />
								{schemaWarningCount} lưu ý cấu trúc
							</span>
						)}
					</div>
				</div>

				{/* 4 Independent Top-Level Tabs */}
				<div
					className={`order-last w-full xl:order-none xl:w-auto overflow-x-auto flex items-center gap-1 p-1 rounded-xl border [&>button]:shrink-0 [&>button]:whitespace-nowrap ${
						isLight
							? 'bg-zinc-100 border-zinc-200'
							: 'bg-[#141418] border-zinc-800'
					}`}
				>
					<button
						type="button"
						onClick={() => selectSection('board')}
						className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
							activeSection === 'board'
								? 'bg-blue-600 text-white font-semibold shadow-sm'
								: isLight
									? 'text-zinc-600 hover:text-zinc-900'
									: 'text-zinc-400 hover:text-zinc-100'
						}`}
					>
						<LayoutDashboard className="w-3.5 h-3.5" />
						<span>Task Board ({overview?.board.activeTaskRows.length || 0})</span>
					</button>

					<button
						type="button"
						onClick={() => selectSection('plan-detail')}
						className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
							activeSection === 'plan-detail'
								? 'bg-blue-600 text-white font-semibold shadow-sm'
								: isLight
									? 'text-zinc-600 hover:text-zinc-900'
									: 'text-zinc-400 hover:text-zinc-100'
						}`}
					>
						<FileCheck2 className="w-3.5 h-3.5" />
						<span>Plans (.plan/)</span>
					</button>

					<button
						type="button"
						onClick={() => selectSection('issues')}
						className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
							activeSection === 'issues'
								? 'bg-blue-600 text-white font-semibold shadow-sm'
								: isLight
									? 'text-zinc-600 hover:text-zinc-900'
									: 'text-zinc-400 hover:text-zinc-100'
						}`}
					>
						<Bug className="w-3.5 h-3.5" />
						<span>Issues ({overview?.issues.length || 0})</span>
					</button>

					<button
						type="button"
						onClick={() => selectSection('architecture')}
						className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
							activeSection === 'architecture'
								? 'bg-blue-600 text-white font-semibold shadow-sm'
								: isLight
									? 'text-zinc-600 hover:text-zinc-900'
									: 'text-zinc-400 hover:text-zinc-100'
						}`}
					>
						<GitMerge className="w-3.5 h-3.5" />
						<span>Kiến trúc</span>
					</button>

					<button
						type="button"
						onClick={() => selectSection('specs')}
						className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
							activeSection === 'specs'
								? 'bg-blue-600 text-white font-semibold shadow-sm'
								: isLight
									? 'text-zinc-600 hover:text-zinc-900'
									: 'text-zinc-400 hover:text-zinc-100'
						}`}
					>
						<BookOpen className="w-3.5 h-3.5" />
						<span>Đặc tả & Kiến trúc</span>
					</button>
				</div>

				{/* Right Controls: Theme Toggle + Reload */}
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={toggleTheme}
						className={`px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
							isLight
								? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
								: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-300'
						}`}
						title={
							isLight
								? 'Chuyển sang nền Đen (Dark)'
								: 'Chuyển sang nền Sáng (Light)'
						}
					>
						{isLight ? (
							<>
								<Moon className="w-3.5 h-3.5" />
								<span>Dark</span>
							</>
						) : (
							<>
								<Sun className="w-3.5 h-3.5 text-amber-400" />
								<span>Light</span>
							</>
						)}
					</button>

					<button
						type="button"
						onClick={() => { if (confirmDiscard(planDirty || specDirty || inspectorDirty)) void fetchOverview(); }}
						className={`px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
							isLight
								? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
								: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-300'
						}`}
						title="Đọc lại toàn bộ file Markdown từ đĩa"
					>
						<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
						<span>Reload</span>
					</button>
				</div>
			</header>

			{/* Main Body: Each Topbar section owns its own layout below */}
			<div className="flex-1 flex overflow-hidden">
				{/* Center Viewport */}
				<main className="flex-1 flex overflow-hidden">
					{error && (
						<div className="m-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400">
							{error}
						</div>
					)}

					{activeSection === 'architecture' && (
						<ArchitectureReviewView isLight={isLight} onSelectFileRef={handleSelectFileRef} initialDiagramId={selectedArchitectureId} />
					)}

					{/* =========================================================
					    SECTION 1: TASK BOARD (NO LEFT SIDEBAR, ONLY TASKS)
					   ========================================================= */}
					{activeSection === 'board' && overview && (
						<div className="flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">
							<div className="max-w-5xl mx-auto space-y-8">
								<div>
									<h1 className="text-2xl font-semibold">Tổng quan công việc</h1>
									<p className={`mt-2 text-sm ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>Theo dõi task, issue và mở plan để review.</p>
								</div>
								{/* Summary Stat Cards */}
								<div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
									<div className={`p-5 rounded-2xl border ${cardBg}`}>
										<div
											className={`text-[11px] font-mono uppercase ${
												isLight ? 'text-zinc-500' : 'text-zinc-400'
											}`}
										>
											Tổng số Tasks (BOARD.md)
										</div>
										<div className="text-2xl font-bold mt-1.5 font-mono">
											{overview.board.activeTaskRows.length}
										</div>
									</div>

									<div className={`p-5 rounded-2xl border ${cardBg}`}>
										<div className="text-[11px] font-mono uppercase text-emerald-500">
											Tasks đã hoàn thành
										</div>
										<div className="text-2xl font-bold text-emerald-400 mt-1.5 font-mono">
											{
												overview.board.activeTaskRows.filter((r) =>
													(r[2] || '').toLowerCase().includes('done')
												).length
											}
											<span
												className={`text-xs font-normal ml-1.5 ${
													isLight ? 'text-zinc-500' : 'text-zinc-500'
												}`}
											>
												/ {overview.board.activeTaskRows.length}
											</span>
										</div>
									</div>

									<div className={`p-5 rounded-2xl border ${cardBg}`}>
										<div className="text-[11px] font-mono uppercase text-amber-500">
											Issues đang mở
										</div>
										<div className="text-2xl font-bold text-amber-400 mt-1.5 font-mono">
											{
												overview.issues.filter(
													(i) =>
														!i.status.toLowerCase().startsWith('resolved')
												).length
											}
											<span
												className={`text-xs font-normal ml-1.5 ${
													isLight ? 'text-zinc-500' : 'text-zinc-500'
												}`}
											>
												/ {overview.issues.length}
											</span>
										</div>
									</div>

									<div className={`p-5 rounded-2xl border ${cardBg}`}>
										<div className="text-[11px] font-mono uppercase text-rose-500">
											P0 / P1 Cần ưu tiên
										</div>
										<div className="text-2xl font-bold text-rose-400 mt-1.5 font-mono">
											{
												overview.issues.filter(
													(i) =>
														(i.priority === 'P0' || i.priority === 'P1') &&
														!i.status.toLowerCase().startsWith('resolved')
												).length
											}
										</div>
									</div>
								</div>

								{/* Tasks Table from .plan/BOARD.md */}
								<section className={`rounded-2xl border overflow-hidden ${cardBg}`}>
									<div
										className={`px-6 py-4 border-b flex items-center justify-between ${
											isLight ? 'border-zinc-200' : 'border-zinc-800/80'
										}`}
									>
										<div>
											<h2 className="text-base font-bold">
												Danh sách Tasks (.plan/BOARD.md)
											</h2>
											<p
												className={`text-xs mt-0.5 ${
													isLight ? 'text-zinc-500' : 'text-zinc-400'
												}`}
											>
												1 Task = 1 phiên làm việc của Agent = 1 file Plan. Bấm vào tên Task để mở trang Review Plan.
											</p>
										</div>
										<button
											type="button"
											onClick={() => handleSelectFileRef('.plan/BOARD.md')}
											className={`px-3 py-1.5 rounded-xl border text-xs font-mono flex items-center gap-1.5 transition ${
												isLight
													? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
													: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-300'
											}`}
										>
											<Edit3 className="w-3 h-3" />
											<span>Sửa BOARD.md</span>
										</button>
									</div>

									<div className="overflow-x-auto">
										<table className="w-full text-left border-collapse text-xs">
											<thead>
												<tr
													className={`border-b font-mono text-[11px] ${
														isLight
															? 'bg-zinc-50 border-zinc-200 text-zinc-500'
															: 'bg-zinc-900/70 border-zinc-800 text-zinc-400'
													}`}
												>
													<th className="px-5 py-3.5 w-52">Task (Plan file)</th>
													<th className="px-5 py-3.5 w-64">Issues</th>
													<th className="px-5 py-3.5 w-44">Status</th>
													<th className="px-5 py-3.5 w-24">Milestone</th>
													<th className="px-5 py-3.5 w-40">Depends on</th>
													<th className="px-5 py-3.5">Owned files</th>
												</tr>
											</thead>
											<tbody
												className={`divide-y ${
													isLight ? 'divide-zinc-100' : 'divide-zinc-800/70'
												}`}
											>
												{overview.board.activeTaskRows.map((row, rIdx) => {
													const taskCell = row[0] || '';
													const issuesCell = row[1] || '';
													const statusCell = row[2] || '';
													const milestoneCell = row[3] || '';
													const dependsCell = row[4] || '';
													const ownedCell = row[5] || '';

													const slugMatch = taskCell.match(/\[`?([^\]]+?)`?\]/);
													const slug = slugMatch
														? slugMatch[1].trim()
														: cleanMarkdownPlain(taskCell);
													const isDone = statusCell
														.toLowerCase()
														.includes('done');
													const rowIssues =
														issuesCell.match(/ISS-\d+/g) || [];
													const statusParsed =
														splitStatusAndNote(statusCell);

													return (
														<tr
															key={rIdx}
															className={`transition ${
																isLight
																	? 'hover:bg-zinc-50/80'
																	: 'hover:bg-zinc-900/40'
															}`}
														>
															<td className="px-5 py-4 align-top">
																<button
																	type="button"
																	onClick={() => handleSelectPlan(slug)}
																	className={`inline-flex items-center whitespace-nowrap gap-1.5 font-mono text-xs font-bold hover:underline ${
																		isLight
																			? 'text-blue-700'
																			: 'text-blue-400'
																	}`}
																>
																	<FileText className="w-3.5 h-3.5 shrink-0" />
																	<span>{slug}</span>
																	<ArrowUpRight className="w-3 h-3 opacity-60" />
																</button>
															</td>
															<td className="px-5 py-4 align-top">
																<div className="flex flex-wrap gap-1.5">
																	{rowIssues.map((issId) => (
																		<button
																			key={issId}
																			type="button"
																			onClick={() =>
																				handleSelectIssue(issId)
																			}
																			className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 rounded-md text-xs font-mono font-semibold transition border ${
																				isLight
																					? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
																					: 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
																			}`}
																		>
																			<Bug className="w-3 h-3 shrink-0" />
																			<span>{issId}</span>
																		</button>
																	))}
																</div>
															</td>
															<td className="px-5 py-4 align-top">
																<div className="flex flex-col items-start gap-1">
																	<span
																		className={`inline-flex items-center whitespace-nowrap px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold border ${
																			isDone
																				? isLight
																					? 'bg-emerald-50 text-emerald-700 border-emerald-200'
																					: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
																				: isLight
																					? 'bg-amber-50 text-amber-800 border-amber-200'
																					: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
																		}`}
																	>
																		{statusParsed.badge}
																	</span>
																	{statusParsed.note && (
																		<span
																			className={`text-[11px] font-mono leading-snug ${
																				isLight
																					? 'text-zinc-500'
																					: 'text-zinc-400'
																			}`}
																		>
																			{statusParsed.note}
																		</span>
																	)}
																</div>
															</td>
															<td className="px-5 py-4 font-mono align-top whitespace-nowrap">
																{milestoneCell}
															</td>
															<td className="px-5 py-4 font-mono align-top">
																<InlineSmartText
																	text={dependsCell}
																	isLight={isLight}
																	onSelectIssue={handleSelectIssue}
																	onSelectFileRef={handleSelectFileRef}
																	onSelectPlan={handleSelectPlan}
																/>
															</td>
															<td className="px-5 py-4 align-top leading-7">
																<InlineSmartText
																	text={ownedCell}
																	isLight={isLight}
																	onSelectIssue={handleSelectIssue}
																	onSelectFileRef={handleSelectFileRef}
																	onSelectPlan={handleSelectPlan}
																/>
															</td>
														</tr>
													);
												})}
											</tbody>
										</table>
									</div>
								</section>

								{/* Visual Task Cards corresponding to the Tasks on BOARD.md */}
								<section className="space-y-4">
									<h2 className="text-base font-bold">
										Tóm tắt nhanh các Task trên Board
									</h2>
									<div className="grid grid-cols-1 md:grid-cols-2 gap-5">
										{boardPlans.map((p) => {
											const totalItems = p.milestones.reduce(
												(acc, m) => acc + m.items.length,
												0
											);
											const doneItems = p.milestones.reduce(
												(acc, m) =>
													acc + m.items.filter((i) => i.checked).length,
												0
											);
											const isDone = p.status.toLowerCase().includes('done');
											return (
												<div
													key={p.slug}
													onClick={() => handleSelectPlan(p.slug)}
													className={`cursor-pointer p-5 rounded-2xl border transition flex flex-col justify-between gap-4 ${cardBg} ${
														isLight
															? 'hover:border-blue-400 hover:shadow-md'
															: 'hover:border-zinc-600 hover:bg-[#16161a]'
													}`}
												>
													<div className="space-y-2.5">
														<div className="flex items-center justify-between gap-2">
															<span className="font-mono text-xs font-bold text-blue-400 flex items-center gap-1.5">
																<FileText className="w-3.5 h-3.5" />
																{p.slug}
															</span>
															<span
																className={`px-2.5 py-0.5 rounded-md text-[11px] font-mono border ${
																	isDone
																		? isLight
																			? 'bg-emerald-50 text-emerald-700 border-emerald-200'
																			: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
																		: isLight
																			? 'bg-zinc-100 text-zinc-700 border-zinc-200'
																			: 'bg-zinc-800 text-zinc-300 border-zinc-700'
																}`}
															>
																{cleanMarkdownPlain(p.status.split('—')[0])}
															</span>
														</div>

														<h3 className="text-sm font-bold leading-relaxed">
															{cleanMarkdownPlain(p.title)}
														</h3>

														{p.goal && (
															<p
																className={`text-xs line-clamp-2 leading-6 ${
																	isLight ? 'text-zinc-600' : 'text-zinc-400'
																}`}
															>
																{cleanMarkdownPlain(p.goal)}
															</p>
														)}
													</div>

													<div
														className={`space-y-2.5 pt-3 border-t ${
															isLight ? 'border-zinc-100' : 'border-zinc-800/80'
														}`}
													>
														<div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
															<div className="flex flex-wrap items-center gap-1.5">
																{p.issues.map((iss) => (
																	<span
																		key={iss}
																		className={`px-2 py-0.5 rounded text-[10px] font-bold ${
																			isLight
																				? 'bg-amber-50 text-amber-800 border border-amber-200'
																				: 'bg-amber-500/15 text-amber-300'
																		}`}
																	>
																		{iss}
																	</span>
																))}
															</div>
															{p.conflictVerdict && (
																<span className="text-emerald-400 flex items-center gap-1 text-[11px]">
																	<GitMerge className="w-3 h-3" />
																	{cleanMarkdownPlain(
																		p.conflictVerdict.split('(')[0]
																	)}
																</span>
															)}
														</div>

														<div
															className={`flex items-center justify-between text-[11px] font-mono ${
																isLight ? 'text-zinc-500' : 'text-zinc-400'
															}`}
														>
															<span>
																{p.acceptanceTests.length} acceptance tests •{' '}
																{p.hotspots.length} hotspots
															</span>
															{totalItems > 0 && (
																<span>
																	Checklist: {doneItems}/{totalItems}
																</span>
															)}
														</div>
													</div>
												</div>
											);
										})}
									</div>
								</section>
							</div>
						</div>
					)}

					{/* =========================================================
					    SECTION 2: PLANS (WITH DEDICATED PLAN LIST SIDEBAR)
					   ========================================================= */}
					{activeSection === 'plan-detail' && (
						<div className="flex-1 flex flex-col md:flex-row overflow-hidden">
							{/* Dedicated Left Sidebar ONLY for Plans section */}
							{isPlanSidebarCollapsed ? (
								<div
									className={`w-10 shrink-0 border-r flex flex-col items-center pt-3 ${sidebarBg}`}
								>
									<button
										type="button"
										onClick={() => setIsPlanSidebarCollapsed(false)}
										title="Mở danh sách Plan"
										aria-label="Mở danh sách Plan"
										className={`p-1.5 rounded-lg border transition ${
											isLight
												? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-600'
												: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-400 hover:text-zinc-200'
										}`}
									>
										<PanelLeftOpen className="w-4 h-4" />
									</button>
								</div>
							) : (
								<aside
									className={`w-full max-h-28 md:w-64 md:max-h-none shrink-0 border-b md:border-b-0 md:border-r flex flex-col overflow-hidden ${sidebarBg}`}
								>
									<div
										className={`px-4 py-3.5 border-b flex items-center justify-between gap-2 ${
											isLight ? 'border-zinc-200' : 'border-zinc-800/80'
										}`}
									>
										<span
											className={`text-[11px] font-mono uppercase font-semibold truncate ${
												isLight ? 'text-zinc-500' : 'text-zinc-400'
											}`}
										>
											Danh sách Plans ({sidebarPlans.length})
										</span>
										<div className="flex items-center gap-1.5 shrink-0">
											<button
												type="button"
												onClick={() => setShowLegacyPlans(!showLegacyPlans)}
												className="text-[11px] font-mono text-blue-500 hover:underline whitespace-nowrap"
											>
												{showLegacyPlans ? 'Ẩn bản cũ' : '+Hiện bản cũ'}
											</button>
											<button
												type="button"
												onClick={() => setIsPlanSidebarCollapsed(true)}
												title="Thu gọn danh sách Plan"
												aria-label="Thu gọn danh sách Plan"
												className={`p-1 rounded-lg border transition ${
													isLight
														? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-600'
														: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-400 hover:text-zinc-200'
												}`}
											>
												<PanelLeftClose className="w-3.5 h-3.5" />
											</button>
										</div>
									</div>

									<div
										className={`flex-1 overflow-y-auto divide-y ${
											isLight ? 'divide-zinc-100' : 'divide-zinc-800/50'
										}`}
									>
										{sidebarPlans.map((p) => {
											const isSelected = p.slug === selectedPlanSlug;
											const isDone = p.status.toLowerCase().includes('done');
											const isApproved = p.status
												.toLowerCase()
												.includes('approved');
											return (
												<button
													key={p.slug}
													type="button"
													onClick={() => handleSelectPlan(p.slug)}
													className={`w-full min-w-0 text-left px-4 py-3.5 transition flex flex-col gap-1.5 ${
														isSelected
															? isLight
																? 'bg-blue-50/80 border-l-2 border-blue-600'
																: 'bg-zinc-900 border-l-2 border-blue-400'
															: isLight
																? 'hover:bg-zinc-50'
																: 'hover:bg-zinc-900/50'
													}`}
												>
													<div className="flex items-center justify-between gap-1.5 w-full min-w-0">
														<span
															className={`font-mono text-xs font-bold truncate ${
																isLight ? 'text-zinc-900' : 'text-zinc-100'
															}`}
														>
															{p.slug}
														</span>
														{p.validation.status === 'warning' && (
															<span
																className="shrink-0"
																title={p.validation.messages.join(', ')}
															>
																<AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
															</span>
														)}
													</div>
													<div
														className={`text-xs line-clamp-1 leading-snug ${
															isLight ? 'text-zinc-500' : 'text-zinc-400'
														}`}
													>
														{cleanMarkdownPlain(p.title)}
													</div>
													<div className="flex flex-wrap items-center gap-1.5 pt-0.5">
														<span
															className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
																isDone
																	? isLight
																		? 'bg-emerald-50 text-emerald-700 border-emerald-200'
																		: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
																	: isApproved
																		? isLight
																			? 'bg-blue-50 text-blue-700 border-blue-200'
																			: 'bg-blue-500/15 text-blue-300 border-blue-500/30'
																		: isLight
																			? 'bg-zinc-100 text-zinc-600 border-zinc-200'
																			: 'bg-zinc-800/80 text-zinc-400 border-zinc-700'
															}`}
														>
															{cleanMarkdownPlain(p.status.split('—')[0])}
														</span>
														{p.issues.slice(0, 3).map((iss) => (
															<span
																key={iss}
																className={`px-2 py-0.5 rounded text-[10px] font-mono ${
																	isLight
																		? 'bg-amber-50 text-amber-800 border border-amber-200'
																		: 'bg-amber-500/15 text-amber-300'
																}`}
															>
																{iss}
															</span>
														))}
														{p.issues.length > 3 && (
															<span className="text-[10px] font-mono text-zinc-500">
																+{p.issues.length - 3}
															</span>
														)}
													</div>
												</button>
											);
										})}
									</div>
								</aside>
							)}

							{/* Plan Review Workbench */}
							<div className="flex-1 min-w-0 min-h-0 overflow-hidden">
								{selectedPlan && (
									<PlanReviewView
										key={selectedPlan.slug}
										plan={selectedPlan}
										isLight={isLight}
										wideLayout={isPlanSidebarCollapsed}
										onSelectIssue={handleSelectIssue}
										onSelectFileRef={handleSelectFileRef}
										onSelectPlan={handleSelectPlan}
										onPlanUpdated={handlePlanUpdated}
										onRefreshOverview={fetchOverview}
										onDirtyChange={setPlanDirty}
										onSavingChange={setPlanSaving}
										externalEditLocked={inspectorDirty || inspectorSaving || savingSpec || planSaving}
										inspectorSelection={inspectorTarget}
										onSelectDiagram={openArchitectureDiagram}
									/>
								)}
								{overview && !selectedPlan && (
									<p className="m-8 text-sm text-zinc-500">Chọn một plan để bắt đầu review.</p>
								)}
							</div>
						</div>
					)}

					{/* =========================================================
					    SECTION 3: ISSUES EXPLORER (NO LEFT SIDEBAR)
					   ========================================================= */}
					{activeSection === 'issues' && overview && (
						<div className="flex-1 flex flex-col overflow-hidden">
							<div className={`px-4 pt-5 md:px-8 ${topbarBg}`}>
								<div className="max-w-5xl mx-auto">
									<h1 className="text-xl font-semibold">Danh sách vấn đề</h1>
									<p className={`mt-1 text-sm ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>
										Tìm vấn đề, xem nguồn và plan phụ trách.
									</p>
								</div>
							</div>
							{/* Filter Bar */}
							<div
								className={`px-8 py-4 border-b flex flex-wrap items-center justify-between gap-3 shrink-0 ${topbarBg}`}
							>
								<div className="max-w-5xl w-full mx-auto flex flex-wrap items-center justify-between gap-3">
									<div
										className={`flex items-center gap-2 flex-1 max-w-md px-3.5 py-2 rounded-xl border ${
											isLight
												? 'bg-zinc-50 border-zinc-200'
												: 'bg-[#121215] border-zinc-800'
										}`}
									>
										<Search className="w-4 h-4 text-zinc-400" />
										<input
											type="text"
											value={issueSearch}
											onChange={(e) => setIssueSearch(e.target.value)}
											placeholder="Tìm theo ISS-NNN, tiêu đề, tên file code..."
											className="w-full bg-transparent text-xs focus:outline-none"
										/>
									</div>

									<div className="flex flex-wrap items-center gap-2 text-xs font-mono">
										{/* Priority filter */}
										<div
											className={`flex items-center gap-1 p-1 rounded-xl border ${
												isLight
													? 'bg-zinc-100 border-zinc-200'
													: 'bg-[#121215] border-zinc-800'
											}`}
										>
											{['ALL', 'P0', 'P1', 'P2', 'P3'].map((pri) => (
												<button
													key={pri}
													type="button"
													onClick={() => setPriorityFilter(pri)}
													className={`px-2.5 py-1 rounded-lg transition ${
														priorityFilter === pri
															? 'bg-blue-600 text-white font-semibold'
															: isLight
																? 'text-zinc-600 hover:text-zinc-900'
																: 'text-zinc-400 hover:text-zinc-200'
													}`}
												>
													{pri}
												</button>
											))}
										</div>

										{/* Status filter */}
										<div
											className={`flex items-center gap-1 p-1 rounded-xl border ${
												isLight
													? 'bg-zinc-100 border-zinc-200'
													: 'bg-[#121215] border-zinc-800'
											}`}
										>
											{[
												{ id: 'ALL', label: 'Tất cả' },
												{ id: 'OPEN', label: 'Open' },
												{ id: 'NEEDS_SPEC', label: 'Needs Spec' },
												{ id: 'PLANNED', label: 'Planned' },
												{ id: 'RESOLVED', label: 'Resolved' },
											].map((st) => (
												<button
													key={st.id}
													type="button"
													onClick={() => setStatusFilter(st.id)}
													className={`px-2.5 py-1 rounded-lg transition ${
														statusFilter === st.id
															? 'bg-blue-600 text-white font-semibold'
															: isLight
																? 'text-zinc-600 hover:text-zinc-900'
																: 'text-zinc-400 hover:text-zinc-200'
													}`}
												>
													{st.label}
												</button>
											))}
										</div>

										{/* Area select */}
										<select
											value={areaFilter}
											onChange={(e) => setAreaFilter(e.target.value)}
											className={`px-3 py-2 rounded-xl border text-xs ${
												isLight
													? 'bg-white border-zinc-200 text-zinc-800'
													: 'bg-[#121215] border-zinc-800 text-zinc-200'
											}`}
										>
											<option value="ALL">Mọi Area</option>
											{allAreas.map((a) => (
												<option key={a} value={a}>
													Area: {a}
												</option>
											))}
										</select>
									</div>
								</div>
							</div>

							{/* Issues Table inside centered container */}
							<div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
								<div className="max-w-5xl mx-auto space-y-4">
									{overview.issueLinterWarnings.length > 0 && (
										<div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-400 space-y-1">
											<div className="font-bold flex items-center gap-1.5">
												<AlertTriangle className="w-4 h-4" />
												<span>
													Phát hiện lệch dữ liệu giữa docs/issues/README.md và file ngày:
												</span>
											</div>
											{overview.issueLinterWarnings.map((w, i) => (
												<div key={i} className="font-mono text-[11px] pl-5">
													• {w}
												</div>
											))}
										</div>
									)}

									<div className={`rounded-2xl border overflow-hidden ${cardBg}`}>
										<table className="w-full text-left border-collapse text-xs">
											<thead>
												<tr
													className={`border-b font-mono text-[11px] ${
														isLight
															? 'bg-zinc-50 border-zinc-200 text-zinc-500'
															: 'bg-zinc-900/80 border-zinc-800 text-zinc-400'
													}`}
												>
													<th className="px-4 py-3.5 w-24">ID</th>
													<th className="px-4 py-3.5 w-16">Pri</th>
													<th className="px-4 py-3.5">Tiêu đề & File liên quan</th>
													<th className="px-4 py-3.5 w-44">Area</th>
													<th className="px-4 py-3.5 w-40">Status</th>
													<th className="px-4 py-3.5 w-40">Plan</th>
												</tr>
											</thead>
											<tbody
												className={`divide-y ${
													isLight ? 'divide-zinc-100' : 'divide-zinc-800/70'
												}`}
											>
												{filteredIssues.map((iss) => {
													const isResolved = iss.status
														.toLowerCase()
														.startsWith('resolved');
													return (
														<tr
															key={iss.id}
															onClick={() => handleSelectIssue(iss.id)}
															className={`cursor-pointer transition ${
																isLight
																	? 'hover:bg-zinc-50'
																	: 'hover:bg-zinc-900/60'
															}`}
														>
															<td className="px-4 py-3.5 font-mono font-bold text-amber-400 align-top">
																<div className="flex items-center gap-1.5">
																	<span>{iss.id}</span>
																	{iss.syncWarning && (
																		<span title={iss.syncWarning}>
																			<AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
																		</span>
																	)}
																</div>
															</td>
															<td className="px-4 py-3.5 font-mono align-top">
																<span
																	className={`px-2 py-0.5 rounded-md text-[11px] font-bold border ${
																		iss.priority === 'P0'
																			? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
																			: iss.priority === 'P1'
																				? 'bg-orange-500/20 text-orange-400 border-orange-500/40'
																				: isLight
																					? 'bg-zinc-100 text-zinc-700 border-zinc-200'
																					: 'bg-zinc-800 text-zinc-300 border-zinc-700'
																	}`}
																>
																	{iss.priority}
																</span>
															</td>
															<td className="px-4 py-3.5 align-top space-y-1.5">
																<div
																	className={`font-medium text-[13px] leading-snug ${
																		isResolved
																			? 'text-zinc-500 line-through'
																			: isLight
																				? 'text-zinc-900'
																				: 'text-zinc-100'
																	}`}
																>
																	{cleanMarkdownPlain(iss.title)}
																</div>
																{iss.codeRefs.length > 0 && (
																	<div className="flex flex-wrap gap-1.5 pt-0.5">
																		{iss.codeRefs.slice(0, 3).map((ref) => {
																			const { shortLabel } =
																				formatShortFileRef(ref);
																			return (
																				<span
																					key={ref}
																					className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
																						isLight
																							? 'bg-sky-50 text-sky-800 border-sky-200'
																							: 'bg-zinc-900 text-sky-300 border-zinc-800'
																					}`}
																				>
																					{shortLabel}
																				</span>
																			);
																		})}
																	</div>
																)}
															</td>
															<td className="px-4 py-3.5 align-top">
																<div className="flex flex-wrap gap-1.5">
																	{iss.area.map((a) => (
																		<span
																			key={a}
																			className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
																				isLight
																					? 'bg-zinc-100 border-zinc-200 text-zinc-700'
																					: 'bg-zinc-900 border-zinc-800 text-zinc-300'
																			}`}
																		>
																			{a}
																		</span>
																	))}
																</div>
															</td>
															<td className="px-4 py-3.5 font-mono align-top">
																{(() => {
																	const parsed = splitStatusAndNote(iss.status);
																	return (
																		<div className="flex flex-col items-start gap-1">
																			<span
																				className={`inline-flex items-center whitespace-nowrap px-2.5 py-0.5 rounded-md text-[11px] font-semibold border ${
																					isResolved
																						? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
																						: iss.status
																									.toLowerCase()
																									.includes('needs spec')
																							? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
																							: 'bg-amber-500/15 text-amber-400 border-amber-500/30'
																				}`}
																			>
																				{parsed.badge}
																			</span>
																			{parsed.note && (
																				<span
																					className={`text-[10px] leading-snug ${
																						isLight
																							? 'text-zinc-500'
																							: 'text-zinc-400'
																					}`}
																				>
																					{parsed.note}
																				</span>
																			)}
																		</div>
																	);
																})()}
															</td>
															<td
																className="px-4 py-3.5 font-mono align-top"
																onClick={(e) => e.stopPropagation()}
															>
																{iss.planRef ? (
																	<button
																		type="button"
																		onClick={() =>
																			handleSelectPlan(iss.planRef)
																		}
																		className="text-blue-400 hover:underline text-left font-medium"
																	>
																		{iss.planRef}
																	</button>
																) : (
																	<span className="text-zinc-500">—</span>
																)}
															</td>
														</tr>
													);
												})}
											</tbody>
										</table>
									</div>
								</div>
							</div>
						</div>
					)}

					{/* =========================================================
					    SECTION 4: SPECS & ARCHITECTURE DOCS
					   ========================================================= */}
					{activeSection === 'specs' && overview && (
						<div className="flex-1 flex flex-col md:flex-row overflow-hidden">
							<div
								className={`w-full max-h-44 md:w-72 md:max-h-none shrink-0 border-b md:border-b-0 md:border-r overflow-y-auto p-3.5 space-y-1.5 ${sidebarBg}`}
							>
								<div
									className={`text-[11px] font-mono uppercase px-2.5 py-1.5 font-semibold ${
										isLight ? 'text-zinc-500' : 'text-zinc-400'
									}`}
								>
									Tài liệu trong docs/ ({overview.docsFiles.length})
								</div>
								{overview.docsFiles.map((df) => (
									<button
										key={df.path}
										type="button"
										onClick={() => { if (df.path !== selectedSpecPath && confirmDiscard(specDirty)) { setSpecDirty(false); setSelectedSpecPath(df.path); } }}
										className={`w-full text-left px-3 py-2.5 rounded-xl text-xs font-mono transition flex flex-col gap-0.5 ${
											selectedSpecPath === df.path
												? isLight
													? 'bg-blue-50 text-blue-700 font-semibold'
													: 'bg-zinc-900 text-blue-400 font-semibold'
												: isLight
													? 'text-zinc-700 hover:bg-zinc-100'
													: 'text-zinc-300 hover:bg-zinc-900/50'
										}`}
									>
										<span className="truncate">{df.path.replace(/^docs\//, '')}</span>
										<span className="text-[10px] text-zinc-500">{df.category}</span>
									</button>
								))}
							</div>

							<div className="flex-1 min-h-0 overflow-y-auto px-4 py-6 md:px-8 md:py-8">
								<div className="max-w-4xl mx-auto space-y-5">
									<div
										className={`flex items-center justify-between px-5 py-3.5 rounded-2xl border ${cardBg}`}
									>
										<div className="min-w-0">
											<h1 className="text-base font-semibold">Tài liệu nguồn</h1>
											<div className="mt-1 truncate font-mono text-xs text-blue-400">{selectedSpecPath}</div>
										</div>
										<div className="flex items-center gap-2">
											{isEditingSpec && (
												<button
													type="button"
													disabled={savingSpec || planSaving || inspectorDirty || inspectorSaving}
													onClick={() => void handleSaveSpec()}
													className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5"
												>
													<Save className="w-3.5 h-3.5" />
													<span>{savingSpec ? 'Đang lưu...' : 'Lưu tài liệu'}</span>
												</button>
											)}
											<button
												type="button"
												disabled={savingSpec || planSaving || inspectorDirty || inspectorSaving || specLoading || (!!specError && !isEditingSpec)}
												onClick={() => setIsEditingSpec(!isEditingSpec)}
												className={`px-3.5 py-1.5 rounded-xl border text-xs flex items-center gap-1.5 ${
													isLight
														? 'bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
														: 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-200'
												}`}
											>
												<Edit3 className="w-3.5 h-3.5" />
												<span>{isEditingSpec ? 'Xem Preview' : 'Chỉnh sửa .md'}</span>
											</button>
										</div>
									</div>

									{specLoading ? <p role="status">Đang tải tài liệu...</p> : isEditingSpec ? (
										<textarea
											disabled={savingSpec || planSaving || inspectorDirty || inspectorSaving}
											value={specContent}
											onChange={(e) => { setSpecContent(e.target.value); setSpecDirty(true); }}
											className={`w-full h-[72vh] p-5 rounded-2xl border text-xs font-mono focus:outline-none focus:border-blue-500 leading-6 ${
												isLight
													? 'bg-white border-zinc-200 text-zinc-900'
													: 'bg-[#121215] border-zinc-800 text-zinc-200'
											}`}
										/>
									) : specError ? (
										<div role="alert" className="text-sm text-rose-500">
											<p>{specError}</p>
											<button type="button" className="mt-2 underline" onClick={() => { if (confirmDiscard(inspectorDirty)) void fetchOverview(); }}>Thử lại</button>
										</div>
									) : (
										<div className={`p-8 rounded-2xl border ${cardBg}`}>
											<RichDocRenderer
												markdown={specContent}
												sourcePath={selectedSpecPath}
												isLight={isLight}
												onSelectIssue={handleSelectIssue}
												onSelectFileRef={handleSelectFileRef}
												onSelectPlan={handleSelectPlan}
											/>
										</div>
									)}
									{isEditingSpec && specError && <div role="alert" className="text-sm text-rose-500">{specError}</div>}
									{(planSaving || inspectorDirty || inspectorSaving) && <p role="status" className="text-sm text-amber-600">Lưu hoặc bỏ bản nháp ở khung khác trước khi sửa tài liệu.</p>}
								</div>
							</div>
						</div>
					)}
				</main>

				{/* Right Context Split-Pane (Issues, Code Snippets, Linked Docs) */}
				<ContextInspectorPane
					target={inspectorTarget}
					issues={overview?.issues || []}
					isLight={isLight}
					onClose={() => setInspectorTarget(null)}
					onSelectIssue={handleSelectIssue}
					onSelectFileRef={handleSelectFileRef}
					onSelectPlan={handleSelectPlan}
					onRefreshOverview={fetchOverview}
					onDirtyChange={setInspectorDirty}
					onSavingChange={setInspectorSaving}
					externalEditLocked={planDirty || planSaving || specDirty || savingSpec}
					refreshVersion={refreshVersion}
				/>
			</div>
		</div>
	);
};

export default DocsDashboardPage;
