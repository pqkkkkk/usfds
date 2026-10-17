import {
  UploadCloud,
  FileSpreadsheet,
  X,
  Trash2,
  Lock,
  ShieldAlert,
  ArrowRight,
  Loader2,
  CheckCircle2
} from 'lucide-react';
import { useDatasetImport } from '../../../hooks/useDatasetImport';
import type { DatasetDetailResponse, DataClassification } from '../../../types/dataset';

interface ImportDatasetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (detail: DatasetDetailResponse) => void;
  defaultProjectId?: string;
}

export const ImportDatasetModal = ({
  isOpen,
  onClose,
  onSuccess,
  defaultProjectId = '9a0aeacc-dcd0-4142-a858-33c90893025d'
}: ImportDatasetModalProps) => {
  const {
    file,
    filePath,
    datasetName,
    displayName,
    dataClassification,
    containsPii,
    description,
    isLoading,
    errorMsg,
    fileInputRef,
    setDatasetName,
    setDisplayName,
    setDataClassification,
    setContainsPii,
    setDescription,
    handleFileSelected,
    handleBrowseNativeFile,
    handleFileChange,
    removeFile,
    handleSubmit: submitForm,
  } = useDatasetImport({
    defaultProjectId,
    onSuccess: (detail) => {
      onSuccess(detail);
      onClose();
    },
  });

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitForm(e);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="flex items-start justify-between p-6 border-b border-dark-800 bg-dark-950/60">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Import Transaction Dataset
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Upload historical batch or transaction dump for fraud profiling & canonical schema mapping
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

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Drag & Drop File Zone */}
          <div
            onClick={() => handleBrowseNativeFile()}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileSelected(e.dataTransfer.files[0]);
              }
            }}
            className="border-2 border-dashed border-dark-700 hover:border-brand-500/60 bg-dark-950/50 hover:bg-brand-500/5 rounded-xl p-5 text-center cursor-pointer transition group"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".csv,.parquet,.json"
              className="hidden"
            />
            <div className="w-10 h-10 rounded-xl bg-dark-850 group-hover:bg-brand-500/20 text-slate-400 group-hover:text-brand-400 mx-auto flex items-center justify-center transition mb-2">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <p className="text-xs font-semibold text-slate-200 group-hover:text-brand-300 transition">
              Select or Drop local transaction file (<span className="text-brand-400 underline">Browse</span>)
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Supports <code className="text-slate-400 font-mono">.csv</code>, <code className="text-slate-400 font-mono">.parquet</code>, <code className="text-slate-400 font-mono">.json</code>
            </p>
          </div>

          {/* Selected File Card */}
          {file && (
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-700/80 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200 font-mono">{file.name}</div>
                    <div className="text-[10px] text-slate-500">{file.size} • Target: {filePath}</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={removeFile}
                  className="p-1.5 text-slate-500 hover:text-rose-400 transition"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Progress Bar Indicator */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span className="text-emerald-400 font-medium">Ready for Ingestion & Profiling</span>
                  <span className="font-mono">100% Ready</span>
                </div>
                <div className="h-1.5 w-full bg-dark-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 w-full rounded-full transition-all duration-300 shadow-glow-emerald" />
                </div>
              </div>
            </div>
          )}

          {/* Form Fields matching ImportDatasetRequest */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                Dataset Identifier <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g. credit_card_fraud_2026_q3"
                  className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 font-mono focus:border-brand-500 focus:outline-none transition"
                  required
                />
                <Lock className="w-3.5 h-3.5 text-slate-600 absolute right-3 top-2.5" />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                Display Label <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. E-Commerce Credit Card Batch 2026 Q3"
                className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none transition"
                required
              />
            </div>
          </div>

          {/* Data Classification */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Data Classification <span className="text-rose-400">*</span>
            </label>
            <select
              value={dataClassification}
              onChange={(e) => setDataClassification(e.target.value as DataClassification)}
              className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none transition"
            >
              <option value="CONFIDENTIAL">Confidential (Level 3 - Financial & Transaction Records)</option>
              <option value="INTERNAL">Internal (Company Internal Analytics)</option>
              <option value="RESTRICTED">Restricted (Highly Sensitive / Compliance Audited)</option>
              <option value="PUBLIC">Public (Anonymized Benchmarks & Open Datasets)</option>
            </select>
          </div>

          {/* Contains PII Toggle */}
          <div className="p-3.5 rounded-xl bg-dark-950/70 border border-dark-800 flex items-start justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Contains Personally Identifiable Information (PII)
                </span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Cardholder PAN, billing addresses, and IPs will be automatically masked/tokenized using SHA-256 vault.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setContainsPii(!containsPii)}
              className={`w-11 h-6 shrink-0 rounded-full transition-colors relative focus:outline-none ${containsPii ? 'bg-brand-500' : 'bg-dark-800'
                }`}
            >
              <div
                className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-1 ${containsPii ? 'right-1' : 'left-1'
                  }`}
              />
            </button>
          </div>

          {/* Description */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Description / Ingestion Purpose
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ghi chú mục đích huấn luyện mô hình hoặc sàng lọc gian lận..."
              className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none transition resize-none"
            />
          </div>
        </form>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-dark-800 bg-dark-950/80">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isLoading}
            className="px-5 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Ingesting & Profiling...</span>
              </>
            ) : (
              <>
                <span>Proceed</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
