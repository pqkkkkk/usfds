import type { ReactNode } from 'react';
import { Database } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center p-8 rounded-xl border border-dashed border-dark-700 bg-dark-900/40 max-w-md mx-auto my-6',
        className
      )}
    >
      <div className="p-3 rounded-full bg-dark-800 text-slate-400 mb-3">
        {icon || <Database className="w-6 h-6 text-slate-500" />}
      </div>
      <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      {description && (
        <p className="text-xs text-slate-400 mt-1 mb-4 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
