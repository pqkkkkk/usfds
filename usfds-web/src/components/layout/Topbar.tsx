import { useEffect, useRef, useState } from 'react';
import {
	ShieldAlert,
	ChevronDown,
	Search,
	Bell,
	CheckCircle2,
	Layers,
	Plus,
	Settings2,
	Lock,
	Unlock,
} from 'lucide-react';
import type { ProjectResponse } from '../../types/project';

interface TopbarProps {
	projects: ProjectResponse[];
	currentProject: ProjectResponse | null;
	onSelectProject: (proj: ProjectResponse) => void;
	onCreateProjectClick: () => void;
	onManageProjectsClick: () => void;
	onOpenOmnisearch: () => void;
}

export const Topbar = ({
	projects,
	currentProject,
	onSelectProject,
	onCreateProjectClick,
	onManageProjectsClick,
	onOpenOmnisearch,
}: TopbarProps) => {
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const dropdownRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!dropdownOpen) {
			return;
		}
		const handleClickOutside = (event: MouseEvent) => {
			if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
				setDropdownOpen(false);
			}
		};
		const handleEscape = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				setDropdownOpen(false);
			}
		};
		document.addEventListener('mousedown', handleClickOutside);
		document.addEventListener('keydown', handleEscape);
		return () => {
			document.removeEventListener('mousedown', handleClickOutside);
			document.removeEventListener('keydown', handleEscape);
		};
	}, [dropdownOpen]);

	return (
		<header className="h-[56px] min-h-[56px] bg-dark-900 border-b border-dark-700/80 px-4 flex items-center justify-between select-none z-30">
			{/* Brand & Project Selector */}
			<div className="flex items-center gap-4">
				{/* USFDS Logo (Click to return to Project Portal) */}
				<button
					type="button"
					onClick={onManageProjectsClick}
					className="flex items-center gap-2.5 pr-4 border-r border-dark-700/80 hover:opacity-90 transition text-left"
					title="Back to All Projects"
				>
					<div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 shadow-glow-blue">
						<ShieldAlert className="w-5 h-5 text-brand-400" />
					</div>
					<div className="flex flex-col">
						<span className="font-bold tracking-wider text-sm text-slate-100 flex items-center gap-1.5 font-mono">
							USFDS
						</span>
					</div>
				</button>

				{/* Project Context Switcher */}
				<div className="relative" ref={dropdownRef}>
					<button
						type="button"
						onClick={() => setDropdownOpen(!dropdownOpen)}
						className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-md bg-dark-850 hover:bg-dark-800 border border-dark-700/80 text-xs text-slate-200 transition focus-ring"
						aria-label="Select Project"
						aria-expanded={dropdownOpen}
					>
						<Layers className="w-3.5 h-3.5 text-brand-400 shrink-0" />
						<div className="flex flex-col text-left">
							<span className="text-[10px] text-slate-400 leading-none flex items-center gap-1.5">
								<span>Project</span>
								{currentProject && (
									<span
										className={`inline-flex items-center gap-0.5 text-[9px] font-mono ${
											currentProject.is_schema_locked
												? 'text-emerald-400'
												: 'text-amber-400'
										}`}
									>
										{currentProject.is_schema_locked ? (
											<Lock className="w-2.5 h-2.5" />
										) : (
											<Unlock className="w-2.5 h-2.5" />
										)}
										{currentProject.is_schema_locked ? 'LOCKED' : 'UNLOCKED'}
									</span>
								)}
							</span>
							<span className="font-medium text-slate-100 max-w-[190px] truncate mt-0.5">
								{currentProject ? currentProject.project_name : 'No Project Selected'}
							</span>
						</div>
						<ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-1 shrink-0" />
					</button>

					{dropdownOpen && (
						<div className="absolute top-full left-0 mt-1.5 w-72 bg-dark-850 border border-dark-700 rounded-xl shadow-2xl py-1.5 z-50 overflow-hidden">
							<div className="px-3 py-1.5 text-[10px] uppercase font-semibold text-slate-400 border-b border-dark-700/60 flex items-center justify-between font-mono">
								<span>Workspace Projects ({projects.length})</span>
							</div>

							<div className="max-h-64 overflow-y-auto divide-y divide-dark-800/60">
								{projects.length === 0 ? (
									<div className="px-3 py-4 text-center text-xs text-slate-400">
										Chưa có dự án nào. Hãy tạo dự án mới.
									</div>
								) : (
									projects.map((proj) => {
										const isSelected = proj.project_id === currentProject?.project_id;
										return (
											<button
												type="button"
												key={proj.project_id}
												onClick={() => {
													onSelectProject(proj);
													setDropdownOpen(false);
												}}
												className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between gap-2 hover:bg-dark-800 transition ${
													isSelected
														? 'text-brand-400 font-semibold bg-dark-800/70'
														: 'text-slate-300'
												}`}
											>
												<div className="truncate flex-1">
													<div className="flex items-center gap-1.5 truncate">
														<span className="truncate">{proj.project_name}</span>
														{proj.status === 'ARCHIVED' && (
															<span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
																ARCHIVED
															</span>
														)}
													</div>
													<div className="text-[10px] text-slate-500 font-mono flex items-center gap-2 mt-0.5">
														<span
															className={
																proj.is_schema_locked
																	? 'text-emerald-400'
																	: 'text-amber-400'
															}
														>
															{proj.is_schema_locked ? 'Schema Locked' : 'Unlocked'}
														</span>
														<span>•</span>
														<span>{proj.datasets_count} DS</span>
														<span>•</span>
														<span>{proj.rules_count} Rules</span>
													</div>
												</div>
												{isSelected && (
													<CheckCircle2 className="w-3.5 h-3.5 text-brand-400 shrink-0" />
												)}
											</button>
										);
									})
								)}
							</div>

							{/* Dropdown Footer Actions */}
							<div className="p-1.5 border-t border-dark-700/80 bg-dark-900/90 flex items-center gap-1.5">
								<button
									type="button"
									onClick={() => {
										setDropdownOpen(false);
										onCreateProjectClick();
									}}
									className="flex-1 py-1.5 px-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-[11px] font-semibold transition flex items-center justify-center gap-1.5"
								>
									<Plus className="w-3.5 h-3.5" />
									<span>New Project</span>
								</button>
								<button
									type="button"
									onClick={() => {
										setDropdownOpen(false);
										onManageProjectsClick();
									}}
									className="py-1.5 px-2.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-200 text-[11px] font-medium transition flex items-center justify-center gap-1.5"
								>
									<Settings2 className="w-3.5 h-3.5 text-slate-400" />
									<span>Manage Projects</span>
								</button>
							</div>
						</div>
					)}
				</div>
			</div>

			{/* Global Omnisearch (Ctrl+K) */}
			<div className="flex-1 max-w-md mx-6 hidden md:block">
				<button
					type="button"
					onClick={onOpenOmnisearch}
					className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg bg-dark-950/80 hover:bg-dark-950 border border-dark-700/70 hover:border-dark-600 text-xs text-slate-400 transition group focus-ring"
				>
					<div className="flex items-center gap-2">
						<Search className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-400" />
						<span>Search datasets, models, rules, transactions...</span>
					</div>
					<kbd className="px-1.5 py-0.5 rounded text-[10px] bg-dark-850 border border-dark-700 text-slate-400 font-mono">
						Ctrl+K
					</kbd>
				</button>
			</div>

			{/* System Status Indicator & Controls */}
			<div className="flex items-center gap-3">
				<button
					type="button"
					onClick={onOpenOmnisearch}
					className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-800 rounded-md transition md:hidden"
					title="Search"
				>
					<Search className="w-4 h-4" />
				</button>

				<button
					type="button"
					className="relative p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-800 rounded-md transition focus-ring"
					aria-label="Notifications"
				>
					<Bell className="w-4 h-4" />
					<span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-brand-500"></span>
				</button>

				{/* User profile avatar */}
				<div className="flex items-center gap-2 pl-2 border-l border-dark-700/80">
					<div className="w-7 h-7 rounded-full bg-gradient-to-tr from-brand-600 to-emerald-500 flex items-center justify-center text-xs font-bold text-white shadow-sm ring-1 ring-white/10">
						DS
					</div>
					<div className="hidden xl:flex flex-col text-left">
						<span className="text-xs font-medium text-slate-200 leading-tight">Data Scientist</span>
						<span className="text-[10px] text-slate-400">Analyst & ML Eng</span>
					</div>
				</div>
			</div>
		</header>
	);
};
