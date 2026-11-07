import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createProject, password, registerAndLogin } from './helpers';
import { groupHref, groupStateHref, projectHref, runHref } from '../src/routes';

interface Seed {
  login: string; projectId: string; groupId: string; historicalStateId: string; currentStateId: string;
  groupRunId: string; ungroupedRunId: string; queuedRunId: string;
}
const seed = (): Seed => JSON.parse(readFileSync(resolve('..', '.local/workflow/groups.json'), 'utf8'));
async function login(page: Page, data: Seed) {
  await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(data.login);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
}
test('saved groups paginate and exact historical conflict preserves every position and source quote', async ({ page }) => {
  const data = seed(); await login(page, data);
  await page.goto('/' + projectHref(data.projectId, 'findings'));
  const groups = page.getByRole('region', { name: 'Группы находок', exact: true });
  await expect(groups.locator('.group-card')).toHaveCount(2);
  await expect(groups).toContainText('Показана часть списка');
  await groups.getByRole('button', { name: 'Показать ещё группы', exact: true }).click();
  await expect(groups.locator('.group-card')).toHaveCount(4);
  await page.goto('/' + groupStateHref(data.projectId, data.groupId, data.historicalStateId));
  const exact = page.getByRole('region', { name: 'Точное состояние группы', exact: true });
  await expect(exact).toContainText('Synthetic opposed positions');
  await expect(exact.getByRole('region', { name: 'Конфликтующие позиции', exact: true }).locator('.conflict-pair > div')).toHaveCount(2);
  await expect(exact).toContainText('Синтетический результат группировки');
  await expect(exact).toContainText('Синтетический вопрос группировки');
  await expect(exact).toContainText(data.historicalStateId);
  await expect(exact.locator('.finding-card')).toHaveCount(3);
  await expect(exact).toContainText('СИНТЕТИЧЕСКИЙ ТЕСТ: отправлять');
  await page.reload(); await expect(exact).toContainText('Synthetic opposed positions');
  await page.goto('/' + groupHref(data.projectId, data.groupId));
  const current = page.getByRole('region', { name: 'Выбранная группа', exact: true });
  await expect(current).toContainText('Later human state'); await expect(current).toContainText(data.currentStateId);
  await expect(current).not.toContainText('Synthetic opposed positions');
  await current.getByRole('link', { name: 'Предыдущее состояние', exact: false }).click();
  await expect(exact).toContainText('Synthetic opposed positions');
});
test('real worker F3 and successful ungrouped results remain distinct from F1 and expose no retry', async ({ page }) => {
  const data = seed(); await login(page, data);
  const root = `/api/v1/projects/${data.projectId}`;
  await expect.poll(async () => (await (await page.request.get(root + '/runs/' + data.queuedRunId)).json()).state, { timeout: 45000 }).toBe('completed');
  await page.goto('/' + runHref(data.projectId, data.queuedRunId));
  const run = page.getByRole('region', { name: 'Выбранное задание', exact: true });
  await expect(run).toContainText('Группировка находок'); await expect(run).toContainText('Синтетический результат группировки');
  await expect(run.getByRole('link', { name: 'Текущее состояние группы', exact: false })).toHaveCount(2);
  await expect(run.getByRole('button', { name: 'Повторить неудачную операцию', exact: true })).toHaveCount(0);
  await page.goto('/' + runHref(data.projectId, data.ungroupedRunId));
  await expect(run).toContainText('Попытка принята без групп');
  await expect(run.getByRole('heading', { name: 'Негруппированные находки этой попытки', exact: true })).toBeVisible();
  await expect(run).toContainText('Завершено');
  await expect(run.getByRole('link', { name: 'Текущее состояние группы', exact: false })).toHaveCount(0);
  const response = await page.request.get(root + '/runs/' + data.ungroupedRunId);
  const result = await response.json(); expect(result.units[0].attempt.grouping_result.ungrouped_findings).toHaveLength(3);
});
test('group 503 is a recoverable read failure and outsider receives no saved group content', async ({ page }) => {
  const data = seed(); await login(page, data);
  const path = `**/api/v1/projects/${data.projectId}/groups/${data.groupId}/states/${data.historicalStateId}`;
  await page.route(path, route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":{"code":"unavailable","message":"Unavailable","details":{}}}' }));
  await page.goto('/' + groupStateHref(data.projectId, data.groupId, data.historicalStateId));
  const exact = page.getByRole('region', { name: 'Точное состояние группы', exact: true });
  await expect(exact.getByRole('alert')).toBeVisible(); await expect(exact).not.toContainText('Synthetic opposed positions');
  await page.unroute(path); await exact.getByRole('button', { name: 'Повторить загрузку группы', exact: true }).click();
  await expect(exact).toContainText('Synthetic opposed positions');
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await registerAndLogin(page); const own = await createProject(page, 'Другая граница проекта');
  const denied = await page.request.get(`/api/v1/projects/${own.id}/groups/${data.groupId}/states/${data.historicalStateId}`);
  expect(denied.status()).toBe(404); expect(await denied.text()).not.toContain('Synthetic opposed positions');
  await page.goto('/' + groupStateHref(own.id, data.groupId, data.historicalStateId));
  await expect(page.locator('main')).not.toContainText('Synthetic opposed positions');
});
test('late group response cannot restore prior project content after navigation', async ({ page }) => {
  const data = seed(); await login(page, data);
  const other = await createProject(page, 'Группы · граница позднего ответа');
  let release!: () => void; let captured!: () => void;
  const hold = new Promise<void>(resolve => { release = resolve; });
  const fetched = new Promise<void>(resolve => { captured = resolve; });
  const path = `**/api/v1/projects/${data.projectId}/groups/${data.groupId}/states/${data.historicalStateId}`;
  await page.route(path, async route => {
    const response = await route.fetch(); captured(); await hold;
    await route.fulfill({ response }).catch(() => {});
  });
  try {
    await page.goto('/' + groupStateHref(data.projectId, data.groupId, data.historicalStateId));
    await fetched;
    await page.goto('/' + projectHref(other.id, 'findings'));
    await expect(page.getByRole('heading', { name: other.name, exact: true })).toBeVisible();
    release(); await page.waitForTimeout(300);
    await expect(page.locator('main')).not.toContainText('Synthetic opposed positions');
    await expect(page.getByRole('region', { name: 'Группы находок', exact: true })).toContainText('Сохранённых групп в этой выборке нет');
  } finally { release(); }
});
test('synthetic saved conflict fits all four Observer widths and exports unmasked evidence', async ({ page }) => {
  test.setTimeout(90000); const data = seed(); await login(page, data);
  const destination = resolve('..', 'docs/qa/full-workflow'); mkdirSync(destination, { recursive: true });
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/' + groupStateHref(data.projectId, data.groupId, data.historicalStateId));
    const exact = page.getByRole('region', { name: 'Точное состояние группы', exact: true });
    await expect(exact).toContainText('Synthetic opposed positions');
    await expect(exact.locator('.finding-card')).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: resolve(destination, `synthetic-group-${width}.png`), fullPage: true, animations: 'disabled' });
  }
});
