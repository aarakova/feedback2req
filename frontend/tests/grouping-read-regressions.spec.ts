import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { authenticatedHeaders, password } from './helpers';
import { groupStateHref, runHref } from '../src/routes';
import type { GroupDetailDTO } from '../src/grouping/ProjectGroups';

interface SavedGroups {
  login: string; projectId: string; groupId: string;
  historicalStateId: string; currentStateId: string; groupRunId: string;
}
async function openSavedGroup(page: Page) {
  const data: SavedGroups = JSON.parse(readFileSync(resolve('..', '.local/workflow/groups.json'), 'utf8'));
  await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(data.login);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
  await page.goto('/' + groupStateHref(data.projectId, data.groupId, data.historicalStateId));
  const exact = page.getByRole('region', { name: 'Точное состояние группы', exact: true });
  await expect(exact).toContainText('Synthetic opposed positions');
  return { data, exact };
}

// FR-011, FR-021 / AC-04, AC-07: saved groups keep their exact source evidence.
test('saved group traces its exact fragment and source state without implicitly starting any task', async ({ page }) => {
  const commands: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/v1\/projects\/[^/]+\/runs$/.test(new URL(request.url()).pathname)) commands.push(request.url());
  });
  const { data, exact } = await openSavedGroup(page);
  const root = `/api/v1/projects/${data.projectId}`;
  const response = await page.request.get(`${root}/groups/${data.groupId}/states/${data.historicalStateId}`);
  expect(response.status()).toBe(200); const group: GroupDetailDTO = await response.json();
  const memberIndex = group.members.findIndex(member => member.finding.evidence.some(item => item.quote.includes('ё🙂\r\n')));
  expect(memberIndex).toBeGreaterThanOrEqual(0);
  const evidenceIndex = group.members[memberIndex].finding.evidence.findIndex(item => item.quote.includes('ё🙂\r\n'));
  const evidence = group.members[memberIndex].finding.evidence[evidenceIndex];
  await exact.locator('.finding-card').nth(memberIndex).getByRole('link', { name: 'Открыть точное состояние фрагмента', exact: false }).nth(evidenceIndex).click();
  const fragment = page.getByRole('region', { name: 'Точное состояние исходного фрагмента', exact: true });
  await expect(fragment).toContainText(evidence.state_id);
  await expect(fragment).toContainText('Цитата точно соответствует границам');
  await expect(fragment).toContainText('Синтетический результат');
  await fragment.getByRole('link', { name: 'Перейти к исходному материалу', exact: true }).click();
  const sourceResponse = await page.request.get(`${root}/sources/${evidence.source_ref.id}`);
  expect(sourceResponse.status()).toBe(200); const source = await sourceResponse.json();
  expect(source.state_id).toBe(evidence.source_ref.state_id);
  expect(Array.from(source.text).slice(evidence.locator.start, evidence.locator.end).join('')).toBe(evidence.quote);
  const text = page.getByRole('region', { name: 'Просмотр материала', exact: true }).getByLabel('Сохранённый текст');
  await expect(text).toBeVisible(); expect(await text.textContent()).toBe(source.text);
  await page.reload(); await expect(text).toBeVisible(); expect(await text.textContent()).toBe(source.text);
  expect(commands).toEqual([]);
});

// FR-032 / AC-01: an expired session removes already displayed project data.
test('expired session on group refresh removes group evidence and project identity', async ({ page }) => {
  const { data } = await openSavedGroup(page);
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await page.getByRole('button', { name: 'Обновить группы', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Точное состояние группы', exact: true })).toHaveCount(0);
  await expect(page.locator('main')).not.toContainText('Synthetic opposed positions');
  await expect(page.locator('main')).not.toContainText(data.historicalStateId);
  await expect(page.getByRole('navigation', { name: 'Разделы проекта', exact: true })).toHaveCount(0);
});

// FR-022/023 / AC-07: a current group is never presented as the old AI state.
test('saved run labels current group links while historical evidence remains separately addressable', async ({ page }) => {
  const { data } = await openSavedGroup(page);
  await page.goto('/' + runHref(data.projectId, data.groupRunId));
  const run = page.getByRole('region', { name: 'Выбранное задание', exact: true });
  await expect(run).toContainText('Синтетический результат группировки');
  await run.getByRole('link', { name: `Текущее состояние группы ${data.groupId}`, exact: false }).click();
  const current = page.getByRole('region', { name: 'Выбранная группа', exact: true });
  await expect(current).toContainText('Later human state');
  await expect(current).toContainText(data.currentStateId);
  await expect(current).not.toContainText('Synthetic opposed positions');
  await current.getByRole('link', { name: 'Предыдущее состояние', exact: false }).click();
  const historical = page.getByRole('region', { name: 'Точное состояние группы', exact: true });
  await expect(historical).toContainText('Synthetic opposed positions');
  await expect(historical).toContainText(data.historicalStateId);
});
