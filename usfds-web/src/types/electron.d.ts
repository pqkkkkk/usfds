export interface ElectronAPI {
  isElectron: boolean;
  platform: string;
  checkBackendStatus: () => Promise<{ healthy: boolean; url: string; external: boolean }>;
  openExternalUrl: (url: string) => Promise<void>;
  minimizeWindow: () => Promise<void>;
  maximizeWindow: () => Promise<void>;
  closeWindow: () => Promise<void>;
  getPathForFile: (file: File) => string;
  openFileDialog: (options?: {
    title?: string;
    filters?: { name: string; extensions: string[] }[];
  }) => Promise<string | null>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
