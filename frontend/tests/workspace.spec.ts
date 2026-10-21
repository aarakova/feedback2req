import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

const password = 'frontend-test-only-2026';
const unique = () => `f1a_${crypto.randomUUID()}`;

async function registerAndLogin(page: Page, login = unique()) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await page.getByLabel('Логин', { exact: true }).fill(login);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('status')).toContainText('Учётная запись создана');
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toBeVisible();
  return login;
}

test('registration, project persistence, session restore and real logout', async ({ page, context }, testInfo) => {
  const login = await registerAndLogin(page);
  await expect(page.getByText('Пока нет доступных проектов')).toBeVisible();
  await page.getByRole('button', { name: '+ Создать проект', exact: true }).click();
  const projectName = `Проект — ${unique()} 🧭`;
  await page.getByLabel('Название проекта').fill(projectName);
  const creation = page.waitForResponse(response => response.url().endsWith('/api/v1/projects') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Создать', exact: true }).click();
  const response = await creation;
  expect(response.status()).toBe(201);
  const requestHeaders = await response.request().allHeaders();
  expect(requestHeaders['origin']).toBe(new URL(page.url()).origin);
  expect(requestHeaders['x-csrf-token']).toBeTruthy();
  const project = await response.json();
  await expect(page.getByRole('heading', { name: projectName, exact: true })).toBeVisible();
  await expect(page.getByText('Владелец', { exact: true })).toBeVisible();
  await expect(page.getByText('Участник', { exact: true })).toBeVisible();
  await expect(page.getByText('Право утверждения · Approver', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: projectName, exact: true })).toBeVisible();
  await expect(page.getByText(login, { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('project-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('project-mobile.png'), fullPage: true });
  const cookie = (await context.cookies()).find(cookie => cookie.name === 'f2r_session');
  expect(cookie?.httpOnly).toBe(true);
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []]);
  await page.getByRole('link', { name: 'Все проекты', exact: false }).click();
  await page.getByRole('link').filter({ has: page.getByRole('heading', { name: projectName, exact: true }) }).click();
  await expect(page.getByRole('heading', { name: projectName, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  expect((await page.request.get(`/api/v1/projects/${project.id}`)).status()).toBe(401);
  await page.goto(`/#/projects/${project.id}`);
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: projectName, exact: true })).not.toBeVisible();
});

test('member permissions refresh from API and revoked access removes project details', async ({ page, playwright }) => {
  await registerAndLogin(page);
  const member = await (await page.request.get('/api/v1/auth/session')).json();
  const origin = new URL(page.url()).origin;
  const owner = await playwright.request.newContext({ baseURL: origin, extraHTTPHeaders: { Origin: origin } });
  try {
    const login = unique();
    expect((await owner.post('/api/v1/auth/register', { data: { login, password } })).status()).toBe(201);
    const session = await (await owner.post('/api/v1/auth/session', { data: { login, password } })).json();
    const headers = { 'X-CSRF-Token': session.csrf_token };
    const project = await (await owner.post('/api/v1/projects', { headers, data: { name: 'Чужой проект с доступом' } })).json();
    const access = `/api/v1/projects/${project.id}/access/${member.user.id}`;
    expect((await owner.put(access, { headers, data: { can_approve: false } })).status()).toBe(200);
    await page.goto(`/#/projects/${project.id}`);
    await expect(page.getByText('Участник', { exact: true })).toBeVisible();
    await expect(page.getByText('Владелец', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Право утверждения · Approver', { exact: true })).toHaveCount(0);
    expect((await owner.put(access, { headers, data: { can_approve: true } })).status()).toBe(200);
    await page.getByRole('button', { name: 'Обновить проект' }).click();
    await expect(page.getByText('Право утверждения · Approver', { exact: true })).toBeVisible();
    expect((await owner.delete(access, { headers })).status()).toBe(204);
    await page.getByRole('button', { name: 'Обновить проект' }).click();
    await expect(page.getByRole('alert')).toContainText('Проект не найден или доступ к нему отозван');
    await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveCount(0);
    await expect(page.getByText('Право утверждения · Approver', { exact: true })).toHaveCount(0);
  } finally { await owner.dispose(); }
});

test('initial session network failure has a working retry', async ({ page }) => {
  await page.route('**/api/v1/auth/session', route => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Не удалось связаться');
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toHaveCount(0);
  await page.unroute('**/api/v1/auth/session');
  await page.getByRole('button', { name: 'Повторить проверку сессии' }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
});

test('a delayed project response cannot restore data after logout', async ({ page }) => {
  await registerAndLogin(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  await page.route('**/api/v1/projects', async route => {
    const response = await route.fetch();
    reached();
    await gate;
    // Aborting an unmounted screen may close the request before this late response.
    await route.fulfill({ response }).catch(() => {});
  });
  await page.getByRole('button', { name: 'Обновить список' }).click();
  await intercepted;
  await expect(page.getByRole('status')).toContainText('Загружаем проекты');
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  release();
  await page.unrouteAll({ behavior: 'wait' });
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toHaveCount(0);
});

test('login errors and unavailable login are reported without signing in', async ({ page }) => {
  const login = await registerAndLogin(page);
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await page.getByLabel('Логин', { exact: true }).fill(login);
  await page.getByLabel('Пароль', { exact: true }).fill('incorrect-password');
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Неверный логин или пароль');
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('alert')).toContainText('Этот логин уже занят');
});

test('project cursor pagination and revoked session clear protected data', async ({ page }) => {
  await registerAndLogin(page);
  const session = await (await page.request.get('/api/v1/auth/session')).json();
  const headers = { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token };
  for (let index = 0; index < 3; index++) {
    expect((await page.request.post('/api/v1/projects', { headers, data: { name: `Pagination ${index}` } })).status()).toBe(201);
  }
  await page.reload();
  await expect(page.getByRole('heading', { name: /^Pagination/ })).toHaveCount(2);
  await page.getByRole('button', { name: 'Показать ещё' }).click();
  await expect(page.getByRole('heading', { name: /^Pagination/ })).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Показать ещё' })).toHaveCount(0);
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await page.getByRole('button', { name: 'Обновить список' }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^Pagination/ })).toHaveCount(0);
});

test('network and logout failures stay errors', async ({ page }) => {
  await registerAndLogin(page);
  await page.route('**/api/v1/projects', route => route.abort());
  await page.getByRole('button', { name: 'Обновить список' }).click();
  await expect(page.getByRole('alert')).toContainText('Не удалось связаться');
  await page.unroute('**/api/v1/projects');
  await page.getByRole('button', { name: 'Повторить запрос' }).click();
  await expect(page.getByText('Пока нет доступных проектов')).toBeVisible();
  await page.route('**/api/v1/auth/session', route => route.request().method() === 'DELETE' ? route.abort() : route.continue());
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Выход не подтверждён' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toHaveCount(0);
  await page.unroute('**/api/v1/auth/session');
  await page.getByRole('button', { name: 'Повторить выход' }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
});
