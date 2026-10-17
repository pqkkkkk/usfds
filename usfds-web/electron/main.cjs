const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { BackendManager } = require('./backend-manager.cjs');

let mainWindow = null;
const backendManager = new BackendManager();

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'USFDS - US Fraud Detection System',
    backgroundColor: '#030712',
    show: false, // Show when ready to prevent flicker
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  });

  // Remove default menu for a clean desktop feel
  mainWindow.setMenuBarVisibility(false);

  // Show window once DOM is ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle opening external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // Determine whether to load dev server or built bundle
  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  const isDev = !app.isPackaged || process.env.NODE_ENV === 'development';

  if (devServerUrl) {
    console.log(`[Electron] Loading Vite Dev Server at ${devServerUrl}`);
    await mainWindow.loadURL(devServerUrl);
  } else if (isDev && process.env.ELECTRON_LOAD_DEV === '1') {
    console.log(`[Electron] Loading default dev server http://127.0.0.1:5173`);
    await mainWindow.loadURL('http://127.0.0.1:5173');
  } else {
    const indexPath = path.join(__dirname, '../dist/index.html');
    console.log(`[Electron] Loading production file at ${indexPath}`);
    await mainWindow.loadFile(indexPath);
  }

  // Open DevTools in development if requested
  if (process.env.ELECTRON_OPEN_DEVTOOLS === '1') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('app:get-backend-status', async () => {
  const isHealthy = await backendManager.checkHealth();
  return {
    healthy: isHealthy,
    url: backendManager.healthUrl,
    external: backendManager.isExternal,
  };
});

ipcMain.handle('window:minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.handle('window:maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('window:close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('dialog:open-file', async (_event, options = {}) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: options.title || 'Select Transaction Dataset File',
    properties: ['openFile'],
    filters: options.filters || [
      { name: 'Dataset Files', extensions: ['csv', 'parquet', 'json', 'tsv'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

// App Lifecycle
app.whenReady().then(async () => {
  console.log('[Electron] App starting. Initializing backend service...');
  try {
    // Start backend in background (won't block UI if already running)
    backendManager.start().catch((err) => {
      console.error('[Electron] Backend startup warning:', err);
    });
  } catch (err) {
    console.error('[Electron] Error during backend initialization:', err);
  }

  await createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Ensure backend is killed on quit
app.on('before-quit', async () => {
  console.log('[Electron] App closing. Terminating child processes...');
  await backendManager.stop();
});
