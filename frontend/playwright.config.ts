import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const built = process.env.F2R_E2E_MODE === 'built';
const origin = built ? 'http://localhost:18000' : 'http://localhost:5173';
const python = resolve('..', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!process.env.F2R_TEST_DATABASE_URL) throw new Error('Set F2R_TEST_DATABASE_URL to a dedicated PostgreSQL test database.');

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
  webServer: [
    {
      command: `"${existsSync(python) ? python : 'python'}" ../scripts/serve_frontend_test.py`,
      url: 'http://127.0.0.1:18000/api/v1/auth/session',
      env: { F2R_E2E_ORIGIN: origin },
      reuseExistingServer: false,
    },
    ...built ? [] : [{
      command: 'npm run dev',
      url: origin,
      env: { F2R_API_PROXY_TARGET: 'http://127.0.0.1:18000' },
      reuseExistingServer: false,
    }],
  ],
});
