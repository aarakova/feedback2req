import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';

const nav = (page: Page) => page.getByRole('navigation', { name: 'Разделы проекта', exact: true });
async function setup(page: Page) {
  await registerAndLogin(page);
  const first = await createProject(page, `Проект А ${unique()}`);
  const second = await createProject(page, `Проект Б ${unique()}`);
  return { first, second };
}
async function open(page: Page, id: string, name: string, section = '') {
  await page.goto(`/#/projects/${id}${section ? `/${section}` : ''}`);
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}

test('all projects stays independent and opens the correct project shell', async ({ page }) => {
  const { first, second } = await setup(page);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
  await expect(nav(page)).toHaveCount(0);
  await page.getByRole('link').filter({ has: page.getByRole('heading', { name: first.name, exact: true }) }).click();
  await expect(page.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  await expect(nav(page).getByRole('link')).toHaveCount(6);
  await expect(nav(page).getByRole('link', { name: 'Обзор проекта', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('navigation', { name: 'Основная навигация', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Все проекты', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
  await page.getByRole('link').filter({ has: page.getByRole('heading', { name: second.name, exact: true }) }).click();
  await expect(page.getByRole('heading', { name: second.name, exact: true })).toBeVisible();
  await expect(page.getByText(first.name, { exact: true })).toHaveCount(0);
});

test('overview and future sections never fetch unsupported API or fabricate product metrics', async ({ page }) => {
  const { first } = await setup(page);
  const requested: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/')) requested.push(new URL(request.url()).pathname); });
  await open(page, first.id, first.name);
  const capabilities = page.getByRole('region', { name: 'Возможности проекта', exact: true });
  await expect(capabilities).toBeVisible();
  await expect(capabilities.locator('.capability-state')).toHaveText(['Доступно', 'Доступно', 'Не подключено']);
  await expect(page.getByRole('heading', { name: 'Ваши полномочия', exact: true })).toBeVisible();
  await expect(page.getByRole('combobox')).toHaveCount(0);
  await expect(page.getByText(/Открытые блокеры|Вымышленные данные|Сбросить демо|Вы · демо/)).toHaveCount(0);
  expect(requested.some(path => /\/(sources|documents|findings|requirements|runs|processing)$/.test(path))).toBe(false);
  for (const name of ['Находки', 'Требования', 'Обработка']) {
    await nav(page).getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    await expect(page.getByText('Функция не подключена', { exact: true })).toBeVisible();
    await expect(nav(page).getByRole('link', { name, exact: true })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('button', { name: /Запустить|Создать требование|Повторить обработку/ })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  }
  expect(requested.some(path => /\/(findings|requirements|runs|processing)(\/|$)/.test(path))).toBe(false);
});

test('material and access routes reload inside the project shell and preserve direct material links', async ({ page }) => {
  const { first } = await setup(page);
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const text = '  Прямой отзыв 🧭 е\u0301\tстрока\r\nвторая строка\n  ';
  const response = await page.request.post(`/api/v1/projects/${first.id}/sources`, {
    headers, data: { kind: 'text', text },
  });
  expect(response.status()).toBe(201); const source = await response.json();
  await open(page, first.id, first.name, `materials/sources/${source.id}`);
  const detail = page.getByRole('region', { name: 'Просмотр материала', exact: true });
  await expect(detail.getByLabel('Сохранённый текст')).toBeVisible();
  expect(await detail.getByLabel('Сохранённый текст').textContent()).toBe(text);
  await page.reload();
  await expect(detail.getByLabel('Сохранённый текст')).toBeVisible();
  expect(await detail.getByLabel('Сохранённый текст').textContent()).toBe(text);
  await expect(nav(page).getByRole('link', { name: 'Материалы', exact: true })).toHaveAttribute('aria-current', 'page');
  await nav(page).getByRole('link', { name: 'Доступ', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Участники', exact: true })).toBeVisible();
  await page.reload();
  await expect(nav(page).getByRole('link', { name: 'Доступ', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('region', { name: 'Участники', exact: true }).getByRole('listitem')).toHaveCount(1);
  await nav(page).getByRole('link', { name: 'Обзор проекта', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Обзор проекта', exact: true })).toBeVisible();
});

test('unknown routes do not fall back to a working project section or keep its data', async ({ page }) => {
  const { first } = await setup(page);
  for (const hash of [`/projects/${first.id}/unknown`, `/projects/${first.id}/access/sources/${crypto.randomUUID()}`,
    `/projects/${first.id}/materials/unknown/${crypto.randomUUID()}`, '/projects/not-a-uuid', '/unknown']) {
    await open(page, first.id, first.name);
    await page.evaluate(value => { location.hash = value; }, hash);
    await expect(page.getByRole('heading', { name: 'Страница не найдена', exact: true })).toBeVisible();
    await expect(nav(page)).toHaveCount(0);
    await expect(page.getByText(first.name, { exact: true })).toHaveCount(0);
  }
  await page.getByRole('link', { name: 'Вернуться к проектам', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
});

test('rapid project changes ignore the late project response in header, sidebar and overview', async ({ page }) => {
  const { first, second } = await setup(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  await page.route(`**/api/v1/projects/${first.id}`, async route => {
    const response = await route.fetch(); reached(); await gate;
    await route.fulfill({ response }).catch(() => {});
  });
  await page.evaluate(id => { location.hash = `/projects/${id}`; }, first.id); await intercepted;
  await page.evaluate(id => { location.hash = `/projects/${id}/findings`; }, second.id);
  await expect(page.getByRole('heading', { name: second.name, exact: true })).toBeVisible();
  await nav(page).getByRole('link', { name: 'Обзор проекта', exact: true }).click();
  release(); await page.unrouteAll({ behavior: 'wait' });
  await expect(page.getByText(first.name, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: second.name, exact: true })).toBeVisible();
  await expect(page.locator('.sidebar-project-name')).toHaveText(second.name);
});

test('project load failure keeps a working return to all projects', async ({ page }) => {
  const { first } = await setup(page);
  await page.route(`**/api/v1/projects/${first.id}`, route => route.abort());
  await page.goto(`/#/projects/${first.id}`);
  await expect(page.getByRole('alert')).toContainText('Не удалось связаться');
  await expect(nav(page)).toHaveCount(0);
  await expect(page.getByText(first.name, { exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Все проекты', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
});

test('revoked Member access removes project chrome even from an informational future section', async ({ page, browser }) => {
  const { first } = await setup(page);
  const origin = new URL(page.url()).origin;
  const login = unique();
  const registered = await page.request.post('/api/v1/auth/register', { headers: { Origin: origin }, data: { login, password } });
  expect(registered.status()).toBe(201); const user = await registered.json();
  const headers = await authenticatedHeaders(page.request, origin);
  const path = `/api/v1/projects/${first.id}/access/${user.id}`;
  expect((await page.request.put(path, { headers, data: { can_approve: false } })).status()).toBe(200);
  const member = await browser.newContext({ baseURL: origin });
  try {
    expect((await member.request.post('/api/v1/auth/session', { headers: { Origin: origin }, data: { login, password } })).status()).toBe(200);
    const memberPage = await member.newPage();
    await open(memberPage, first.id, first.name, 'requirements');
    await expect(nav(memberPage).getByRole('link', { name: 'Доступ', exact: true })).toHaveCount(0);
    await expect(nav(memberPage).getByRole('link')).toHaveCount(5);
    expect((await page.request.delete(path, { headers })).status()).toBe(204);
    await memberPage.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(memberPage.getByRole('alert')).toContainText('Проект не найден');
    await expect(memberPage.getByText(first.name, { exact: true })).toHaveCount(0);
    await expect(nav(memberPage)).toHaveCount(0);
    await expect(memberPage.getByRole('heading', { name: 'Требования', exact: true })).toHaveCount(0);
    await memberPage.getByRole('link', { name: 'Все проекты', exact: false }).click();
    await expect(memberPage.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
  } finally { await member.close(); }
});

test('project navigation works on desktop and mobile with keyboard focus and one current section', async ({ page }, testInfo) => {
  const { first } = await setup(page); await open(page, first.id, first.name);
  await page.screenshot({ path: testInfo.outputPath('overview-desktop.png'), fullPage: true });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    if (await page.locator('.own-id details').getAttribute('open') === null) await page.getByText('Мой ID', { exact: true }).click();
    const materials = nav(page).getByRole('link', { name: 'Материалы', exact: true });
    await nav(page).getByRole('link', { name: 'Обзор проекта', exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(materials).toBeFocused();
    expect(await materials.evaluate(element => getComputedStyle(element).outlineWidth)).toBe('2px');
    await page.keyboard.press('Enter');
    await expect(materials).toHaveAttribute('aria-current', 'page');
    await expect(nav(page).locator('[aria-current="page"]')).toHaveCount(1);
    await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('link', { name: 'К содержимому', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#main-content')).toBeFocused();
    await nav(page).getByRole('link', { name: 'Обзор проекта', exact: true }).click();
    await page.screenshot({ path: testInfo.outputPath(`overview-mobile-${width}.png`), fullPage: true });
  }
});
