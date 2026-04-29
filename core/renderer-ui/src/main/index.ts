import { app, BrowserWindow } from 'electron';
import path from 'path';
import fs from 'fs';
import { createMainWindow } from './window-manager';
import { registerIPCHandlers, disconnectKernel } from './ipc-handlers';

// Dev mode only if explicitly running with VITE_DEV=1 (from dev:electron script)
const isDev = process.env.VITE_DEV === '1';

function loadContent(win: BrowserWindow): void {
  if (isDev) {
    win.loadURL('http://localhost:5173');
    win.webContents.openDevTools({ mode: 'detach' });
  } else {
    const htmlPath = path.join(__dirname, '..', 'renderer', 'index.html');
    if (fs.existsSync(htmlPath)) {
      win.loadFile(htmlPath);
    } else {
      console.error('[renderer-ui] dist/renderer/index.html not found. Run pnpm run build first.');
    }
  }
}

app.whenReady().then(() => {
  const win = createMainWindow();
  registerIPCHandlers(win);
  loadContent(win);
});

app.on('window-all-closed', () => {
  disconnectKernel();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    const win = createMainWindow();
    registerIPCHandlers(win);
    loadContent(win);
  }
});
