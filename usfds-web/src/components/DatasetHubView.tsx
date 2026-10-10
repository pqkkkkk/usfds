import { useState } from 'react';
import { 
  Database, 
  Upload, 
  Search, 
  GitBranch, 
  ArrowRight,
  FolderGit2,
} from 'lucide-react';
import { PageHeader } from './layout/PageHeader';
import type { DatasetEntity } from '../types/navigation';

interface DatasetHubViewProps {
  onSelectDataset: (dataset: DatasetEntity) => void;
  onOpenInspector?: (item: any) => void;
}

export const SAMPLE_DATASETS: DatasetEntity[] = [
  {
    id: '57e490a7-7f73-4ecd-a425-eb83c6474134',
    name: 'E-Commerce Transactions 2026',
    description: 'Tập dữ liệu thanh toán trực tuyến phân tích thẻ tín dụng và hành vi đặt hàng gian lận',
    category: 'E-Commerce / Payment',
    createdAt: '2026-10-10 07:20',
    updatedAt: '10 mins ago',
    totalArtifacts: 3,
    artifacts: [
      {
        id: 'art-raw-8921',
        name: 'raw_transactions_oct2026.csv',
        stage: 'RAW',
        parentId: null,
        rows: 154200,
        columns: 32,
        qualityScore: 88,
        fileSize: '42.8 MB',
        format: 'CSV',
        checksum: 'sha256:e3b0c44298fc1c14...b4c6',
        createdAt: '2026-10-01 08:32',
        children: [
          {
            id: 'art-map-9014',
            name: 'ecommerce_canonical_mapped.parquet',
            stage: 'MAPPED',
            parentId: 'art-raw-8921',
            rows: 154200,
            columns: 5,
            qualityScore: 98,
            fileSize: '14.2 MB',
            format: 'Parquet',
            checksum: 'sha256:7d8f9213ef21004a...911b',
            createdAt: '2026-10-01 09:10',
            branch: 'main',
            children: [
              {
                id: 'art-prep-9520',
                name: 'features_velocity_7d_normalized.parquet',
                stage: 'PRE_PROCESSED',
                parentId: 'art-map-9014',
                rows: 154200,
                columns: 58,
                qualityScore: 100,
                fileSize: '28.6 MB',
                format: 'Parquet',
                checksum: 'sha256:f45a19028cb18903...a381',
                createdAt: '2026-10-02 11:25',
                branch: 'main',
              },
              {
                id: 'art-prep-9521',
                name: 'features_velocity_1h_experimental.parquet',
                stage: 'PRE_PROCESSED',
                parentId: 'art-map-9014',
                rows: 154200,
                columns: 42,
                qualityScore: 96,
                fileSize: '21.0 MB',
                format: 'Parquet',
                checksum: 'sha256:39a8bc43d910123e...199a',
                createdAt: '2026-10-03 14:00',
                branch: 'exp-short-window',
              }
            ]
          }
        ]
      }
    ]
  },
  {
    id: 'ds-banking-wire-aml',
    name: 'Core Banking Wire Transfer Log',
    description: 'Dữ liệu chuyển tiền liên ngân hàng phục vụ sàng lọc AML và phát hiện giao dịch bất thường',
    category: 'Banking / Wire Transfer',
    createdAt: '2026-09-25 10:15',
    updatedAt: '2 days ago',
    totalArtifacts: 2,
    artifacts: [
      {
        id: 'art-raw-7712',
        name: 'wire_transfers_sep2026.csv',
        stage: 'RAW',
        parentId: null,
        rows: 85200,
        columns: 24,
        qualityScore: 82,
        fileSize: '18.4 MB',
        format: 'CSV',
        checksum: 'sha256:1a82bc994022c019...88fa',
        createdAt: '2026-09-25 10:20',
        children: [
          {
            id: 'art-map-7801',
            name: 'wire_transfers_mapped.parquet',
            stage: 'MAPPED',
            parentId: 'art-raw-7712',
            rows: 85200,
            columns: 5,
            qualityScore: 94,
            fileSize: '6.5 MB',
            format: 'Parquet',
            checksum: 'sha256:91efaa0129bcdef0...3341',
            createdAt: '2026-09-26 14:30',
            branch: 'main'
          }
        ]
      }
    ]
  },
  {
    id: 'ds-atm-cash-withdrawals',
    name: 'ATM Cash Withdrawal Records',
    description: 'Nhật ký rút tiền mặt tại cây ATM và điểm chấp nhận POS',
    category: 'Retail Banking / ATM',
    createdAt: '2026-10-05 16:00',
    updatedAt: 'Yesterday',
    totalArtifacts: 1,
    artifacts: [
      {
        id: 'art-raw-3301',
        name: 'atm_logs_q3_2026.csv',
        stage: 'RAW',
        parentId: null,
        rows: 240500,
        columns: 18,
        qualityScore: 78,
        fileSize: '54.1 MB',
        format: 'CSV',
        checksum: 'sha256:bb87091238910fed...2231',
        createdAt: '2026-10-05 16:05',
        children: []
      }
    ]
  }
];

export const DatasetHubView = ({
  onSelectDataset,
}: DatasetHubViewProps) => {
  const [search, setSearch] = useState('');

  const filtered = SAMPLE_DATASETS.filter(ds => 
    ds.name.toLowerCase().includes(search.toLowerCase()) ||
    ds.category.toLowerCase().includes(search.toLowerCase()) ||
    ds.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Page Header */}
      <PageHeader
        title="Datasets"
        subtitle="Quản lý các tập dữ liệu trong hệ thống. Nhấn vào từng Dataset để xem cây phả hệ (Lineage Explorer) và các Artifact tương ứng."
        badge={`${SAMPLE_DATASETS.length} Datasets`}
        badgeColor="blue"
        breadcrumbs={[{ label: 'Data Management' }, { label: 'Datasets' }]}
        actions={
          <div className="flex items-center gap-2">
            <button 
              onClick={() => alert("Mở Modal Import Dataset")}
              className="px-3.5 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5 focus-ring"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Import Dataset</span>
            </button>
          </div>
        }
      />

      {/* Main Container */}
      <div className="flex-1 p-6 overflow-y-auto space-y-4">
        {/* Search & Filter Toolbar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-dark-900 border border-dark-700/80 p-3 rounded-xl">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search datasets by name, category, or ID..."
              className="w-full bg-dark-950 border border-dark-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="font-mono">{filtered.length} datasets found</span>
          </div>
        </div>

        {/* Dataset Table - High Density, Client-friendly */}
        <div className="bg-dark-900 border border-dark-700/80 rounded-xl overflow-hidden shadow-lg">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-dark-850 border-b border-dark-700 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Dataset Name & Identifier</th>
                <th className="py-3 px-4">Domain / Category</th>
                <th className="py-3 px-4">Artifacts & Branches</th>
                <th className="py-3 px-4">Updated</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-800">
              {filtered.map((item) => (
                <tr 
                  key={item.id}
                  onClick={() => onSelectDataset(item)}
                  className="hover:bg-dark-800/50 transition cursor-pointer group"
                >
                  <td className="py-4 px-4">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 shrink-0 group-hover:scale-105 transition">
                        <Database className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-semibold text-slate-100 group-hover:text-brand-400 transition text-sm">
                          {item.name}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5 line-clamp-1 max-w-lg">
                          {item.description}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono mt-1">
                          ID: {item.id}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="py-4 px-4">
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-dark-800 border border-dark-700 text-slate-300">
                      {item.category}
                    </span>
                  </td>

                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-dark-850 border border-dark-700/80 text-brand-400 font-mono text-[11px]">
                        <GitBranch className="w-3.5 h-3.5" />
                        <span>{item.totalArtifacts} {item.totalArtifacts > 1 ? 'artifacts' : 'artifact'}</span>
                      </div>
                    </div>
                  </td>

                  <td className="py-4 px-4 text-slate-400 text-[11px]">
                    {item.updatedAt}
                  </td>

                  <td className="py-4 px-4 text-right">
                    <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => onSelectDataset(item)}
                        className="px-3 py-1.5 rounded-lg bg-brand-500/20 hover:bg-brand-500/30 text-brand-400 border border-brand-500/40 text-xs font-semibold flex items-center gap-1.5 transition"
                      >
                        <FolderGit2 className="w-3.5 h-3.5" />
                        <span>View Lineage</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="px-4 py-3 bg-dark-850 border-t border-dark-700 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Client-only local workspace</span>
            <span>Click any Dataset row to enter Lineage & Artifact Explorer</span>
          </div>
        </div>
      </div>
    </div>
  );
};
