import React, { useEffect, useRef, useState } from 'react';
import {
	X,
	Bug,
	FileCode2,
	ExternalLink,
	AlertTriangle,
	FileText,
	Save,
	Edit3,
} from 'lucide-react';
import {
	docsDashboardApi,
	type ParsedIssue,
	type FileSnippetResponse,
} from '@/api/docsDashboardApi';
import {
	RichDocRenderer,
	cleanMarkdownPlain,
	formatShortFileRef,
} from './RichDocRenderer';

export type InspectorTarget =
	| { type: 'issue'; issueId: string }
	| { type: 'file'; fileRef: string }
	| null;

interface ContextInspectorPaneProps {
	target: InspectorTarget;
	issues: ParsedIssue[];
	isLight?: boolean;
	onClose: () => void;
	onSelectIssue: (issueId: string) => void;
	onSelectFileRef: (fileRef: string) => void;
	onSelectPlan: (slug: string) => void;
	onRefreshOverview: () => Promise<void>;
}

const ISSUE_STATUS_OPTIONS = [
	'Open',
	'Open — needs spec',
	'Planned',
	'In progress',
	`Resolved (${new Date().toISOString().slice(2, 10)})`,
	"Won't fix",
];

export const ContextInspectorPane: React.FC<ContextInspectorPaneProps> = ({
	target,
	issues,
	isLight = false,
	onClose,
	onSelectIssue,
	onSelectFileRef,
	onSelectPlan,
	onRefreshOverview,
}) => {
	const [fileData, setFileData] = useState<FileSnippetResponse | null>(null);
	const [fileLoading, setFileLoading] = useState(false);
	const [fileError, setFileError] = useState<string | null>(null);
	const [showFullFile, setShowFullFile] = useState(false);
	const [isEditingMd, setIsEditingMd] = useState(false);
	const [editBuffer, setEditBuffer] = useState('');
	const [saving, setSaving] = useState(false);
	const contentRef = useRef<HTMLDivElement>(null);
	const [anchorError, setAnchorError] = useState<string | null>(null);

	useEffect(() => {
		setIsEditingMd(false);
		setShowFullFile(false);
		setAnchorError(null);
		if (!target || target.type !== 'file') {
			setFileData(null);
			setFileError(null);
			return;
		}
		let cancelled = false;
		setFileLoading(true);
		setFileData(null);
		setFileError(null);
		const ref = target.fileRef;
		const fileRef = /#(?!L\d+(?:-L?\d+)?$)/.test(ref) ? ref.split('#', 1)[0] : ref;

		docsDashboardApi
			.getFile(fileRef)
			.then((data) => {
				if (!cancelled) {
					setFileData(data);
					setEditBuffer(data.content);
				}
			})
			.catch((err) => {
				if (!cancelled) {
					setFileError(err instanceof Error ? err.message : String(err));
				}
			})
			.finally(() => {
				if (!cancelled) {
					setFileLoading(false);
				}
			});

		return () => {
			cancelled = true;
		};
	}, [target]);

	useEffect(() => {
		if (!target || target.type !== 'file' || !fileData || fileLoading || isEditingMd) return;
		const fragment = target.fileRef.split('#')[1];
		if (!fragment || /^L\d+(?:-L?\d+)?$/.test(fragment)) return;
		const heading = Array.from(contentRef.current?.querySelectorAll<HTMLElement>('[data-doc-heading]') ?? [])
			.find((element) => element.dataset.docHeading === fragment);
		if (heading) {
			heading.scrollIntoView({ block: 'start' });
			setAnchorError(null);
		} else {
			setAnchorError(`Không tìm thấy mục #${fragment} trong ${fileData.path}.`);
		}
	}, [target, fileData, fileLoading, isEditingMd]);

	if (!target) {
		return null;
	}

	const panelSurface = isLight
		? 'bg-white border-zinc-200 text-zinc-900'
		: 'bg-[#0c0c0e] border-zinc-800/90 text-zinc-100';
	const headerSurface = isLight
		? 'bg-zinc-50 border-zinc-200'
		: 'bg-[#121215] border-zinc-800/90';
	const cardSurface = isLight
		? 'bg-zinc-50 border-zinc-200'
		: 'bg-[#141418] border-zinc-800';

	if (target.type === 'issue') {
		const issue = issues.find((iss) => iss.id === target.issueId);

		const handleStatusChange = async (newStatus: string) => {
			if (!issue) {
				return;
			}
			setSaving(true);
			try {
				await docsDashboardApi.updateIssueStatus(issue.id, newStatus);
				await onRefreshOverview();
			} finally {
				setSaving(false);
			}
		};

		return (
			<aside
				className={`fixed inset-0 z-40 w-full lg:static lg:w-[480px] xl:w-[540px] shrink-0 border-l flex flex-col h-full overflow-hidden shadow-2xl ${panelSurface}`}
			>
				{/* Header */}
				<div
					className={`px-5 py-3.5 border-b flex items-center justify-between gap-2 ${headerSurface}`}
				>
					<div className="flex items-center gap-2.5 min-w-0">
						<span
							className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-bold border ${
								isLight
									? 'bg-amber-50 text-amber-800 border-amber-300'
									: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
							}`}
						>
							<Bug className="w-3.5 h-3.5" />
							{target.issueId}
						</span>
						{issue && (
							<span
								className={`px-2 py-0.5 rounded-md text-xs font-mono font-bold border ${
									issue.priority === 'P0'
										? isLight
											? 'bg-rose-50 text-rose-700 border-rose-300'
											: 'bg-rose-500/20 text-rose-300 border-rose-500/40'
										: issue.priority === 'P1'
											? isLight
												? 'bg-orange-50 text-orange-700 border-orange-300'
												: 'bg-orange-500/20 text-orange-300 border-orange-500/40'
											: isLight
												? 'bg-zinc-100 text-zinc-700 border-zinc-300'
												: 'bg-zinc-800 text-zinc-300 border-zinc-700'
								}`}
							>
								{issue.priority}
							</span>
						)}
					</div>
					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng bảng ngữ cảnh"
						className={`p-1.5 rounded-lg transition ${
							isLight
								? 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-200/70'
								: 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
						}`}
						title="Đóng khung ngữ cảnh"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{/* Body */}
				<div className="flex-1 overflow-y-auto p-5 space-y-5">
					{!issue ? (
						<div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400">
							Không tìm thấy thông tin cho {target.issueId} trong docs/issues/.
						</div>
					) : (
						<>
							<div>
								<h3
									className={`text-base font-bold leading-relaxed ${
										isLight ? 'text-zinc-900' : 'text-zinc-100'
									}`}
								>
									{cleanMarkdownPlain(issue.title)}
								</h3>
								<div className="flex flex-wrap items-center gap-2 mt-2.5 text-xs font-mono">
									<span
										className={`px-2.5 py-0.5 rounded-md border ${
											isLight
												? 'bg-zinc-100 border-zinc-200 text-zinc-700'
												: 'bg-zinc-900 border-zinc-800 text-zinc-300'
										}`}
									>
										Loại: {issue.type}
									</span>
									{issue.area.map((a) => (
										<span
											key={a}
											className={`px-2.5 py-0.5 rounded-md border ${
												isLight
													? 'bg-blue-50 border-blue-200 text-blue-700'
													: 'bg-blue-500/10 border-blue-500/30 text-blue-300'
											}`}
										>
											{a}
										</span>
									))}
								</div>
							</div>

							{/* Sync Warning if README vs Dated File disagrees */}
							{issue.syncWarning && (
								<div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5 text-xs text-amber-400">
									<AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
									<div className="leading-relaxed">
										<div className="font-semibold">Cảnh báo đồng bộ Markdown:</div>
										<div>{issue.syncWarning}</div>
									</div>
								</div>
							)}

							{/* Quick Interactive Status Updater */}
							<div className={`p-4 rounded-xl border space-y-2.5 ${cardSurface}`}>
								<div className="flex items-center justify-between">
									<span
										className={`text-[11px] font-mono uppercase ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										Đổi trạng thái (Cập nhật cả README & {issue.datedFile.split('/').pop()})
									</span>
									{saving && (
										<span className="text-[11px] text-blue-400 font-mono">
											Đang lưu...
										</span>
									)}
								</div>
								<div className="flex flex-wrap gap-1.5">
									{ISSUE_STATUS_OPTIONS.map((opt) => {
										const active = issue.status
											.toLowerCase()
											.startsWith(opt.split(' ')[0].toLowerCase());
										return (
											<button
												key={opt}
												type="button"
												disabled={saving}
												onClick={() => handleStatusChange(opt)}
												className={`px-2.5 py-1 rounded-md text-xs font-mono transition border ${
													active
														? isLight
															? 'bg-emerald-600 text-white border-emerald-600 font-semibold'
															: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-semibold'
														: isLight
															? 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-100'
															: 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:bg-zinc-800'
												}`}
											>
												{opt}
											</button>
										);
									})}
								</div>
							</div>

							{/* Linked Plan & Source File */}
							<div
								className={`flex items-center justify-between gap-2 p-3.5 rounded-xl border text-xs ${cardSurface}`}
							>
								<div className="flex items-center gap-2">
									<span className={isLight ? 'text-zinc-500' : 'text-zinc-400'}>
										Plan phụ trách:
									</span>
									{issue.planRef ? (
										<button
											type="button"
											onClick={() => onSelectPlan(issue.planRef)}
											className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono font-medium transition border ${
												isLight
													? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
													: 'bg-blue-500/15 text-blue-300 border-blue-500/30 hover:bg-blue-500/25'
											}`}
										>
											<FileText className="w-3.5 h-3.5" />
											{issue.planRef}
										</button>
									) : (
										<span className="text-zinc-500 font-mono">Chưa gán (Backlog)</span>
									)}
								</div>
								{issue.datedFile && (
									<button
										type="button"
										onClick={() => onSelectFileRef(issue.datedFile)}
										className="text-xs font-mono text-sky-400 hover:underline"
									>
										Mở {issue.datedFile.split('/').pop()}
									</button>
								)}
							</div>

							{/* Full Issue Markdown Body */}
							<div className={`p-4 rounded-xl border ${cardSurface}`}>
								<div
									className={`text-[11px] font-mono uppercase mb-3 ${
										isLight ? 'text-zinc-500' : 'text-zinc-400'
									}`}
								>
									Nội dung chi tiết ({issue.datedFile.split('/').pop()})
								</div>
								<RichDocRenderer
									markdown={issue.bodyMarkdown}
									isLight={isLight}
									onSelectIssue={onSelectIssue}
									onSelectFileRef={onSelectFileRef}
									onSelectPlan={onSelectPlan}
								/>
							</div>

							{/* Extracted Code References */}
							{issue.codeRefs.length > 0 && (
								<div className="space-y-2">
									<div
										className={`text-[11px] font-mono uppercase ${
											isLight ? 'text-zinc-500' : 'text-zinc-400'
										}`}
									>
										File code liên quan ({issue.codeRefs.length})
									</div>
									<div className="flex flex-wrap gap-2">
										{issue.codeRefs.map((ref) => {
											const { shortLabel, pkgHint } = formatShortFileRef(ref);
											return (
												<button
													key={ref}
													type="button"
													onClick={() => onSelectFileRef(ref)}
													title={ref}
													className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono transition border ${
														isLight
															? 'bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100'
															: 'bg-zinc-900 text-sky-300 border-zinc-800 hover:border-sky-500/40'
													}`}
												>
													<FileCode2 className="w-3.5 h-3.5" />
													{pkgHint && (
														<span className="opacity-50">{pkgHint}/</span>
													)}
													<span>{shortLabel}</span>
												</button>
											);
										})}
									</div>
								</div>
							)}
						</>
					)}
				</div>
			</aside>
		);
	}

	// File or Code Snippet Inspector
	const isMarkdownFile = fileData?.path.endsWith('.md');

	const handleSaveMd = async () => {
		if (!fileData) {
			return;
		}
		setSaving(true);
		try {
			await docsDashboardApi.saveFile(fileData.path, editBuffer);
			setFileData({
				...fileData,
				content: editBuffer,
				snippet: editBuffer,
			});
			setIsEditingMd(false);
			await onRefreshOverview();
		} finally {
			setSaving(false);
		}
	};

	const vscodeHref = fileData
		? `vscode://file/${fileData.absPath}${
				fileData.highlightStart ? `:${fileData.highlightStart}` : ''
			}`
		: '#';

	const { shortLabel } = formatShortFileRef(target.fileRef);

	return (
		<aside
			className={`fixed inset-0 z-40 w-full lg:static lg:w-[500px] xl:w-[600px] shrink-0 border-l flex flex-col h-full overflow-hidden shadow-2xl ${panelSurface}`}
		>
			{/* Header */}
			<div
				className={`px-5 py-3.5 border-b flex items-center justify-between gap-2 ${headerSurface}`}
			>
				<div className="flex items-center gap-2 min-w-0">
					<FileCode2 className="w-4 h-4 text-sky-400 shrink-0" />
					<div className="truncate">
						<div className="text-xs font-mono font-bold truncate" title={target.fileRef}>
							{shortLabel}
						</div>
						<div
							className={`text-[10px] font-mono truncate ${
								isLight ? 'text-zinc-500' : 'text-zinc-400'
							}`}
						>
							{target.fileRef}
						</div>
					</div>
				</div>
				<div className="flex items-center gap-1.5 shrink-0">
					{fileData && isMarkdownFile && (
						<button
							type="button"
							onClick={() => setIsEditingMd(!isEditingMd)}
							className={`px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 border transition ${
								isEditingMd
									? 'bg-blue-600 text-white border-blue-600'
									: isLight
										? 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100'
										: 'bg-zinc-900 text-zinc-300 border-zinc-800 hover:bg-zinc-800'
							}`}
						>
							<Edit3 className="w-3 h-3" />
							<span>{isEditingMd ? 'Preview' : 'Sửa file'}</span>
						</button>
					)}
					{fileData && (
						<a
							href={vscodeHref}
							className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 transition ${
								isLight
									? 'bg-white hover:bg-zinc-100 text-sky-700 border-zinc-200'
									: 'bg-zinc-900 hover:bg-zinc-800 text-sky-300 border-zinc-800'
							}`}
							title="Mở trực tiếp tại dòng này trong VS Code / Antigravity"
						>
							<ExternalLink className="w-3 h-3" />
							<span>Mở IDE</span>
						</a>
					)}
					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng bảng ngữ cảnh"
						className={`p-1.5 rounded-lg transition ${
							isLight
								? 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-200/70'
								: 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
						}`}
					>
						<X className="w-4 h-4" />
					</button>
				</div>
			</div>

			{/* Content */}
			<div ref={contentRef} className="flex-1 overflow-y-auto p-5">
				{fileLoading && (
					<div className="text-xs font-mono text-zinc-400">Đang đọc file...</div>
				)}
				{fileError && (
					<div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 font-mono">
						{fileError}
					</div>
				)}
				{anchorError && <div role="alert" className="text-xs text-rose-400">{anchorError}</div>}
				{fileData && !fileLoading && (
					<div className="space-y-3">
						{isEditingMd ? (
							<div className="space-y-3">
								<div className="flex items-center justify-between">
									<span className="text-xs text-zinc-400 font-mono">
										Chỉnh sửa {fileData.path}
									</span>
									<button
										type="button"
										disabled={saving}
										onClick={handleSaveMd}
										className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition"
									>
										<Save className="w-3.5 h-3.5" />
										<span>{saving ? 'Đang lưu...' : 'Lưu vào đĩa'}</span>
									</button>
								</div>
								<textarea
									value={editBuffer}
									onChange={(e) => setEditBuffer(e.target.value)}
									className={`w-full h-[65vh] p-4 rounded-xl border text-xs font-mono focus:outline-none focus:border-blue-500 leading-6 ${
										isLight
											? 'bg-zinc-50 border-zinc-200 text-zinc-900'
											: 'bg-[#09090b] border-zinc-800 text-zinc-200'
									}`}
								/>
							</div>
						) : isMarkdownFile && !fileData.highlightStart ? (
							<div className={`p-4 rounded-xl border ${cardSurface}`}>
								<RichDocRenderer
									markdown={fileData.content}
									sourcePath={fileData.path}
									isLight={isLight}
									onSelectIssue={onSelectIssue}
									onSelectFileRef={onSelectFileRef}
									onSelectPlan={onSelectPlan}
								/>
							</div>
						) : (
							<>
								<div
									className={`flex items-center justify-between text-xs font-mono px-3.5 py-2 rounded-xl border ${cardSurface}`}
								>
									<span>
										{fileData.highlightStart
											? `Dòng ${fileData.highlightStart}${
													fileData.highlightEnd &&
													fileData.highlightEnd !== fileData.highlightStart
														? `–${fileData.highlightEnd}`
														: ''
												} / ${fileData.totalLines} dòng`
											: `Tổng ${fileData.totalLines} dòng`}
									</span>
									{fileData.highlightStart && (
										<button
											type="button"
											onClick={() => setShowFullFile(!showFullFile)}
											className="text-blue-400 hover:underline font-medium"
										>
											{showFullFile ? 'Thu gọn về đoạn trích' : 'Xem toàn bộ file'}
										</button>
									)}
								</div>

								<div
									className={`rounded-xl border overflow-x-auto ${
										isLight
											? 'bg-zinc-50 border-zinc-200'
											: 'bg-[#09090b] border-zinc-800'
									}`}
								>
									<table className="w-full border-collapse font-mono text-xs leading-6">
										<tbody>
											{(showFullFile
												? fileData.content.split(/\r?\n/)
												: fileData.snippet.split(/\r?\n/)
											).map((lineText, idx) => {
												const lineNum = showFullFile
													? idx + 1
													: fileData.sliceStart + idx;
												const isHighlighted =
													fileData.highlightStart !== null &&
													fileData.highlightEnd !== null &&
													lineNum >= fileData.highlightStart &&
													lineNum <= fileData.highlightEnd;
												return (
													<tr
														key={lineNum}
														className={
															isHighlighted
																? isLight
																	? 'bg-amber-100/80 border-l-2 border-amber-500'
																	: 'bg-blue-500/15 border-l-2 border-blue-400'
																: isLight
																	? 'hover:bg-zinc-100'
																	: 'hover:bg-zinc-900/60'
														}
													>
														<td
															className={`select-none px-3 py-0.5 text-right w-12 border-r ${
																isLight
																	? 'text-zinc-400 border-zinc-200'
																	: 'text-zinc-500 border-zinc-800'
															}`}
														>
															{lineNum}
														</td>
														<td
															className={`px-3.5 py-0.5 whitespace-pre ${
																isLight ? 'text-zinc-800' : 'text-zinc-200'
															}`}
														>
															{lineText || ' '}
														</td>
													</tr>
												);
											})}
										</tbody>
									</table>
								</div>
							</>
						)}
					</div>
				)}
			</div>
		</aside>
	);
};
