import { BrowserWindow, screen } from 'electron';
import path from 'path';

let mainWindow: BrowserWindow | null = null;

export function createMainWindow(): BrowserWindow {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 400,
    height: 700,
    x: screenWidth - 450,
    y: screenHeight - 750,
    transparent: true,
    frame: false,
    hasShadow: false,
    resizable: false,
    skipTaskbar: false,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.setIgnoreMouseEvents(false);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}
