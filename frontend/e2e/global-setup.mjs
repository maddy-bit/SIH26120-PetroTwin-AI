import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(fileURLToPath(new URL('..', import.meta.url)));
const root = resolve(frontend, '..');
const python = resolve(root, '.venv', 'Scripts', 'python.exe');
const viteCli = resolve(frontend, 'node_modules', 'vite', 'bin', 'vite.js');
const runId = process.env.PETROTWIN_E2E_RUN_ID;
const pidFile = join(tmpdir(), `petrotwin-e2e-${runId}.json`);
const apiPort = process.env.PETROTWIN_E2E_API_PORT;
const frontendPort = process.env.PETROTWIN_E2E_FRONTEND_PORT;

export default async function globalSetup() {
const backend = spawn(python, ['-m', 'uvicorn', 'ml_service.main:app', '--app-dir', root, '--host', '127.0.0.1', '--port', apiPort], {
  cwd: root, env: { ...process.env, DATABASE_URL: process.env.PETROTWIN_E2E_DATABASE_URL, PETROTWIN_DATA_MODE: 'simulation', CORS_ORIGINS: process.env.PETROTWIN_E2E_FRONTEND_URL },
  detached: true, windowsHide: true, stdio: 'ignore',
});
const frontendServer = spawn(process.execPath, [viteCli, '--host', '127.0.0.1', '--port', frontendPort, '--strictPort'], {
  cwd: frontend, env: { ...process.env, VITE_API_URL: process.env.PETROTWIN_E2E_API_URL },
  detached: true, windowsHide: true, stdio: 'ignore',
});
writeFileSync(pidFile, JSON.stringify({ backend: backend.pid, frontend: frontendServer.pid, database: process.env.PETROTWIN_E2E_DB_PATH }));

async function waitFor(url, label) {
  const deadline = Date.now() + 60_000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = new Error(`${label} returned HTTP ${response.status}`);
    } catch (error) { lastError = error; }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`${label} did not become ready: ${lastError}`);
}

try {
  await Promise.all([
    waitFor(`${process.env.PETROTWIN_E2E_API_URL}/health`, 'FastAPI'),
    waitFor(process.env.PETROTWIN_E2E_FRONTEND_URL, 'Vite'),
  ]);
} catch (error) {
  process.stderr.write(`${error}\n`);
  process.exitCode = 1;
}
}
