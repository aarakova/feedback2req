import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createProject, registerAndLogin } from './helpers';

const deployed = ['compose', 'built'].includes(process.env.F2R_E2E_MODE ?? '');
const projectId = '11111111-1111-4111-8111-111111111111';
const fixture = (state = 'ready', extra = '') => `/tests/fixtures/observer.html?section=overview&state=${state}${extra}`;
const shots = resolve('..', 'docs', 'qa', 'observer-overview');

test.describe('isolated overview data', () => {
  test.skip(deployed, 'The marked fixture is intentionally excluded from production.');

  for (const [selector, index, filter, count] of [
    ['.metric', 0, 'all', 4], ['.metric', 1, 'approved', 2], ['.metric', 2, 'blocker', 1], ['.metric', 3, 'lost', 2],
    ['.decision-category', 0, 'draft', 1], ['.decision-category', 1, 'approved', 2], ['.decision-category', 2, 'rejected', 1],
    ['.availability-row', 0, 'approved_all', 0], ['.availability-row', 1, 'approved_partial', 1], ['.availability-row', 2, 'approved_lost', 1],
  ] as const) {
    test(`${selector} ${index} opens ${filter} and restores its selection after reload`, async ({ page }) => {
      await page.goto(fixture());
      const link = page.locator(`.observer-overview ${selector}`).nth(index);
      await expect(link).toHaveAttribute('href', `#/projects/${projectId}/requirements?filter=${filter}`);
      await link.focus(); await page.keyboard.press('Enter');
      await expect(page).toHaveURL(new RegExp(`requirements\\?filter=${filter}$`));
      await expect(page.getByLabel('Фильтр требований')).toHaveValue(filter);
      await expect(page.locator('.requirement-register .req-row')).toHaveCount(count);
      await page.reload();
      await expect(page.getByLabel('Фильтр требований')).toHaveValue(filter);
      await expect(page.locator('.requirement-register .req-row')).toHaveCount(count);
    });
  }

  test('group and attention links open the selected details in the same project', async ({ page }) => {
    await page.goto(fixture());
    const group = page.locator('.group-summary');
    await expect(group).toContainText('Находок: 2');
    await expect(group).toContainText('Требований: 2');
    await expect(group).toContainText('Открытых замечаний: 2');
    await expect(group.locator('.group-bar>span')).toHaveAttribute('style', 'width: 100%;');
    await group.click();
    await expect(page).toHaveURL(/findings\/groups\/G-01$/);
    await expect(page.getByRole('region', { name: 'Состав группы', exact: true })).toContainText('Нужно автоматическое сохранение.');
    await page.reload();
    await expect(page.getByRole('region', { name: 'Состав группы', exact: true })).toContainText('Нужно автоматическое сохранение.');
    await page.goto(fixture());
    const attention = page.getByRole('region', { name: 'Нуждается во внимании', exact: true });
    await expect(attention).toContainText('Открыт блокер');
    await expect(attention).toContainText('Открытых замечаний: 2');
    await expect(attention).toContainText('Проверка: Актуальна');
    await attention.getByRole('link').filter({ hasText: 'REQ-04' }).click();
    await expect(page).toHaveURL(/requirements\/REQ-04$/);
    await expect(page.getByRole('region', { name: 'Карточка выбранного требования', exact: true })).toContainText('Историческое утверждение сохранено.');
  });

  for (const mode of ['loading', 'error', 'empty', 'unavailable', 'partial', 'partial_empty', 'invalid_counts']) {
    test(`${mode}: unknown values never create fake metrics or filter links`, async ({ page }) => {
      await page.goto(fixture(mode));
      await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
      await expect(page.locator('.metric-grid a, .decision-legend a')).toHaveCount(0);
      if (mode !== 'invalid_counts') await expect(page.locator('a.availability-row')).toHaveCount(0);
      await expect(page.locator('.donut-center strong')).toHaveText('—');
      if (mode === 'error') await expect(page.getByRole('alert')).toContainText('Тестовая ошибка загрузки');
      if (mode === 'loading') await expect(page.getByRole('status')).toContainText('Загружаем данные раздела');
      if (mode === 'partial_empty') {
        await expect(page.getByText('Сведения об открытых случаях пока не получены.', { exact: true })).toBeVisible();
        await expect(page.getByText('Открытых случаев в полученной выборке нет.', { exact: true })).toHaveCount(0);
      }
      if (mode === 'empty') await expect(page.getByText('Открытых случаев в полученной выборке нет.', { exact: true })).toBeVisible();
    });
  }

  test('explicit zero remains actionable and opens an actually empty selection', async ({ page }) => {
    await page.goto(fixture('zero'));
    await expect(page.locator('.metric-value')).toHaveText(['0', '0', '0', '0']);
    await expect(page.locator('.metric-grid a')).toHaveCount(4);
    await expect(page.locator('.decision-legend a, a.availability-row')).toHaveCount(6);
    await expect(page.locator('.decision-donut svg circle')).toHaveCount(1);
    await expect(page.getByText('Открытых случаев в полученной выборке нет.', { exact: true })).toBeVisible();
    await page.locator('a.availability-row').first().click();
    await expect(page.getByLabel('Фильтр требований')).toHaveValue('approved_all');
    await expect(page.locator('.requirement-register .req-row')).toHaveCount(0);
  });

  test('missing group counts and issue coverage stay unknown and lost is restricted to Approved', async ({ page }) => {
    await page.goto(fixture('unknown_counts'));
    await expect(page.locator('.group-counts')).toHaveText('Находок: —Требований: —Открытых замечаний: —');
    await expect(page.getByRole('img', { name: 'Относительное количество находок неизвестно' })).toBeVisible();
    await expect(page.locator('.group-bar-unknown')).toHaveCount(1);
    await expect(page.getByRole('region', { name: 'Нуждается во внимании', exact: true })).toContainText('Блокеры: —');
    await page.goto(fixture('relative_scale'));
    await expect(page.locator('.group-bar>span')).toHaveAttribute('style', 'width: 50%;');
    await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
    await page.goto(fixture('mixed_loss'));
    await page.locator('.metric').nth(3).click();
    await expect(page.locator('.requirement-register .req-row')).toHaveCount(2);
    await expect(page.locator('.requirement-register')).not.toContainText('REQ-01');
  });

  test('project scope rejects all overview links and data from another project', async ({ page }) => {
    await page.goto(fixture('ready', '&scope=wrong'));
    await expect(page.getByText('Данные другого проекта не отображаются.', { exact: true })).toBeVisible();
    await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
    await expect(page.locator('.metric-grid a, .decision-legend a, a.availability-row, .group-summary')).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Нуждается во внимании', exact: true }).getByRole('link')).toHaveCount(0);
  });

  for (const width of [1440, 1280, 390, 320]) {
    test(`long Unicode labels and keyboard focus fit ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(fixture('long_names'));
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const link = page.locator('.metric').first(); await link.focus();
      await expect(link).toBeFocused();
      expect(await link.evaluate(element => getComputedStyle(element).outlineStyle)).toBe('solid');
      await page.keyboard.press('Enter');
      await expect(page.getByLabel('Фильтр требований')).toHaveValue('all');
    });
  }

  test('overview reference comparison exports ready and unavailable compositions at all four sizes', async ({ page, context }) => {
    test.setTimeout(90000); mkdirSync(shots, { recursive: true });
    const reference = await context.newPage();
    await reference.route('**/__overview_reference__', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: readFileSync(resolve('..', 'prototype', 'index.html'), 'utf8') }));
    await reference.goto('/__overview_reference__');
    try {
      for (const width of [1440, 1280, 390, 320]) {
        await page.setViewportSize({ width, height: 900 }); await reference.setViewportSize({ width, height: 900 });
        await reference.locator('[data-action="navigate"][data-view="analytics"]:visible').first().click();
        await reference.locator('#app').screenshot({ path: resolve(shots, `reference-${width}.png`), animations: 'disabled' });
        for (const mode of ['ready', 'unavailable']) {
          await page.goto(fixture(mode)); await page.mouse.move(0, 0);
          await expect(page.locator('.metric')).toHaveCount(4);
          await expect(page.locator('.observer-overview>.observer-twos')).toHaveCount(2);
          expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
          const appWidth = await page.locator('.metric').first().evaluate(element => element.getBoundingClientRect().width);
          const refWidth = await reference.locator('.metric').first().evaluate(element => element.getBoundingClientRect().width);
          expect(Math.abs(appWidth - refWidth)).toBeLessThanOrEqual(1);
          const appDonut = await page.locator('.decision-donut').evaluate(element => element.getBoundingClientRect().width);
          const refDonut = await reference.locator('.donut').evaluate(element => element.getBoundingClientRect().width);
          expect(appDonut).toBe(refDonut);
          await page.screenshot({ path: resolve(shots, `fixture-${mode}-${width}.png`), fullPage: true, animations: 'disabled' });
          await expect(page).toHaveScreenshot(`overview-${mode}-${width}.png`, { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.001 });
        }
      }
    } finally { await reference.close(); }
  });
});

test('real project filter routes survive reload, reject invalid filters and never call an unsupported F2 API', async ({ page }) => {
  await registerAndLogin(page);
  const first = await createProject(page, 'Обзор → фильтры 🧭');
  const second = await createProject(page, 'Другой проект');
  const semantic: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && /\/(requirements|groups)(\/|$)/.test(new URL(request.url()).pathname)) semantic.push(request.url()); });
  await page.goto(`/#/projects/${first.id}`);
  await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
  await expect(page.locator('.metric-grid a, .decision-legend a, a.availability-row')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Возможности проекта', exact: true })).toContainText('Доступно');
  for (const filter of ['all', 'approved', 'blocker', 'lost', 'draft', 'rejected', 'approved_all', 'approved_partial', 'approved_lost']) {
    await page.goto(`/#/projects/${first.id}/requirements?filter=${filter}`); await page.reload();
    await expect(page.getByLabel('Фильтр требований')).toHaveValue(filter);
    await expect(page.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  }
  await page.goto(`/#/projects/${second.id}/requirements?filter=approved`);
  await expect(page.getByRole('heading', { name: second.name, exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: first.name, exact: true })).toHaveCount(0);
  for (const suffix of ['requirements?filter=bogus', 'requirements?filter=all&filter=lost', 'materials?filter=all', 'requirements?filter=all&extra=1']) {
    await page.goto(`/#/projects/${second.id}/${suffix}`);
    await expect(page.getByRole('heading', { name: 'Страница не найдена', exact: true })).toBeVisible();
  }
  expect(semantic).toEqual([]);
});
