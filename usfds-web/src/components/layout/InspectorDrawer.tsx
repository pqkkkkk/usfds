import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';

interface InspectorTab {
  id: string;
  label: string;
}

interface InspectorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  tabs?: InspectorTab[];
  activeTab?: string;
  onSelectTab?: (tabId: string) => void;
  children: ReactNode;
  footerActions?: ReactNode;
  width?: 'md' | 'lg' | 'xl';
}

export const InspectorDrawer = ({
  isOpen,
  onClose,
  title,
  subtitle,
  tabs,
  activeTab,
  onSelectTab,
  children,
  footerActions,
  width = 'lg',
}) => {
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const widthClasses = {
    md: 'w-[420px]',
    lg: 'w-[520px]',
    xl: 'w-[640px]',
  };

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex shadow-2xl">
      {/* Slide-over panel */}
      <div 
        ref={drawerRef}
        role="dialog"
        aria-label={title}
        className={`h-full ${widthClasses[width]} bg-dark-900 border-l border-dark-700/80 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-200 z-50`}
      >
        {/* Drawer Header */}
        <div className="border-b border-dark-700/80 px-5 py-3.5 bg-dark-850 shrink-0">
          <div className="flex items-center justify-between gap-3">
            <div className="truncate">
              <h3 className="text-sm font-bold text-slate-100 truncate">
                {title}
              </h3>
              {subtitle && (
                <p className="text-[11px] text-slate-400 truncate mt-0.5 font-mono">
                  {subtitle}
                </p>
              )}
            </div>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-800 rounded-md transition focus-ring"
              aria-label="Close Inspector"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Tabs if provided */}
          {tabs && tabs.length > 0 && (
            <div className="flex items-center gap-1 mt-3 border-b border-dark-700/60 -mb-3.5 pt-1">
              {tabs.map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => onSelectTab && onSelectTab(tab.id)}
                    className={`px-3 py-1.5 text-xs font-medium border-b-2 transition ${
                      isActive
                        ? 'border-brand-500 text-brand-400 font-semibold'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs text-slate-300">
          {children}
        </div>

        {/* Drawer Footer Actions */}
        {footerActions && (
          <div className="border-t border-dark-700/80 px-5 py-3 bg-dark-850/80 shrink-0 flex items-center justify-end gap-2.5">
            {footerActions}
          </div>
        )}
      </div>
    </div>
  );
};
