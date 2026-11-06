import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { authenticatedHeaders, createProject, registerAndLogin } from './helpers';

const deployed = ['compose', 'built'].includes(process.env.F2R_E2E_MODE ?? '');
const screenshots = resolve('..', 'docs', 'qa', 'observer-v3', 'screenshots');
const paletteKeys = ['--bg', '--surface', '--ink', '--muted', '--line', '--accent', '--draft', '--approved', '--rejected', '--radius'];
const stableStyle = resolve('tests', 'fixtures', 'visual-mask.css');
const sections = [
  ['overview', 'analytics'], ['materials', 'materials'], ['findings', 'findings'],
  ['requirements', 'requirements'], ['processing', 'processing'], ['access', 'access'],
] as const;

test('Observer visual compositions match reference palette and keep responsive screenshot baselines', async ({ page, context }, testInfo) => {
  test.setTimeout(180000);
  mkdirSync(screenshots, { recursive: true });
  await registerAndLogin(page);
  const project = await createProject(page, 'Сервис заявок');
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  expect((await page.request.post(`/api/v1/projects/${project.id}/sources`, {
    headers, data: { kind: 'text', text: 'Синтетический отзыв: нужно сохранять изменения без потери текста.' },
  })).status()).toBe(201);
  expect((await page.request.post(`/api/v1/projects/${project.id}/documents`, {
    headers, data: { title: 'Описание сервиса заявок', text: 'Синтетическая документация продукта. Контекст, не самостоятельная потребность.' },
  })).status()).toBe(201);

  const reference = await context.newPage();
  await reference.route('**/__observer_reference__', route => route.fulfill({
    contentType: 'text/html; charset=utf-8', body: readFileSync(resolve('..', 'prototype', 'index.html'), 'utf8'),
  }));
  await reference.goto('/__observer_reference__');
  try {
    for (const width of [1440, 1280, 390, 320]) {
      await page.setViewportSize({ width, height: 900 }); await reference.setViewportSize({ width, height: 900 });
      for (const [section, prototypeView] of sections) {
        await page.goto(`/#/projects/${project.id}${section === 'overview' ? '' : `/${section}`}`);
        await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible();
        if (section === 'overview') await expect(page.getByRole('region', { name: 'Материалы и обработка', exact: true }).locator('dd').first()).toHaveText('1');
        if (section === 'findings') await expect(page.getByRole('region', { name: 'Группы находок', exact: true })).toContainText('Группировка F2 пока не подключена.');
        if (section === 'processing') {
          await expect(page.getByRole('region', { name: 'История запусков', exact: true })).toContainText('В истории пока нет запусков.');
          await expect(page.getByRole('form', { name: 'Запуск обработки текста', exact: true }).getByRole('group', { name: 'Текстовые отзывы', exact: true }).getByRole('checkbox')).toHaveCount(1);
        }
        if (section === 'materials') {
          await expect(page.getByRole('region', { name: 'Отзывы', exact: true }).locator('.material-list li')).toHaveCount(1);
          await expect(page.getByRole('region', { name: 'Документы продукта', exact: true }).locator('.material-list li')).toHaveCount(1);
        }
        if (section === 'access') await expect(page.getByRole('region', { name: 'Участники', exact: true }).getByRole('listitem')).toHaveCount(1);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.mouse.move(0, 0);
        await expect(page).toHaveScreenshot(`observer-${section}-${width}.png`, {
          fullPage: true, animations: 'disabled', caret: 'hide', stylePath: stableStyle, maxDiffPixelRatio: 0.001,
        });
        await page.screenshot({ path: deployed ? resolve(screenshots, `app-${section}-${width}.png`)
          : testInfo.outputPath(`app-${section}-${width}.png`), fullPage: true, animations: 'disabled' });

        await reference.locator(`[data-action="navigate"][data-view="${prototypeView}"]:visible`).first().click();
        if (prototypeView === 'requirements') await reference.locator('[data-action="req-layout"][data-layout="list"]:visible').click();
        await reference.mouse.move(0, 0);
        await reference.locator('#app').screenshot({ path: resolve(screenshots, `reference-${section}-${width}.png`), animations: 'disabled' });
        const expectedPalette = await reference.locator('#app').evaluate((element, keys) => keys.map(key => getComputedStyle(element).getPropertyValue(key).trim()), paletteKeys);
        const actualPalette = await page.locator('.observer-v3.workspace').evaluate((element, keys) => keys.map(key => getComputedStyle(element).getPropertyValue(key).trim()), paletteKeys);
        expect(actualPalette).toEqual(expectedPalette);
        if (width >= 1280 && section === 'overview') {
          await expect(page.locator('.metric-grid .metric')).toHaveCount(4);
          const appPadding = await page.locator('main.content').evaluate(element => getComputedStyle(element).paddingLeft);
          const referencePadding = await reference.locator('#app .content').evaluate(element => getComputedStyle(element).paddingLeft);
          expect(appPadding).toBe(referencePadding);
        }
      }
    }
  } finally { await reference.close(); }
});

test('new detail addresses stay scoped and ordinary application never loads visual fixtures or unsupported F2 API', async ({ page }) => {
  await registerAndLogin(page);
  const project = await createProject(page, 'Проверка границ Observer');
  const semantic: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/') && /\/(requirements|groups)(\/|$)/.test(new URL(request.url()).pathname)) semantic.push(request.url());
  });
  for (const path of ['requirements/REQ-01', 'findings/groups/G-01', 'processing']) {
    await page.goto(`/#/projects/${project.id}/${path}`); await page.reload();
    await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible();
    if (path === 'processing') await expect(page.getByRole('form', { name: 'Запуск обработки текста', exact: true })).toBeVisible();
    else await expect(page.getByText('Функция не подключена', { exact: true })).toBeVisible();
    await expect(page.getByRole('note')).toHaveCount(0);
    await expect(page.getByText('Сохранение изменений', { exact: true })).toHaveCount(0);
  }
  expect(semantic).toEqual([]);
  if (deployed) expect((await page.request.get('/tests/fixtures/observer.html')).status()).toBe(404);
});
