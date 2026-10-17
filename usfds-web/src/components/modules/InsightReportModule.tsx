import { PageHeader } from '../layout/PageHeader';
import { BarChart2 } from 'lucide-react';

export const InsightReportModule = () => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <PageHeader
        title="Insight & Report"
        subtitle="Báo cáo phân tích xu hướng gian lận, hiệu suất mô hình và tỷ lệ cảnh báo giả (False Positive)"
        badge="Analytics"
        badgeColor="purple"
        breadcrumbs={[
          { label: 'Insight & Report' },
          { label: 'Dashboard' }
        ]}
      />
      
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
          <BarChart2 className="w-8 h-8 text-purple-400 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-100">Fraud Insights & Executive Reporting</h3>
          <p className="text-xs text-slate-400">
            Biểu đồ thống kê tỷ lệ phát hiện gian lận, xu hướng biến động theo thời gian và hiệu quả rule/model.
          </p>
        </div>
      </div>
    </div>
  );
};
