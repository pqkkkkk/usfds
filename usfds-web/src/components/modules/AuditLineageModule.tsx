import { PageHeader } from '../layout/PageHeader';
import { GitCommit, GitBranch } from 'lucide-react';

export const AuditLineageModule = () => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <PageHeader
        title="Audit Logs & Lineage DAG"
        subtitle="Truy vết nguồn gốc toàn vẹn dữ liệu, lịch sử huấn luyện và nhật ký hệ thống"
        badge="Governance"
        badgeColor="purple"
        breadcrumbs={[
          { label: 'Audit & Lineage' },
          { label: 'Overview' }
        ]}
      />
      
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
          <GitBranch className="w-8 h-8 text-purple-400 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-100">Immutable Lineage DAG</h3>
          <p className="text-xs text-slate-400">
            Cây phả hệ liên kết từ Dataset thô ban đầu đến phiên bản mô hình được triển khai.
          </p>
        </div>
      </div>
    </div>
  );
};
