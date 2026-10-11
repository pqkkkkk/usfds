import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../utils/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  header?: ReactNode;
  footer?: ReactNode;
}

export function Card({ className, header, footer, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl bg-dark-900 border border-dark-700/80 shadow-md shadow-dark-950/20 overflow-hidden flex flex-col',
        className
      )}
      {...props}
    >
      {header && <div className="px-5 py-3.5 border-b border-dark-700/80 bg-dark-850/50">{header}</div>}
      <div className="p-5 flex-1">{children}</div>
      {footer && <div className="px-5 py-3 border-t border-dark-700/80 bg-dark-850/30">{footer}</div>}
    </div>
  );
}
