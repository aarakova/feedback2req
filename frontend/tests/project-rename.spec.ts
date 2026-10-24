import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';

const settings = (page: Page) => page.getByRole('region', { name: 'Настройки проекта', exact: true });
const input = (page: Page) => page.getByLabel('Новое название проекта', { exact: true });
const saved = (page: Page) => settings(page).getByRole('status').filter({ hasText: 'Название проекта сохранено.' });
const unknown = (page: Page) => settings(page).getByRole('group', { name: 'Неизвестный результат переименования', exact: true });

async function setup(page: Page) {
  const login = await registerAndLogin(page);
  const project = await createProject(page, 'Исходный проект');
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const path = `/api/v1/projects/${project.id}`;
  await page.goto(`/#/projects/${project.id}/access`);
  await expect(settings(page)).toBeVisible();
  return { project, path, headers, login };
}

async function edit(page: Page, name: string) {
  await settings(page).getByRole('button', { name: 'Изменить название', exact: true }).click();
  await input(page).fill(name);
}

test('real rename sends exact PATCH, updates all project views and safely renders Unicode and markup', async ({ page }, testInfo) => {
  const { project, path } = await setup(page);
  const submitted = '  Новое имя 🧭 е\u0301 <script>пример</script>  ';
  const name = submitted.trim();
  await edit(page, submitted);
  const response = page.waitForResponse(response => response.url().endsWith(path) && response.request().method() === 'PATCH');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  expect(result.request().postDataJSON()).toEqual({ name: submitted });
  expect((await result.request().allHeaders())['x-csrf-token']).toBeTruthy();
  expect((await result.json()).name).toBe(name);
  await expect(saved(page)).toBeVisible();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await expect(page.locator('.sidebar-project-name')).toHaveText(name);
  await expect(settings(page).getByRole('button', { name: 'Изменить название', exact: true })).toBeFocused();
  await expect(page.locator('.project-header script')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await edit(page, 'Ещё одно имя');
  await page.screenshot({ path: testInfo.outputPath('rename-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('rename-mobile.png'), fullPage: true });
  await settings(page).getByRole('button', { name: 'Отменить переименование', exact: true }).click();
  await page.getByRole('link', { name: 'Все проекты', exact: false }).click();
  await expect(page.getByRole('link').filter({ has: page.getByRole('heading', { name, exact: true }) })).toBeVisible();
  expect((await (await page.request.get(path)).json()).id).toBe(project.id);
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []]);
});

test('cancel never writes and name limits use real server validation without truncating the draft', async ({ page }) => {
  const { path } = await setup(page); let patches = 0;
  page.on('request', request => { if (request.method() === 'PATCH') patches++; });
  await edit(page, 'Не сохранять');
  await settings(page).getByRole('button', { name: 'Отменить переименование' }).click();
  await expect(settings(page).getByRole('button', { name: 'Изменить название', exact: true })).toBeFocused();
  expect(patches).toBe(0);
  await edit(page, '   ');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(settings(page).getByRole('alert')).toContainText('непустое название');
  expect(patches).toBe(0);
  await input(page).fill('я'.repeat(201));
  const response = page.waitForResponse(response => response.url().endsWith(path) && response.request().method() === 'PATCH');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  expect((await response).status()).toBe(422);
  await expect(input(page)).toHaveValue('я'.repeat(201));
  await expect(saved(page)).toHaveCount(0);
  await expect(unknown(page)).toHaveCount(0);
  const name = '🧭'.repeat(200);
  await input(page).fill(name);
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(saved(page)).toBeVisible();
  expect((await (await page.request.get(path)).json()).name).toBe(name);
});

for (const choice of ['overwrite', 'current'] as const) {
  test(`concurrent owner rename preserves draft and requires explicit ${choice} choice`, async ({ page, playwright }) => {
    const { path, login } = await setup(page);
    const origin = new URL(page.url()).origin;
    const other = await playwright.request.newContext({ baseURL: origin, extraHTTPHeaders: { Origin: origin } });
    try {
      expect((await other.post('/api/v1/auth/session', { data: { login, password } })).status()).toBe(200);
      const headers = await authenticatedHeaders(other, origin);
      await edit(page, 'Мой вариант');
      expect((await other.patch(path, { headers, data: { name: 'Имя из другой сессии' } })).status()).toBe(200);
      let patches = 0;
      page.on('request', request => { if (request.method() === 'PATCH') patches++; });
      await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
      await expect(settings(page).getByRole('group', { name: 'Конкурентное изменение названия' })).toContainText('Имя из другой сессии');
      await expect(input(page)).toHaveValue('Мой вариант');
      await expect(page.getByRole('heading', { name: 'Имя из другой сессии', exact: true })).toBeVisible();
      expect(patches).toBe(0);
      if (choice === 'overwrite') {
        await settings(page).getByRole('button', { name: 'Сохранить моё название', exact: true }).click();
        await expect(saved(page)).toBeVisible();
        expect((await (await page.request.get(path)).json()).name).toBe('Мой вариант'); expect(patches).toBe(1);
      } else {
        await settings(page).getByRole('button', { name: 'Использовать текущее название', exact: true }).click();
        await expect(input(page)).toHaveValue('Имя из другой сессии');
        expect(patches).toBe(0);
      }
    } finally { await other.dispose(); }
  });
}

test('lost committed PATCH stays unknown; failed verification preserves lock and successful GET reconciles', async ({ page }) => {
  const { path } = await setup(page); let patches = 0;
  await page.route(`**${path}`, async route => {
    if (route.request().method() !== 'PATCH') { await route.continue(); return; }
    patches++; const response = await route.fetch(); expect(response.status()).toBe(200); await route.abort();
  });
  await edit(page, 'Сохранённое без ответа');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(unknown(page)).toBeVisible();
  await expect(saved(page)).toHaveCount(0);
  await expect(settings(page).getByRole('button', { name: 'Сохранить название', exact: true })).toBeDisabled();
  await expect(input(page)).toHaveValue('Сохранённое без ответа');
  await page.route(`**${path}`, route => route.abort(), { times: 1 });
  await settings(page).getByRole('button', { name: 'Проверить текущее название', exact: true }).click();
  await expect(settings(page).getByRole('alert')).toBeVisible();
  await expect(unknown(page)).toBeVisible();
  await settings(page).getByRole('button', { name: 'Проверить текущее название', exact: true }).click();
  await expect(settings(page).getByRole('status').filter({ hasText: 'Текущее название:' })).toContainText('Сохранённое без ответа');
  await expect(page.getByRole('heading', { name: 'Сохранённое без ответа', exact: true })).toBeVisible();
  await expect(unknown(page)).toHaveCount(0); await expect(saved(page)).toHaveCount(0); expect(patches).toBe(1);
});

test('500 preserves draft, blocks duplicate PATCH and requires GET before manual retry', async ({ page }) => {
  const { path } = await setup(page);
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  let patches = 0;
  await page.route(`**${path}`, async route => {
    if (route.request().method() !== 'PATCH') { await route.continue(); return; }
    patches++; await gate; await route.fulfill({ status: 500, json: { error: { code: 'internal_error' } } });
  });
  await edit(page, 'Черновик после ошибки');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(settings(page).getByRole('button', { name: 'Сохранить название', exact: true })).toBeDisabled();
  release(); await expect(unknown(page)).toBeVisible();
  await expect(input(page)).toHaveValue('Черновик после ошибки'); expect(patches).toBe(1);
  await settings(page).getByRole('button', { name: 'Проверить текущее название', exact: true }).click();
  await expect(settings(page).getByRole('status').filter({ hasText: 'Текущее название:' })).toContainText('Исходный проект');
  await expect(saved(page)).toHaveCount(0); expect(patches).toBe(1);
});

for (const code of ['csrf_rejected', 'forbidden'] as const) {
  test(`${code} rejects rename without claiming success or discarding the draft`, async ({ page }) => {
    const { path } = await setup(page);
    await page.route(`**${path}`, route => route.request().method() === 'PATCH'
      ? route.fulfill({ status: 403, json: { error: { code } } }) : route.continue());
    await edit(page, 'Черновик');
    await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
    await expect(settings(page).getByRole('alert')).toBeVisible();
    await expect(input(page)).toHaveValue('Черновик'); await expect(unknown(page)).toHaveCount(0);
    await expect(saved(page)).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Исходный проект', exact: true })).toBeVisible();
  });
}

test('failed preflight does not send PATCH or claim unknown mutation', async ({ page }) => {
  const { path } = await setup(page);
  await edit(page, 'После восстановления'); let patches = 0;
  page.on('request', request => { if (request.method() === 'PATCH') patches++; });
  await page.route(`**${path}`, route => route.abort(), { times: 1 });
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(settings(page).getByRole('alert')).toContainText('Не удалось связаться');
  await expect(input(page)).toHaveValue('После восстановления'); await expect(unknown(page)).toHaveCount(0);
  expect(patches).toBe(0);
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(saved(page)).toBeVisible(); expect(patches).toBe(1);
});

test('Member and Approver cannot rename through UI or real PATCH', async ({ page, browser }) => {
  const { project, path, headers } = await setup(page); const origin = new URL(page.url()).origin;
  const login = unique();
  const response = await page.request.post('/api/v1/auth/register', { headers: { Origin: origin }, data: { login, password } });
  expect(response.status()).toBe(201); const user = await response.json();
  const member = await browser.newContext({ baseURL: origin });
  try {
    expect((await member.request.post('/api/v1/auth/session', { headers: { Origin: origin }, data: { login, password } })).status()).toBe(200);
    const memberPage = await member.newPage(); const memberHeaders = await authenticatedHeaders(member.request, origin);
    expect((await member.request.patch(path, { headers: memberHeaders, data: { name: 'Чужое имя' } })).status()).toBe(404);
    for (const can_approve of [false, true]) {
      expect((await page.request.put(`${path}/access/${user.id}`, { headers, data: { can_approve } })).status()).toBe(200);
      await memberPage.goto(`/#/projects/${project.id}/access`); await memberPage.reload();
      await expect(memberPage.getByText('Просмотр и управление участниками доступны только владельцу проекта.')).toBeVisible();
      await expect(settings(memberPage)).toHaveCount(0);
      expect((await member.request.patch(path, { headers: memberHeaders, data: { name: 'Чужое имя' } })).status()).toBe(403);
    }
  } finally { await member.close(); }
});

for (const action of ['project', 'logout'] as const) {
  test(`late committed rename response cannot return after switching ${action}`, async ({ page }) => {
    const { path } = await setup(page); const other = await createProject(page, 'Другой проект');
    let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
    let reached!: () => void; const intercepted = new Promise<void>(resolve => { reached = resolve; });
    await page.route(`**${path}`, async route => {
      if (route.request().method() !== 'PATCH') { await route.continue(); return; }
      const response = await route.fetch(); expect(response.status()).toBe(200); reached(); await gate;
      await route.fulfill({ response }).catch(() => {});
    });
    await edit(page, 'Имя прошлого проекта');
    await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click(); await intercepted;
    if (action === 'project') {
      await page.evaluate(id => { location.hash = `/projects/${id}/access`; }, other.id);
      await expect(page.getByRole('heading', { name: 'Другой проект', exact: true })).toBeVisible();
    } else {
      await page.getByRole('button', { name: 'Выйти', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Вход в аккаунт', exact: true })).toBeVisible();
    }
    release(); await page.unrouteAll({ behavior: 'wait' });
    await expect(page.getByText('Имя прошлого проекта', { exact: true })).toHaveCount(0);
    await expect(saved(page)).toHaveCount(0);
  });
}

test('focus during a committed pending rename retains unknown outcome until explicit verification', async ({ page }) => {
  const { path } = await setup(page);
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void; const intercepted = new Promise<void>(resolve => { reached = resolve; });
  let patches = 0;
  await page.route(`**${path}`, async route => {
    if (route.request().method() !== 'PATCH') { await route.continue(); return; }
    patches++; const response = await route.fetch(); expect(response.status()).toBe(200); reached(); await gate;
    await route.fulfill({ response }).catch(() => {});
  });
  await edit(page, 'Имя после focus');
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click(); await intercepted;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(unknown(page)).toBeVisible(); release(); await page.unrouteAll({ behavior: 'wait' });
  await expect(saved(page)).toHaveCount(0);
  await settings(page).getByRole('button', { name: 'Проверить текущее название', exact: true }).click();
  await expect(settings(page).getByRole('status').filter({ hasText: 'Текущее название:' })).toContainText('Имя после focus');
  expect(patches).toBe(1);
});

test('expired session before rename removes the form and project identity', async ({ page }) => {
  const { headers } = await setup(page); await edit(page, 'Не отправлять');
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await settings(page).getByRole('button', { name: 'Сохранить название', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт', exact: true })).toBeVisible();
  await expect(settings(page)).toHaveCount(0);
  await expect(page.getByText('Исходный проект', { exact: true })).toHaveCount(0);
});
