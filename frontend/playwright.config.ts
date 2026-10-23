import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const deployed = ['compose', 'built'].includes(process.env.F2R_E2E_MODE ?? '');
const origin = deployed ? (process.env.F2R_E2E_BASE_URL ?? 'http://localhost:18080') : 'http://localhost:5173';
const python = resolve('..', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const externalApi = process.env.F2R_E2E_API_EXTERNAL === 'true';
if (!deployed && !externalApi && !process.env.F2R_TEST_DATABASE_URL) throw new Error('Set F2R_TEST_DATABASE_URL to a dedicated PostgreSQL test database.');

export default defineConfig({
  testDir: './tests',
  workers: 1,
  retries: 0,
  use: {
    baseURL: origin,
    ...devices['Desktop Chrome'],
    channel: process.env.F2R_BROWSER_CHANNEL,
    // Traces can contain submitted credentials and cookie headers; do not record them.
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  webServer: deployed ? (process.env.F2R_E2E_TUNNEL ? [{
    command: 'node ../scripts/forward_test_port.mjs',
    url: origin,
    reuseExistingServer: false,
  }] : []) : [
    ...externalApi ? [] : [{
      command: `"${existsSync(python) ? python : 'python'}" ../scripts/serve_frontend_test.py`,
      url: 'http://127.0.0.1:18000/api/v1/auth/session',
      env: { F2R_E2E_ORIGIN: origin },
      reuseExistingServer: false,
    }],
    {
      command: 'npm run dev',
      url: origin,
      // Test servers have no interactive stdin; Vite must not exit when that pipe closes.
      env: { F2R_API_PROXY_TARGET: process.env.F2R_API_PROXY_TARGET ?? 'http://127.0.0.1:18000', CI: 'true' },
      reuseExistingServer: false,
    },
  ],
});
