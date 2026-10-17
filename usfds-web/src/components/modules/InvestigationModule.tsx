import { PageHeader } from '../layout/PageHeader';
import { SearchCheck } from 'lucide-react';

export const InvestigationModule = () => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <PageHeader
        title="Investigation & Case Review"
        subtitle="Rà soát các giao dịch bị gắn cờ gian lận, điều tra nguyên nhân và đưa ra quyết định xử lý"
        badge="Module"
        badgeColor="amber"
        breadcrumbs={[
          { label: 'Investigation' },
          { label: 'Alert Queue' }
        ]}
      />
      
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
          <SearchCheck className="w-8 h-8 text-amber-400 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-100">Case Investigation & Alert Queue</h3>
          <p className="text-xs text-slate-400">
            Hàng đợi rà soát cảnh báo giao dịch gian lận, điều tra chi tiết và phân công xử lý ca nghi vấn.
          </p>
        </div>
      </div>
    </div>
  );
};
