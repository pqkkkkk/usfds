import { useState } from 'react';
import { 
  ShieldAlert, 
  ChevronDown, 
  Search, 
  Bell, 
  CheckCircle2, 
  Layers
} from 'lucide-react';
import type { Project } from '../../types/navigation';

interface TopbarProps {
  projects: Project[];
  currentProject: Project;
  onSelectProject: (proj: Project) => void;
  onOpenOmnisearch: () => void;
}

export const Topbar = ({
  projects,
  currentProject,
  onSelectProject,
  onOpenOmnisearch,
}: TopbarProps) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <header className="h-[56px] min-h-[56px] bg-dark-900 border-b border-dark-700/80 px-4 flex items-center justify-between select-none z-30">
      {/* Brand & Project Selector */}
      <div className="flex items-center gap-4">
        {/* USFDS Logo */}
        <div className="flex items-center gap-2.5 pr-4 border-r border-dark-700/80">
          <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 shadow-glow-blue">
            <ShieldAlert className="w-5 h-5 text-brand-400" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold tracking-wider text-sm text-slate-100 flex items-center gap-1.5 font-mono">
              USFDS
            </span>
          </div>
        </div>

        {/* Project Context Switcher */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-dark-850 hover:bg-dark-800 border border-dark-700/80 text-xs text-slate-200 transition focus-ring"
            aria-label="Select Project"
          >
            <Layers className="w-3.5 h-3.5 text-brand-400" />
            <div className="flex flex-col text-left">
              <span className="text-[10px] text-slate-400 leading-none">Project</span>
              <span className="font-medium text-slate-100 max-w-[180px] truncate">{currentProject.name}</span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-1" />
          </button>

          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-1.5 w-64 bg-dark-850 border border-dark-700 rounded-lg shadow-xl py-1 z-50">
              <div className="px-3 py-1.5 text-[10px] uppercase font-semibold text-slate-400 border-b border-dark-700/60">
                Select Workspace Project
              </div>
              {projects.map((proj) => (
                <button
                  key={proj.id}
                  onClick={() => {
                    onSelectProject(proj);
                    setDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-dark-800 transition ${
                    proj.id === currentProject.id ? 'text-brand-400 font-semibold bg-dark-800/60' : 'text-slate-300'
                  }`}
                >
                  <div className="truncate">
                    <div>{proj.name}</div>
                    <div className="text-[10px] text-slate-500">{proj.id}</div>
                  </div>
                  {proj.id === currentProject.id && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Global Omnisearch (Ctrl+K) */}
      <div className="flex-1 max-w-md mx-6 hidden md:block">
        <button
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

        {/* Action icons */}
        <button 
          onClick={onOpenOmnisearch}
          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-800 rounded-md transition md:hidden"
          title="Search"
        >
          <Search className="w-4 h-4" />
        </button>

        <button 
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
