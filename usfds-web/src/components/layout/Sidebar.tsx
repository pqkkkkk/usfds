import type { ElementType } from 'react';
import { 
  Database, 
  BrainCircuit, 
  ShieldCheck, 
  Terminal, 
  SearchCheck,
  BarChart2,
  Settings,
  ChevronLeft, 
  ChevronRight
} from 'lucide-react';
import type { AppModule } from '../../types/navigation';

interface SidebarProps {
  activeModule: AppModule;
  onSelectModule: (module: AppModule) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

interface ModuleOption {
  id: AppModule;
  label: string;
  subLabel: string;
  icon: ElementType;
}

export const Sidebar = ({
  activeModule,
  onSelectModule,
  collapsed,
  onToggleCollapse,
}: SidebarProps) => {
  const modules: ModuleOption[] = [
    {
      id: 'data-management',
      label: 'Quản lý dữ liệu',
      subLabel: 'Tập dữ liệu & nguồn gốc',
      icon: Database,
    },
    {
      id: 'model-management',
      label: 'Quản lý mô hình',
      subLabel: 'Huấn luyện & đánh giá',
      icon: BrainCircuit,
    },
    {
      id: 'rule-management',
      label: 'Quản lý luật',
      subLabel: 'Thiết kế & kiểm thử lịch sử',
      icon: ShieldCheck,
    },
    {
      id: 'detection',
      label: 'Phát hiện gian lận',
      subLabel: 'Tác vụ suy luận',
      icon: Terminal,
    },
    {
      id: 'investigation',
      label: 'Điều tra',
      subLabel: 'Xem xét hồ sơ & cảnh báo',
      icon: SearchCheck,
    },
    {
      id: 'insight-report',
      label: 'Phân tích & Báo cáo',
      subLabel: 'Phân tích & xu hướng',
      icon: BarChart2,
    },
    {
      id: 'project-settings',
      label: 'Cài đặt dự án',
      subLabel: 'Thông tin & lược đồ thô',
      icon: Settings,
    },
  ];

  return (
    <aside
      className={`relative bg-dark-900 border-r border-dark-700/80 transition-all duration-200 select-none flex flex-col justify-between z-20 ${
        collapsed ? 'w-[64px] min-w-[64px]' : 'w-[240px] min-w-[240px]'
      }`}
    >
      {/* Module List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-4 px-2 space-y-2">
        {!collapsed && (
          <div className="px-3 pb-1 text-[10px] font-semibold tracking-wider uppercase text-slate-500 font-mono">
            Điều hướng
          </div>
        )}

        <div className="space-y-1">
          {modules.map((mod) => {
            const Icon = mod.icon;
            const isActive = activeModule === mod.id;
            return (
              <button
                key={mod.id}
                onClick={() => onSelectModule(mod.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition group focus-ring ${
                  isActive
                    ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30 font-semibold shadow-sm'
                    : 'text-slate-300 hover:text-slate-100 hover:bg-dark-800/70 border border-transparent'
                } ${collapsed ? 'justify-center px-0' : ''}`}
                title={collapsed ? mod.label : undefined}
              >
                <Icon className={`w-4 h-4 shrink-0 transition ${
                  isActive ? 'text-brand-400' : 'text-slate-400 group-hover:text-slate-200'
                }`} />

                {!collapsed && (
                  <div className="truncate text-left">
                    <div className="truncate">{mod.label}</div>
                    <div className="text-[10px] text-slate-500 font-normal truncate">
                      {mod.subLabel}
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Collapse Toggle Footer */}
      <div className="p-2 border-t border-dark-700/80 bg-dark-950/40">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center gap-2 py-2 px-2.5 rounded-md hover:bg-dark-800 text-slate-400 hover:text-slate-200 text-xs transition focus-ring"
          aria-label={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span className="font-medium text-[11px]">Thu gọn thanh bên</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
