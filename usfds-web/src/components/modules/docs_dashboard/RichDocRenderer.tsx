import React from 'react';
import { FileCode2, Bug, FileText } from 'lucide-react';
import { MermaidDiagram } from './MermaidDiagram';

interface RichDocRendererProps {
	markdown: string;
	isLight?: boolean;
	onSelectIssue: (issueId: string) => void;
	onSelectFileRef: (fileRef: string) => void;
	onSelectPlan?: (slug: string) => void;
}

const FILE_PATH_PATTERN =
	/^(?:usfds-[a-z0-9_-]+\/|docs\/|\.plan\/|\.claude\/|scripts\/|deploy\/|database\/|[a-zA-Z0-9_/-]+\.(?:py|ts|tsx|md|sh|yml|json))/;

/** Strip markdown backticks and bold markers for plain-text titles/summaries */
export function cleanMarkdownPlain(raw: string): string {
	if (!raw) {
		return '';
	}
	return raw
		.replace(/`([^`]+)`/g, '$1')
		.replace(/\*\*([^*]+)\*\*/g, '$1')
		.replace(/<!--.*?-->/g, '')
		.trim();
}

/** Split a status string like "In progress (rotate key)" or "Planning (plan drafted...)" into a short badge + optional note */
export function splitStatusAndNote(rawStatus: string): {
	badge: string;
	note: string;
} {
	const cleaned = cleanMarkdownPlain(rawStatus);
	const dashParts = cleaned.split(/\s+—\s+/);
	const firstPart = dashParts[0].trim();
	const dashNote = dashParts.slice(1).join(' — ').trim();

	const parenMatch = firstPart.match(/^([^(]+)\(([^)]+)\)(.*)$/);
	if (parenMatch) {
		const main = parenMatch[1].trim();
		const inside = parenMatch[2].trim();
		const rest = parenMatch[3].trim();
		const combinedNote = [inside, rest, dashNote].filter(Boolean).join(' • ');
		return {
			badge: main || cleaned,
			note: combinedNote,
		};
	}
	return {
		badge: firstPart || cleaned,
		note: dashNote,
	};
}

/** Compact a long repo path like `usfds-core/src/usfds_core/domain/entities/system.py:10-15` into `system.py:10-15` */
export function formatShortFileRef(fullRef: string): {
	shortLabel: string;
	pkgHint: string;
} {
	const cleaned = fullRef
		.replace(/^file:\/\/\/[a-zA-Z]:\/.*?\/usfds\//, '')
		.replace(/^file:\/\/\/.*?\/usfds\//, '');
	const parts = cleaned.split('/');
	const lastPart = parts[parts.length - 1] || cleaned;
	const firstPart = parts.length > 1 ? parts[0] : '';
	return {
		shortLabel: lastPart,
		pkgHint: firstPart.startsWith('usfds-') ? firstPart.replace('usfds-', '') : firstPart,
	};
}

export const InlineSmartText: React.FC<{
	text: string;
	isLight?: boolean;
	onSelectIssue: (issueId: string) => void;
	onSelectFileRef: (fileRef: string) => void;
	onSelectPlan?: (slug: string) => void;
}> = ({ text, isLight = false, onSelectIssue, onSelectFileRef, onSelectPlan }) => {
	const cleanedText = text.replace(/<!--.*?-->/g, '');
	const tokenRegex =
		/(\[`?[^\]]+`?\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*|\bISS-\d+\b)/g;
	const parts = cleanedText.split(tokenRegex);

	return (
		<span className="leading-7">
			{parts.map((part, idx) => {
				if (!part) {
					return null;
				}

				// 1. Issue badge: ISS-NNN
				if (/^ISS-\d+$/.test(part)) {
					return (
						<button
							key={idx}
							type="button"
							onClick={() => onSelectIssue(part)}
							className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono font-semibold transition align-baseline border ${
								isLight
									? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
									: 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
							}`}
							title={`Xem chi tiết ${part}`}
						>
							<Bug className="w-3 h-3 shrink-0" />
							<span>{part}</span>
						</button>
					);
				}

				// 2. Markdown link: [label](href)
				const linkMatch = part.match(/^\[`?([^\]]+?)`?\]\(([^)]+)\)$/);
				if (linkMatch) {
					const label = linkMatch[1].replace(/`/g, '');
					const href = linkMatch[2];

					if (/^ISS-\d+$/.test(label)) {
						return (
							<button
								key={idx}
								type="button"
								onClick={() => onSelectIssue(label)}
								className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono font-semibold transition border ${
									isLight
										? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
										: 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
								}`}
							>
								<Bug className="w-3 h-3 shrink-0" />
								<span>{label}</span>
							</button>
						);
					}

					if (href.startsWith('http://') || href.startsWith('https://')) {
						return (
							<a
								key={idx}
								href={href}
								target="_blank"
								rel="noreferrer"
								className={`underline underline-offset-4 font-medium mx-0.5 ${
									isLight
										? 'text-blue-600 hover:text-blue-700'
										: 'text-blue-400 hover:text-blue-300'
								}`}
							>
								{label}
							</a>
						);
					}

					if (
						onSelectPlan &&
						(href.includes('.plan/') ||
							(!href.includes('/') &&
								href.endsWith('.md') &&
								!/^\d{2}-\d{2}-\d{4}/.test(href)))
					) {
						const slug = href
							.split('/')
							.pop()
							?.replace(/\.md$/, '');
						if (slug && slug !== 'README' && slug !== 'BOARD') {
							return (
								<button
									key={idx}
									type="button"
									onClick={() => onSelectPlan(slug)}
									className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono font-medium transition border ${
										isLight
											? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
											: 'bg-blue-500/15 text-blue-300 border-blue-500/30 hover:bg-blue-500/25'
									}`}
								>
									<FileText className="w-3 h-3 shrink-0" />
									<span>{label}</span>
								</button>
							);
						}
					}

					const { shortLabel } = formatShortFileRef(label);
					return (
						<button
							key={idx}
							type="button"
							onClick={() => onSelectFileRef(href)}
							className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono transition border ${
								isLight
									? 'bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100'
									: 'bg-sky-500/15 text-sky-300 border-sky-500/30 hover:bg-sky-500/25'
							}`}
							title={`Mở xem nhanh: ${href}`}
						>
							<FileCode2 className="w-3 h-3 shrink-0" />
							<span>{shortLabel}</span>
						</button>
					);
				}

				// 3. Inline code: `...`
				if (part.startsWith('`') && part.endsWith('`')) {
					const inner = part.slice(1, -1);
					if (/^ISS-\d+$/.test(inner)) {
						return (
							<button
								key={idx}
								type="button"
								onClick={() => onSelectIssue(inner)}
								className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono font-semibold transition border ${
									isLight
										? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
										: 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
								}`}
							>
								<Bug className="w-3 h-3 shrink-0" />
								<span>{inner}</span>
							</button>
						);
					}
					if (FILE_PATH_PATTERN.test(inner)) {
						const { shortLabel, pkgHint } = formatShortFileRef(inner);
						return (
							<button
								key={idx}
								type="button"
								onClick={() => onSelectFileRef(inner)}
								className={`inline-flex items-center whitespace-nowrap gap-1 px-2 py-0.5 my-0.5 mx-0.5 rounded-md text-xs font-mono transition border align-baseline ${
									isLight
										? 'bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100'
										: 'bg-zinc-800/90 text-sky-300 border-zinc-700 hover:border-sky-500/50 hover:bg-zinc-800'
								}`}
								title={`Click để xem code: ${inner}`}
							>
								<FileCode2 className="w-3 h-3 shrink-0 opacity-80" />
								{pkgHint && (
									<span className="opacity-55 text-[10px]">{pkgHint}/</span>
								)}
								<span className="font-medium">{shortLabel}</span>
							</button>
						);
					}
					return (
						<code
							key={idx}
							className={`inline-block px-1.5 py-0.5 my-0.5 mx-0.5 rounded font-mono text-xs leading-snug ${
								isLight
									? 'bg-zinc-100 text-zinc-800 border border-zinc-200/80'
									: 'bg-zinc-800/80 text-zinc-200 border border-zinc-700/70'
							}`}
						>
							{inner}
						</code>
					);
				}

				// 4. Bold: **...**
				if (part.startsWith('**') && part.endsWith('**')) {
					return (
						<strong
							key={idx}
							className={`font-semibold ${
								isLight ? 'text-zinc-900' : 'text-zinc-100'
							}`}
						>
							{part.slice(2, -2).replace(/`/g, '')}
						</strong>
					);
				}

				return <span key={idx}>{part}</span>;
			})}
		</span>
	);
};

export const RichDocRenderer: React.FC<RichDocRendererProps> = ({
	markdown,
	isLight = false,
	onSelectIssue,
	onSelectFileRef,
	onSelectPlan,
}) => {
	const lines = markdown.split(/\r?\n/);
	const elements: React.ReactNode[] = [];

	let i = 0;
	while (i < lines.length) {
		const line = lines[i];

		// Skip HTML comments
		if (line.trim().startsWith('<!--') && line.trim().endsWith('-->')) {
			i++;
			continue;
		}

		// Code block ```
		if (line.trim().startsWith('```')) {
			const lang = line.trim().slice(3).trim();
			const codeLines: string[] = [];
			i++;
			while (i < lines.length && !lines[i].trim().startsWith('```')) {
				codeLines.push(lines[i]);
				i++;
			}
			i++;
			if (lang.toLowerCase() === 'mermaid') {
				elements.push(
					<MermaidDiagram
						key={`mermaid-${i}`}
						code={codeLines.join('\n')}
						isLight={isLight}
					/>
				);
				continue;
			}
			elements.push(
				<div
					key={`code-${i}`}
					className={`my-4 rounded-xl border overflow-hidden ${
						isLight
							? 'bg-zinc-50 border-zinc-200'
							: 'bg-zinc-950 border-zinc-800'
					}`}
				>
					{lang && (
						<div
							className={`px-4 py-1.5 border-b text-[11px] font-mono uppercase ${
								isLight
									? 'bg-zinc-100 border-zinc-200 text-zinc-500'
									: 'bg-zinc-900 border-zinc-800 text-zinc-400'
							}`}
						>
							{lang}
						</div>
					)}
					<pre
						className={`p-4 text-xs font-mono overflow-x-auto leading-6 ${
							isLight ? 'text-zinc-800' : 'text-zinc-200'
						}`}
					>
						{codeLines.join('\n')}
					</pre>
				</div>
			);
			continue;
		}

		// Markdown table
		if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
			const tableLines: string[] = [];
			while (
				i < lines.length &&
				lines[i].trim().startsWith('|') &&
				lines[i].trim().endsWith('|')
			) {
				tableLines.push(lines[i].trim());
				i++;
			}
			const rows = tableLines
				.filter((l) => !/^\|[\s\-:|]+\|$/.test(l))
				.map((l) =>
					l
						.slice(1, -1)
						.split('|')
						.map((c) => c.trim())
				);
			if (rows.length > 0) {
				const header = rows[0];
				const body = rows.slice(1);
				elements.push(
					<div
						key={`tbl-${i}`}
						className={`my-4 overflow-x-auto rounded-xl border ${
							isLight ? 'border-zinc-200' : 'border-zinc-800'
						}`}
					>
						<table className="w-full text-left border-collapse text-xs">
							<thead>
								<tr
									className={`border-b font-semibold ${
										isLight
											? 'bg-zinc-100/80 border-zinc-200 text-zinc-700'
											: 'bg-zinc-900 border-zinc-800 text-zinc-300'
									}`}
								>
									{header.map((cell, cIdx) => (
										<th key={cIdx} className="px-4 py-3">
											<InlineSmartText
												text={cell}
												isLight={isLight}
												onSelectIssue={onSelectIssue}
												onSelectFileRef={onSelectFileRef}
												onSelectPlan={onSelectPlan}
											/>
										</th>
									))}
								</tr>
							</thead>
							<tbody
								className={`divide-y ${
									isLight
										? 'divide-zinc-200 bg-white'
										: 'divide-zinc-800/80 bg-zinc-950/40'
								}`}
							>
								{body.map((row, rIdx) => (
									<tr
										key={rIdx}
										className={
											isLight
												? 'hover:bg-zinc-50/80'
												: 'hover:bg-zinc-900/50'
										}
									>
										{row.map((cell, cIdx) => (
											<td
												key={cIdx}
												className={`px-4 py-3 align-top leading-7 ${
													isLight ? 'text-zinc-700' : 'text-zinc-300'
												}`}
											>
												<InlineSmartText
													text={cell}
													isLight={isLight}
													onSelectIssue={onSelectIssue}
													onSelectFileRef={onSelectFileRef}
													onSelectPlan={onSelectPlan}
												/>
											</td>
										))}
									</tr>
								))}
							</tbody>
						</table>
					</div>
				);
			}
			continue;
		}

		// Headings
		const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
		if (hMatch) {
			const level = hMatch[1].length;
			const text = hMatch[2].trim();
			const sizeClass =
				level === 1
					? `text-xl font-bold mt-6 mb-3 pb-2 border-b ${
							isLight
								? 'text-zinc-900 border-zinc-200'
								: 'text-zinc-100 border-zinc-800'
						}`
					: level === 2
						? `text-base font-bold mt-6 mb-2.5 ${
								isLight ? 'text-zinc-900' : 'text-zinc-100'
							}`
						: level === 3
							? `text-sm font-semibold mt-4 mb-2 ${
									isLight ? 'text-blue-700' : 'text-blue-400'
								}`
							: `text-xs font-semibold mt-3 mb-1.5 ${
									isLight ? 'text-zinc-800' : 'text-zinc-200'
								}`;
			elements.push(
				<div key={`h-${i}`} className={sizeClass}>
					<InlineSmartText
						text={text}
						isLight={isLight}
						onSelectIssue={onSelectIssue}
						onSelectFileRef={onSelectFileRef}
						onSelectPlan={onSelectPlan}
					/>
				</div>
			);
			i++;
			continue;
		}

		// Blockquote
		if (line.trim().startsWith('>')) {
			const quoteLines: string[] = [];
			while (i < lines.length && lines[i].trim().startsWith('>')) {
				quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
				i++;
			}
			elements.push(
				<blockquote
					key={`q-${i}`}
					className={`my-3 pl-4 pr-3 py-2.5 border-l-2 border-blue-500 rounded-r-xl text-xs space-y-1.5 leading-7 ${
						isLight
							? 'bg-zinc-100/80 text-zinc-700'
							: 'bg-zinc-900/70 text-zinc-300'
					}`}
				>
					{quoteLines.map((ql, qIdx) => (
						<div key={qIdx}>
							<InlineSmartText
								text={ql}
								isLight={isLight}
								onSelectIssue={onSelectIssue}
								onSelectFileRef={onSelectFileRef}
								onSelectPlan={onSelectPlan}
							/>
						</div>
					))}
				</blockquote>
			);
			continue;
		}

		// Bullet list item
		const liMatch = line.match(/^(\s*)[-*]\s+(.+)$/);
		if (liMatch) {
			const indent = Math.min(4, Math.floor(liMatch[1].length / 2));
			const content = liMatch[2];
			elements.push(
				<div
					key={`li-${i}`}
					style={{ paddingLeft: `${indent * 18}px` }}
					className={`flex items-start gap-2.5 my-2 text-[13px] leading-7 ${
						isLight ? 'text-zinc-700' : 'text-zinc-300'
					}`}
				>
					<span className="text-blue-500 mt-1.5 text-[10px] select-none">●</span>
					<div className="flex-1 min-w-0">
						<InlineSmartText
							text={content}
							isLight={isLight}
							onSelectIssue={onSelectIssue}
							onSelectFileRef={onSelectFileRef}
							onSelectPlan={onSelectPlan}
						/>
					</div>
				</div>
			);
			i++;
			continue;
		}

		// Horizontal rule
		if (/^---+$/.test(line.trim())) {
			elements.push(
				<hr
					key={`hr-${i}`}
					className={`my-5 ${isLight ? 'border-zinc-200' : 'border-zinc-800'}`}
				/>
			);
			i++;
			continue;
		}

		// Blank line
		if (!line.trim()) {
			i++;
			continue;
		}

		// Paragraph
		elements.push(
			<p
				key={`p-${i}`}
				className={`my-2.5 text-[13px] leading-7 ${
					isLight ? 'text-zinc-700' : 'text-zinc-300'
				}`}
			>
				<InlineSmartText
					text={line}
					isLight={isLight}
					onSelectIssue={onSelectIssue}
					onSelectFileRef={onSelectFileRef}
					onSelectPlan={onSelectPlan}
				/>
			</p>
		);
		i++;
	}

	return <div className="space-y-1.5">{elements}</div>;
};
