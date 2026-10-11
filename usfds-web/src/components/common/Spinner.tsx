import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface SpinnerProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export function Spinner({ className, size = 'md', label }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-2.5 p-4 text-slate-400">
      <Loader2 className={cn('animate-spin text-brand-500', sizeClasses[size], className)} />
      {label && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </div>
  );
}
