import { useState } from 'react';
import {
  Download,
  X,
  ShieldAlert,
  Copy,
  Check,
  Loader2,
  Lock,
  Sparkles
} from 'lucide-react';
import type { ExportDatasetRequest, DatasetArtifactResponse } from '../../../types/dataset';

interface ExportDatasetModalProps {
  isOpen: boolean;
  onClose: () => void;
  datasetName?: string;
  artifact: DatasetArtifactResponse | null;
  onExport: (payload: ExportDatasetRequest, filename: string) => Promise<any>;
  isExporting?: boolean;
  exportError?: string | null;
}

export const ExportDatasetModal = ({
  isOpen,
  onClose,
  datasetName = '',
  artifact,
  onExport,
  isExporting = false,
  exportError = null,
}: ExportDatasetModalProps) => {
  const [includeTrain, setIncludeTrain] = useState(true);
  const [includeTest, setIncludeTest] = useState(true);
  const [includePipeline, setIncludePipeline] = useState(true);
  const [includeSchema, setIncludeSchema] = useState(true);
  const [fileFormat, setFileFormat] = useState<'parquet' | 'csv'>('parquet');
  const [bundleZip, setBundleZip] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const targetArtifactId = artifact?.artifact_id || 'art-prep-9520';
  const exportFilename = `usfds_${datasetName}_normalized_${fileFormat}.zip`;

  const handleCopyFilename = () => {
    navigator.clipboard.writeText(exportFilename);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    const payload: ExportDatasetRequest = {
      include_train: includeTrain,
      include_test: includeTest,
      include_pipeline: includePipeline,
      include_schema: includeSchema,
      file_format: fileFormat,
    };

    try {
      await onExport(payload, exportFilename);
      onClose();
    } catch {
      // Error handling is surfaced via exportError prop from custom hook
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-dark-800 bg-dark-950/60">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Export Normalized Dataset & Pipeline Artifacts
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Generate secure offline bundles for offline ML modeling, backtesting, or regulatory auditing.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {exportError && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{exportError}</span>
            </div>
          )}

          {/* Source Artifact Meta Card */}
          <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-center justify-between text-xs">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Source Artifact:</span>
                <span className="px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 font-mono font-bold text-[10px]">
                  {artifact?.pipeline_stage || 'PRE_PROCESSED'}
                </span>
                <span className="font-mono text-slate-300">{targetArtifactId.slice(0, 12)}...</span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono truncate max-w-sm">
                Checksum: {artifact?.checksum_sha256 ? `${artifact.checksum_sha256.slice(0, 24)}...` : 'sha256:4e8b7c195794e36fe300...'}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[11px] font-mono text-slate-300">Branch: <span className="text-brand-400 font-bold">main</span></div>
              <div className="text-[10px] text-slate-500">Total: ~9.0 MB uncompressed</div>
            </div>
          </div>

          {/* Select Artifact Components */}
          <div className="space-y-2.5">
            <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              Select Artifact Components to Export
            </label>

            <div className="space-y-2">
              {/* Component 1: Train Set */}
              <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-dark-800 hover:border-dark-700 cursor-pointer transition">
                <div className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    checked={includeTrain}
                    onChange={(e) => setIncludeTrain(e.target.checked)}
                    className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-mono font-bold text-slate-200">train_processed.parquet</div>
                    <div className="text-[10px] text-slate-500">80,000 rows • 24 features</div>
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-400">6.2 MB</span>
              </label>

              {/* Component 2: Test Set */}
              <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-dark-800 hover:border-dark-700 cursor-pointer transition">
                <div className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    checked={includeTest}
                    onChange={(e) => setIncludeTest(e.target.checked)}
                    className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-mono font-bold text-slate-200">test_processed.parquet</div>
                    <div className="text-[10px] text-slate-500">20,000 rows • 24 features</div>
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-400">1.6 MB</span>
              </label>

              {/* Component 3: Fitted Pipeline */}
              <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-dark-800 hover:border-dark-700 cursor-pointer transition">
                <div className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    checked={includePipeline}
                    onChange={(e) => setIncludePipeline(e.target.checked)}
                    className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-mono font-bold text-slate-200">fitted_pipeline.joblib</div>
                    <div className="text-[10px] text-slate-500">Preprocessing transformers & learned scaling statistics</div>
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-400">1.2 MB</span>
              </label>

              {/* Component 4: Schema Definition */}
              <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-dark-800 hover:border-dark-700 cursor-pointer transition">
                <div className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    checked={includeSchema}
                    onChange={(e) => setIncludeSchema(e.target.checked)}
                    className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-mono font-bold text-slate-200">schema_definition.json</div>
                    <div className="text-[10px] text-slate-500">Column metadata, data types, and quality audit report</div>
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-400">45 KB</span>
              </label>
            </div>
          </div>

          {/* File Serialization Format */}
          <div className="space-y-2">
            <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              File Serialization Format
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                onClick={() => setFileFormat('parquet')}
                className={`p-3 rounded-xl border cursor-pointer transition flex items-start gap-2.5 ${fileFormat === 'parquet'
                  ? 'bg-brand-500/10 border-brand-500/50 shadow-glow-blue'
                  : 'bg-dark-950 border-dark-800 hover:border-dark-700'
                  }`}
              >
                <input
                  type="radio"
                  name="format"
                  checked={fileFormat === 'parquet'}
                  onChange={() => { }}
                  className="mt-0.5 text-brand-500"
                />
                <div>
                  <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <span>Apache Parquet (.parquet)</span>
                    <Sparkles className="w-3 h-3 text-brand-400" />
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Recommended for ML & columnar analytics. Snappy compression preserves datatypes.
                  </div>
                </div>
              </label>

              <label
                onClick={() => setFileFormat('csv')}
                className={`p-3 rounded-xl border cursor-pointer transition flex items-start gap-2.5 ${fileFormat === 'csv'
                  ? 'bg-brand-500/10 border-brand-500/50 shadow-glow-blue'
                  : 'bg-dark-950 border-dark-800 hover:border-dark-700'
                  }`}
              >
                <input
                  type="radio"
                  name="format"
                  checked={fileFormat === 'csv'}
                  onChange={() => { }}
                  className="mt-0.5 text-brand-500"
                />
                <div>
                  <div className="text-xs font-bold text-slate-200">
                    Comma-Separated (.csv)
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Plain-text tabular format. Larger file size, ignores nested vector attributes.
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* Bundle ZIP Archive */}
          <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={bundleZip}
                onChange={(e) => setBundleZip(e.target.checked)}
                className="rounded border-dark-700 text-brand-500"
              />
              <span className="text-xs font-bold text-slate-200">
                Bundle all selected files into a compressed ZIP archive (.zip)
              </span>
            </label>

            <div className="flex items-center justify-between p-2 rounded-lg bg-dark-900 border border-dark-850 font-mono text-[11px] text-slate-300">
              <span className="truncate">{exportFilename}</span>
              <button
                type="button"
                onClick={handleCopyFilename}
                className="text-slate-400 hover:text-slate-200 p-1 transition flex items-center gap-1"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Security Compliance Note */}
          <div className="p-3 rounded-xl bg-dark-950 border border-dark-800/80 flex items-start gap-2.5 text-slate-400 text-[11px]">
            <Lock className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <span className="font-semibold text-slate-300">Security Compliance:</span> Export event will be logged to Enterprise Audit Trail (Event: #EXP-8941). All cardholder PANs remain salted & masked with SHA-256 tokens under PCI-DSS Level 1 compliance.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-dark-800 bg-dark-950/80">
          <button
            type="button"
            onClick={onClose}
            disabled={isExporting}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={isExporting || (!includeTrain && !includeTest && !includePipeline && !includeSchema)}
            className="px-5 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Archiving & Downloading...</span>
              </>
            ) : (
              <>
                <Download className="w-3.5 h-3.5" />
                <span>Download Bundle</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
