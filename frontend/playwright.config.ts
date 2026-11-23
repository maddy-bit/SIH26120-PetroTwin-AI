import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = fileURLToPath(new URL('.', import.meta.url));
const repoRoot = resolve(frontendDir, '..');
const databasePath = join(tmpdir(), `petrotwin-playwright-${process.pid}.sqlite3`);
const databaseUrl = `sqlite:///${databasePath.replace(/\\/g, '/')}`;
const apiPort = 47541;
const frontendPort = 47542;
const apiUrl = `http://127.0.0.1:${apiPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

process.env.PETROTWIN_E2E_DB_PATH = databasePath;
process.env.PETROTWIN_E2E_API_URL = apiUrl;
process.env.PETROTWIN_E2E_API_PORT = String(apiPort);
process.env.PETROTWIN_E2E_FRONTEND_PORT = String(frontendPort);
process.env.PETROTWIN_E2E_FRONTEND_URL = frontendUrl;
process.env.PETROTWIN_E2E_DATABASE_URL = databaseUrl;
process.env.PETROTWIN_E2E_RUN_ID = String(process.pid);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: frontendUrl,
    browserName: 'chromium',
    channel: 'chrome',
    headless: true,
    trace: 'retain-on-failure',
  },
  globalSetup: './e2e/global-setup.mjs',
  globalTeardown: './e2e/global-teardown.mjs',
});
