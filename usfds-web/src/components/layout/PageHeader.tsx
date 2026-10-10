import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { ChevronRight, Home } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  tab?: string;
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: string;
  badgeColor?: 'blue' | 'green' | 'amber' | 'purple';
  breadcrumbs: BreadcrumbItem[];
  onNavigate?: (tab: string) => void;
  actions?: ReactNode;
}

export const PageHeader = ({
  title,
  subtitle,
  badge,
  badgeColor = 'blue',
  breadcrumbs,
  onNavigate,
  actions,
}: PageHeaderProps) => {
  const badgeStyles = {
    blue: 'bg-brand-500/10 text-brand-400 border-brand-500/30',
    green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  };

  return (
    <div className="border-b border-dark-700/80 bg-dark-900/40 px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4 select-none shrink-0">
      {/* Left: Breadcrumbs & Page Titles */}
      <div className="space-y-1.5">
        {/* Breadcrumb line */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[11px] text-slate-400">
          <button 
            onClick={() => onNavigate && onNavigate('data-hub')}
            className="flex items-center gap-1 hover:text-slate-200 transition focus-ring rounded"
          >
            <Home className="w-3 h-3" />
            <span>USFDS</span>
          </button>
          {breadcrumbs.map((crumb, idx) => (
            <Fragment key={idx}>
              <ChevronRight className="w-3 h-3 text-slate-600" />
              {crumb.tab && onNavigate ? (
                <button
                  onClick={() => onNavigate(crumb.tab!)}
                  className="hover:text-slate-200 transition focus-ring rounded truncate max-w-[150px]"
                >
                  {crumb.label}
                </button>
              ) : (
                <span className="text-slate-300 font-medium truncate max-w-[200px]">
                  {crumb.label}
                </span>
              )}
            </Fragment>
          ))}
        </nav>

        {/* Title and Badges */}
        <div className="flex items-center gap-3">
          <h1 className="text-lg md:text-xl font-bold text-slate-100 tracking-tight font-sans">
            {title}
          </h1>
          {badge && (
            <span className={`text-[11px] uppercase font-semibold px-2 py-0.5 rounded border font-mono ${badgeStyles[badgeColor]}`}>
              {badge}
            </span>
          )}
        </div>

        {subtitle && (
          <p className="text-xs text-slate-400 line-clamp-1 max-w-3xl">
            {subtitle}
          </p>
        )}
      </div>

      {/* Right: Actions / Buttons */}
      {actions && (
        <div className="flex items-center gap-2.5 shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
};
