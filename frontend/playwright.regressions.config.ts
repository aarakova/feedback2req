import { defineConfig } from '@playwright/test';
import base from './playwright.config';

// Explicit opt-in only: known failing AUD regressions must not join normal tests/.
export default defineConfig({ ...base, testDir: './regressions' });
