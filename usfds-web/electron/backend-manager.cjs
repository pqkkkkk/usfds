const http = require('http');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

class BackendManager {
  constructor(options = {}) {
    this.port = options.port || 8000;
    this.host = options.host || '127.0.0.1';
    this.healthUrl = `http://${this.host}:${this.port}/health`;
    this.serverDir = options.serverDir || path.resolve(__dirname, '../../usfds-server');
    this.serverProcess = null;
    this.isExternal = false;
  }

  /**
   * Check if backend is already listening and responsive
   */
  async checkHealth(timeoutMs = 1500) {
    return new Promise((resolve) => {
      const req = http.get(this.healthUrl, { timeout: timeoutMs }, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 400) {
          resolve(true);
        } else {
          resolve(false);
        }
      });

      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  /**
   * Wait until the backend is healthy or timeout is reached
   */
  async waitForHealthy(maxWaitMs = 30000, intervalMs = 1000) {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWaitMs) {
      const isHealthy = await this.checkHealth(1200);
      if (isHealthy) {
        return true;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
  }

  /**
   * Start the backend process if not already running
   */
  async start() {
    const alreadyRunning = await this.checkHealth();
    if (alreadyRunning) {
      console.log(`[BackendManager] USFDS backend already running on ${this.healthUrl}.`);
      this.isExternal = true;
      return { success: true, external: true };
    }

    console.log(`[BackendManager] Starting USFDS backend from: ${this.serverDir}`);

    // Verify server directory exists
    if (!fs.existsSync(this.serverDir)) {
      console.warn(`[BackendManager] Server directory not found at: ${this.serverDir}`);
    }

    // Try starting via poetry run usfds-server
    try {
      this.serverProcess = spawn('poetry', ['run', 'usfds-server'], {
        cwd: this.serverDir,
        shell: true,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      this.isExternal = false;

      this.serverProcess.stdout.on('data', (data) => {
        const text = data.toString().trim();
        if (text) console.log(`[Python Server] ${text}`);
      });

      this.serverProcess.stderr.on('data', (data) => {
        const text = data.toString().trim();
        if (text) console.error(`[Python Server (err)] ${text}`);
      });

      this.serverProcess.on('exit', (code, signal) => {
        console.log(`[BackendManager] Python server exited with code: ${code}, signal: ${signal}`);
        this.serverProcess = null;
      });

      console.log(`[BackendManager] Backend spawned (PID: ${this.serverProcess.pid}). Waiting for health check...`);
      const ready = await this.waitForHealthy(30000, 1000);

      if (ready) {
        console.log(`[BackendManager] Backend is ready and responding at ${this.healthUrl}!`);
        return { success: true, external: false };
      } else {
        console.warn(`[BackendManager] Backend did not respond within timeout, but process was started.`);
        return { success: false, external: false, error: 'Timeout waiting for backend' };
      }
    } catch (err) {
      console.error(`[BackendManager] Failed to spawn backend process:`, err);
      return { success: false, external: false, error: err.message };
    }
  }

  /**
   * Stop the backend process if it was started by this manager
   */
  async stop() {
    if (this.isExternal) {
      console.log(`[BackendManager] Backend was started externally. Leaving it running.`);
      return;
    }

    if (!this.serverProcess || !this.serverProcess.pid) {
      return;
    }

    console.log(`[BackendManager] Stopping backend process (PID: ${this.serverProcess.pid})...`);
    const pid = this.serverProcess.pid;

    if (process.platform === 'win32') {
      try {
        exec(`taskkill /pid ${pid} /T /F`, (err) => {
          if (err) {
            console.warn(`[BackendManager] taskkill error (process might have already exited):`, err.message);
          } else {
            console.log(`[BackendManager] Backend process tree killed successfully.`);
          }
        });
      } catch (e) {
        console.warn(`[BackendManager] Error terminating process:`, e);
      }
    } else {
      try {
        this.serverProcess.kill('SIGTERM');
      } catch (e) {
        console.warn(`[BackendManager] Error killing process:`, e);
      }
    }

    this.serverProcess = null;
  }
}

module.exports = { BackendManager };
