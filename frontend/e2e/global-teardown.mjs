import { execFileSync } from 'node:child_process';
import { rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export default async function globalTeardown() {
  const runId = process.env.PETROTWIN_E2E_RUN_ID;
  if (!runId) return;
  const pidFile = join(tmpdir(), `petrotwin-e2e-${runId}.json`);
  try {
    const processes = JSON.parse(readFileSync(pidFile, 'utf8'));
    for (const pid of [processes.frontend, processes.backend]) {
      if (!Number.isInteger(pid)) continue;
      try { execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* already stopped */ }
    }
    for (const suffix of ['', '-shm', '-wal']) rmSync(`${processes.database}${suffix}`, { force: true });
  } finally {
    rmSync(pidFile, { force: true });
  }
}
