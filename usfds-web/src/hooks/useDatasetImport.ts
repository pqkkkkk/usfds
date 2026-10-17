import { useState, useCallback, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetApi } from '../api/datasetApi';
import { DATASETS_QUERY_KEY } from './useDatasetList';
import type { ImportDatasetRequest, DatasetDetailResponse, DataClassification } from '../types/dataset';

export interface SampleFileInfo {
  name: string;
  path: string;
  size: string;
  records: string;
  desc: string;
  stem: string;
}

export const SAMPLE_FILES: SampleFileInfo[] = [
  {
    name: 'raw.csv (E-Commerce)',
    path: '../datasets/e-commerce-fraud-detection-dataset/raw.csv',
    size: '25.1 MB',
    records: '~150,000',
    desc: 'E-Commerce Online Fraud Transaction Stream',
    stem: 'ecommerce_fraud_events'
  },
  {
    name: 'raw.csv (Sparkov)',
    path: '../datasets/sparkov/raw.csv',
    size: '335 MB',
    records: '~1,850,000',
    desc: 'Sparkov Simulated Credit Card Fraud Logs',
    stem: 'sparkov_credit_card_fraud'
  },
  {
    name: 'raw.csv (IEEE-CIS)',
    path: '../datasets/ieee-cis/raw.csv',
    size: '651 MB',
    records: '~590,000',
    desc: 'IEEE-CIS Credit Card Benchmark Sample',
    stem: 'ieee_cis_transactions'
  }
];

interface UseDatasetImportOptions {
  defaultProjectId?: string;
  onSuccess?: (detail: DatasetDetailResponse) => void;
}

export function useDatasetImport({
  defaultProjectId = '9a0aeacc-dcd0-4142-a858-33c90893025d',
  onSuccess,
}: UseDatasetImportOptions = {}) {
  const queryClient = useQueryClient();

  const [file, setFile] = useState<{ name: string; size: string; path: string } | null>(null);
  const [filePath, setFilePath] = useState('');
  const [datasetName, setDatasetName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [dataClassification, setDataClassification] = useState<DataClassification>('CONFIDENTIAL');
  const [containsPii, setContainsPii] = useState(true);
  const [description, setDescription] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Importing dataset handler
  const importMutation = useMutation({
    mutationFn: async (payload: ImportDatasetRequest) => {
      const res = await datasetApi.importDataset(payload);
      if (!res.success || !res.data) {
        throw new Error(res.error || 'Nhập dataset thất bại.');
      }
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: DATASETS_QUERY_KEY });
      onSuccess?.(data);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || 'Lỗi mạng khi tải lên dataset.');
    },
  });

  // Handle file selection from File Input or Drag & Drop
  const handleFileSelected = useCallback((selected: File) => {
    const sizeMb = (selected.size / (1024 * 1024)).toFixed(1);
    const cleanStem = selected.name.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_');

    // Trong môi trường Desktop (Electron):
    // Electron 28+ / Chromium 128+ đã loại bỏ thuộc tính `File.path` vì lý do bảo mật.
    // Thay vào đó, lấy absolute path thông qua `window.electronAPI.getPathForFile(file)`.
    let desktopNativePath = '';
    if (window.electronAPI?.getPathForFile) {
      try {
        desktopNativePath = window.electronAPI.getPathForFile(selected) || '';
      } catch (err) {
        console.warn('Failed to retrieve native file path via electronAPI:', err);
      }
    }
    if (!desktopNativePath) {
      desktopNativePath = (selected as any).path || '';
    }

    console.log("Resolved desktop native path:", desktopNativePath);
    const resolvedPath = desktopNativePath && desktopNativePath.length > 0
      ? desktopNativePath
      : (filePath && filePath.endsWith(selected.name) ? filePath : `../datasets/${selected.name}`);

    setFile({
      name: selected.name,
      size: `${sizeMb} MB`,
      path: resolvedPath,
    });
    setFilePath(resolvedPath);
    setDatasetName(cleanStem);
    setDisplayName(selected.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' ').toUpperCase());
    setErrorMsg(null);
  }, [filePath]);

  // Handle opening native file chooser on Desktop, or HTML input fallback
  const handleBrowseNativeFile = useCallback(async () => {
    if (window.electronAPI?.openFileDialog) {
      try {
        const selectedPath = await window.electronAPI.openFileDialog({
          title: 'Select Transaction Dataset File',
          filters: [
            { name: 'Dataset Files (*.csv, *.parquet, *.json, *.tsv)', extensions: ['csv', 'parquet', 'json', 'tsv'] },
            { name: 'All Files (*.*)', extensions: ['*'] },
          ],
        });

        if (selectedPath) {
          const fileName = selectedPath.split(/[/\\]/).pop() || 'dataset.csv';
          const cleanStem = fileName.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_');

          setFile({
            name: fileName,
            size: 'Local Disk File',
            path: selectedPath,
          });
          setFilePath(selectedPath);
          setDatasetName(cleanStem);
          setDisplayName(fileName.replace(/\.[^/.]+$/, '').replace(/_/g, ' ').toUpperCase());
          setErrorMsg(null);
          return true;
        }
        return false;
      } catch (err: any) {
        console.warn('Error opening native file dialog:', err);
      }
    }

    // Fallback to standard HTML file input
    fileInputRef.current?.click();
    return false;
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  }, [handleFileSelected]);

  const handleSelectSample = useCallback((sample: SampleFileInfo) => {
    setFile({
      name: sample.name,
      size: sample.size,
      path: sample.path
    });
    setFilePath(sample.path);
    setDatasetName(sample.stem);
    setDisplayName(sample.desc);
    setErrorMsg(null);
  }, []);

  const removeFile = useCallback(() => {
    setFile(null);
    setFilePath('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const resetForm = useCallback(() => {
    setFile(null);
    setFilePath('');
    setDatasetName('');
    setDisplayName('');
    setDescription('');
    setContainsPii(false);
    setDataClassification('INTERNAL');
    setErrorMsg(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!filePath.trim()) {
      setErrorMsg('Vui lòng cung cấp đường dẫn tệp trên hệ thống (Local / Server File Path).');
      return;
    }
    if (!datasetName.trim()) {
      setErrorMsg('Vui lòng nhập định danh Dataset Identifier.');
      return;
    }

    setErrorMsg(null);

    const payload: ImportDatasetRequest = {
      file_path: filePath.trim(),
      dataset_name: datasetName.trim(),
      display_name: displayName.trim() || undefined,
      description: description.trim() || undefined,
      project_id: defaultProjectId,
      // Mock user id, deploy as only client app so don't need user management
      user_id: '3fa85f64-5717-4562-b3fc-2c963f66afa6',
      contains_pii: containsPii,
      data_classification: dataClassification,
    };

    try {
      return await importMutation.mutateAsync(payload);
    } catch {
      // Error handled by onError callback in mutation
    }
  }, [filePath, datasetName, displayName, description, defaultProjectId, containsPii, dataClassification, importMutation]);

  return {
    file,
    filePath,
    setFilePath,
    datasetName,
    displayName,
    dataClassification,
    containsPii,
    description,
    isLoading: importMutation.isPending,
    errorMsg,
    fileInputRef,
    sampleFiles: SAMPLE_FILES,
    setDatasetName,
    setDisplayName,
    setDataClassification,
    setContainsPii,
    setDescription,
    setErrorMsg,
    handleFileSelected,
    handleBrowseNativeFile,
    handleFileChange,
    handleSelectSample,
    removeFile,
    handleSubmit,
    resetForm,
  };
}

export default useDatasetImport;
