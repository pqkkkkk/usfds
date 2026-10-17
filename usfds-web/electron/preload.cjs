const { contextBridge, ipcRenderer, shell, webUtils } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  platform: process.platform,
  checkBackendStatus: () => ipcRenderer.invoke('app:get-backend-status'),
  openExternalUrl: (url) => shell.openExternal(url),
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),

  // Modern Electron API to get native filesystem path of an HTML5 File object
  getPathForFile: (file) => {
    try {
      if (webUtils && typeof webUtils.getPathForFile === 'function') {
        return webUtils.getPathForFile(file);
      }
      return file.path || '';
    } catch (e) {
      console.warn('[electronAPI] getPathForFile error:', e);
      return file.path || '';
    }
  },

  // Open native system file picker dialog
  openFileDialog: (options) => ipcRenderer.invoke('dialog:open-file', options),
});
