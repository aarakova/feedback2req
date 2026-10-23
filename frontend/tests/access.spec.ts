import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';

const panel = (page: Page) => page.getByRole('region', { name: 'Участники', exact: true });
const memberRow = (page: Page, id: string) => panel(page).getByRole('listitem', { name: `Участник ${id}`, exact: true });

async function newUser(page: Page) {
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: new URL(page.url()).origin }, data: { login: unique(), password },
  });
  expect(response.status()).toBe(201);
  return response.json() as Promise<{ id: string; login: string }>;
}

async function setup(page: Page, count = 0) {
  await registerAndLogin(page);
  const session = await (await page.request.get('/api/v1/auth/session')).json();
  const project = await createProject(page, 'Проект доступа');
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const path = `/api/v1/projects/${project.id}/access`;
  const members = [];
  for (let i = 0; i < count; i++) {
    const user = await newUser(page); members.push(user);
    expect((await page.request.put(`${path}/${user.id}`, { headers, data: { can_approve: false } })).status()).toBe(200);
  }
  await page.goto(`/#/projects/${project.id}/access`);
  await expect(panel(page).getByRole('listitem')).not.toHaveCount(0);
  await expect(panel(page).getByRole('button', { name: 'Добавить участника', exact: true })).toBeEnabled();
  return { project, headers, path, members, owner: session.user };
}

async function allRows(page: Page) {
  while (await panel(page).getByRole('button', { name: 'Показать ещё', exact: true }).count()) {
    await panel(page).getByRole('button', { name: 'Показать ещё', exact: true }).click();
    await expect(panel(page).getByRole('button', { name: 'Добавить участника', exact: true })).toBeEnabled();
  }
}

async function addForm(page: Page, id: string) {
  await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).click();
  await page.getByLabel('ID пользователя', { exact: true }).fill(id);
}

test('own ID without projects copies real clipboard and reports clipboard denial', async ({ page, context }) => {
  await registerAndLogin(page);
  const session = await (await page.request.get('/api/v1/auth/session')).json();
  await page.getByText('Мой ID', { exact: true }).click();
  await expect(page.getByLabel('Мой ID пользователя')).toHaveText(session.user.id);
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: 'Копировать ID' }).click();
  await expect(page.getByRole('status')).toHaveText('ID скопирован.');
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(session.user.id);
  await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {
    configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) },
  }));
  await page.getByRole('button', { name: 'Копировать ID' }).click();
  await expect(page.getByRole('status')).toContainText('Не удалось скопировать ID');
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []]);
});

test('owner is immutable, cursor pages reload, navigation and mobile keyboard layout work', async ({ page }, testInfo) => {
  const { project, owner } = await setup(page, 4);
  await expect(panel(page).getByRole('list', { name: 'Список участников' }).getByRole('listitem')).toHaveCount(2);
  await allRows(page);
  await expect(panel(page).getByRole('list', { name: 'Список участников' }).getByRole('listitem')).toHaveCount(5);
  await expect(memberRow(page, owner.id).getByText('Владелец', { exact: true })).toBeVisible();
  await expect(memberRow(page, owner.id).getByRole('button')).toHaveCount(0);
  await page.reload();
  await expect(panel(page).getByRole('listitem')).toHaveCount(2);
  await page.getByRole('link', { name: 'Материалы', exact: true }).click();
  await page.goBack(); await expect(panel(page)).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
  await page.goto(`/#/projects/${project.id}/access`);
  await expect(panel(page).getByRole('button', { name: 'Добавить участника', exact: true })).toBeEnabled();
  await page.screenshot({ path: testInfo.outputPath('access-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByText('Мой ID', { exact: true }).click();
  await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('ID пользователя', { exact: true })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('access-mobile.png'), fullPage: true });
});

test('new member is added once with exact PUT and Approver can be granted and revoked', async ({ page, playwright }) => {
  const { project, path } = await setup(page);
  await expect(panel(page).getByText('Кроме владельца участников пока нет.')).toBeVisible();
  const user = await newUser(page); await addForm(page, user.id);
  const response = page.waitForResponse(response => response.url().endsWith(`${path}/${user.id}`) && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  const created = await response;
  expect(created.status()).toBe(200);
  expect(created.request().postDataJSON()).toEqual({ can_approve: false });
  expect((await created.request().allHeaders())['x-csrf-token']).toBeTruthy();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toBeVisible();
  await expect(page.getByRole('form', { name: 'Добавление участника' })).toHaveCount(0);
  const member = await playwright.request.newContext({ baseURL: new URL(page.url()).origin });
  try {
    expect((await member.post('/api/v1/auth/session', { headers: { Origin: new URL(page.url()).origin }, data: { login: user.login, password } })).status()).toBe(200);
    for (const [button, approve] of [['Назначить Approver', true], ['Отозвать Approver', false]] as const) {
      await expect(memberRow(page, user.id).getByRole('button', { name: button, exact: true })).toBeEnabled();
      await memberRow(page, user.id).getByRole('button', { name: button, exact: true }).click();
      await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toBeVisible();
      const rights = await (await member.get(`/api/v1/projects/${project.id}`)).json();
      expect(rights.permissions).toEqual({ is_owner: false, is_member: true, can_approve: approve });
    }
  } finally { await member.dispose(); }
});

test('duplicate ID beyond first page never silently revokes Approver', async ({ page }) => {
  const { path, headers, members } = await setup(page, 4);
  const user = [...members].sort((a, b) => a.id.localeCompare(b.id)).at(-1)!;
  expect((await page.request.put(`${path}/${user.id}`, { headers, data: { can_approve: true } })).status()).toBe(200);
  let puts = 0;
  page.on('request', request => { if (request.method() === 'PUT') puts++; });
  await addForm(page, user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Участник уже в проекте' })).toBeVisible();
  expect(puts).toBe(0);
  await expect(memberRow(page, user.id).getByRole('button', { name: 'Отозвать Approver' })).toBeVisible();
});

test('invalid IDs, nonexistent user and owner target preserve form without false success', async ({ page }) => {
  const { owner } = await setup(page); await addForm(page, 'bad-id');
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toContainText('формате UUID');
  await page.getByLabel('ID пользователя', { exact: true }).fill(owner.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toContainText('Владелец уже участвует');
  const missing = crypto.randomUUID();
  await page.getByLabel('ID пользователя', { exact: true }).fill(missing);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toContainText('не зарегистрирован');
  await expect(page.getByLabel('ID пользователя', { exact: true })).toHaveValue(missing);
  await expect(panel(page).getByText('Доступ сохранён:', { exact: false })).toHaveCount(0);
});

test('removal requires confirmation, supports cancellation and repeated DELETE', async ({ page }) => {
  const { path, headers, members } = await setup(page, 1);
  const row = memberRow(page, members[0].id);
  await row.getByRole('button', { name: 'Удалить участника', exact: true }).click();
  await expect(row.getByRole('group', { name: 'Подтверждение удаления' })).toBeVisible();
  await row.getByRole('button', { name: 'Отмена удаления' }).click();
  await expect(row.getByRole('group')).toHaveCount(0);
  await row.getByRole('button', { name: 'Удалить участника', exact: true }).click();
  expect((await page.request.delete(`${path}/${members[0].id}`, { headers })).status()).toBe(204);
  await row.getByRole('button', { name: 'Удалить из проекта', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ к проекту отсутствует' })).toBeVisible();
  await expect(row).toHaveCount(0);
});

test('Member and Approver have no access controls or API rights; outsider cannot open project', async ({ page }) => {
  const { project, path, headers, members, owner } = await setup(page, 1);
  for (const approve of [false, true]) {
    expect((await page.request.put(`${path}/${members[0].id}`, { headers, data: { can_approve: approve } })).status()).toBe(200);
    const ownerCookies = await page.context().cookies();
    const origin = new URL(page.url()).origin;
    expect((await page.request.post('/api/v1/auth/session', { headers: { Origin: origin }, data: { login: members[0].login, password } })).status()).toBe(200);
    await page.reload();
    await expect(page.getByText('Просмотр и управление участниками доступны только владельцу проекта.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Участники', exact: true })).toHaveCount(0);
    await expect(panel(page)).toHaveCount(0);
    const memberHeaders = await authenticatedHeaders(page.request, origin);
    expect((await page.request.get(path)).status()).toBe(403);
    expect((await page.request.put(`${path}/${owner.id}`, { headers: memberHeaders, data: { can_approve: true } })).status()).toBe(403);
    expect((await page.request.delete(`${path}/${members[0].id}`, { headers: memberHeaders })).status()).toBe(403);
    await page.context().clearCookies(); await page.context().addCookies(ownerCookies);
  }
  const outsider = await newUser(page);
  expect((await page.request.post('/api/v1/auth/session', { headers: { Origin: new URL(page.url()).origin }, data: { login: outsider.login, password } })).status()).toBe(200);
  await page.goto(`/#/projects/${project.id}/access`); await page.reload();
  await expect(page.getByRole('alert')).toContainText('Проект не найден');
  await expect(panel(page)).toHaveCount(0);
});

test('Owner-only 403 clears participants but preserves project and working overview', async ({ page }) => {
  const { project, path } = await setup(page, 1);
  await page.route(`**${path}`, route => route.fulfill({ status: 403, json: { error: { code: 'forbidden' } } }));
  await panel(page).getByRole('button', { name: 'Обновить участников' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('Недостаточно прав');
  await expect(panel(page).getByRole('listitem')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Обзор проекта' }).click();
  await expect(page.getByRole('heading', { name: 'Ваши полномочия' })).toBeVisible();
});

for (const method of ['PUT', 'DELETE'] as const) {
  test(`lost ${method} response does not retry; verification traverses real pages`, async ({ page }) => {
    const { path, members } = await setup(page, 4);
    const user = [...members].sort((a, b) => a.id.localeCompare(b.id)).at(-1)!;
    await allRows(page);
    let writes = 0;
    await page.route(`**${path}/${user.id}`, async route => {
      if (route.request().method() !== method) { await route.continue(); return; }
      writes++;
      const response = await route.fetch(); expect(response.status()).toBe(method === 'PUT' ? 200 : 204);
      await route.abort();
    });
    if (method === 'PUT') await memberRow(page, user.id).getByRole('button', { name: 'Назначить Approver' }).click();
    else {
      await memberRow(page, user.id).getByRole('button', { name: 'Удалить участника', exact: true }).click();
      await memberRow(page, user.id).getByRole('button', { name: 'Удалить из проекта', exact: true }).click();
    }
    await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toBeVisible();
    await expect(panel(page).getByText('Доступ сохранён:', { exact: false })).toHaveCount(0);
    let reads = 0;
    page.on('request', request => { if (request.method() === 'GET' && request.url().includes(path)) reads++; });
    await page.getByRole('button', { name: 'Проверить текущее состояние', exact: true }).click();
    await expect(panel(page).getByRole('status').filter({ hasText: 'Текущее состояние' })).toContainText(method === 'PUT' ? 'участник с правом Approver' : 'доступ отсутствует');
    expect(writes).toBe(1); expect(reads).toBeGreaterThanOrEqual(2);
  });
}

test('concurrent removal before permissions preflight never recreates membership', async ({ page }) => {
  const { path, headers, members } = await setup(page, 1);
  expect((await page.request.delete(`${path}/${members[0].id}`, { headers })).status()).toBe(204);
  let puts = 0;
  page.on('request', request => { if (request.method() === 'PUT') puts++; });
  await memberRow(page, members[0].id).getByRole('button', { name: 'Назначить Approver' }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ изменён в другой сессии' })).toBeVisible();
  expect(puts).toBe(0);
  await expect(memberRow(page, members[0].id)).toHaveCount(0);
});

test('read failure retries, server failure preserves form and pending PUT blocks duplicates', async ({ page }) => {
  const { path } = await setup(page);
  await page.route(`**${path}`, route => route.abort());
  await panel(page).getByRole('button', { name: 'Обновить участников' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('Не удалось связаться');
  await page.unroute(`**${path}`);
  await panel(page).getByRole('button', { name: 'Повторить загрузку участников' }).click();
  await expect(panel(page).getByText('Кроме владельца участников пока нет.')).toBeVisible();
  const user = await newUser(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let writes = 0;
  await page.route(`**${path}/${user.id}`, async route => {
    writes++; await gate;
    await route.fulfill({ status: 500, json: { error: { code: 'internal_error' } } });
  });
  await addForm(page, user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Добавить в проект', exact: true })).toBeDisabled();
  release();
  await expect(panel(page).getByRole('alert')).toContainText('Сервер не смог');
  await expect(page.getByLabel('ID пользователя', { exact: true })).toHaveValue(user.id);
  await expect(page.getByRole('button', { name: 'Добавить в проект', exact: true })).toBeDisabled();
  expect(writes).toBe(1);
});

for (const action of ['logout', 'project', 'user'] as const) {
  test(`late access response cannot return data after switching ${action}`, async ({ page }) => {
    const { path, members } = await setup(page, 1);
    const other = await createProject(page, 'Другой проект');
    const otherUser = action === 'user' ? await newUser(page) : undefined;
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let reached!: () => void;
    const intercepted = new Promise<void>(resolve => { reached = resolve; });
    await page.route(`**${path}`, async route => {
      const response = await route.fetch(); reached(); await gate;
      await route.fulfill({ response }).catch(() => {});
    });
    await panel(page).getByRole('button', { name: 'Обновить участников' }).click(); await intercepted;
    if (action === 'logout') {
      await page.getByRole('button', { name: 'Выйти', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
    } else if (action === 'project') {
      await page.evaluate(id => { location.hash = `/projects/${id}/access`; }, other.id);
      await expect(page.getByRole('heading', { name: other.name, exact: true })).toBeVisible();
    } else {
      expect((await page.request.post('/api/v1/auth/session', {
        headers: { Origin: new URL(page.url()).origin }, data: { login: otherUser!.login, password },
      })).status()).toBe(200);
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.getByRole('alert')).toContainText('Проект не найден');
    }
    release(); await page.unrouteAll({ behavior: 'wait' });
    await expect(memberRow(page, members[0].id)).toHaveCount(0);
  });
}

test('revoked session on access read removes all protected screens', async ({ page }) => {
  const { headers } = await setup(page, 1);
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await panel(page).getByRole('button', { name: 'Обновить участников' }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await expect(panel(page)).toHaveCount(0);
});

test('add with Approver needs one submission and protects owner through the real API', async ({ page }) => {
  const { path, headers, owner } = await setup(page);
  for (const method of ['put', 'delete'] as const) {
    const response = await page.request[method](`${path}/${owner.id}`, {
      headers, ...method === 'put' ? { data: { can_approve: false } } : {},
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).error.code).toBe('owner_access_immutable');
  }
  const user = await newUser(page); await addForm(page, user.id);
  await page.getByLabel('Сразу назначить Approver', { exact: true }).check();
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toContainText('Право Approver назначено');
  await expect(memberRow(page, user.id).getByText('Право утверждения · Approver', { exact: true })).toBeVisible();
});

test('permissions changed in another owner session require a new explicit action', async ({ page, playwright }) => {
  const { path, owner, members } = await setup(page, 1);
  const origin = new URL(page.url()).origin;
  const otherOwner = await playwright.request.newContext({ baseURL: origin, extraHTTPHeaders: { Origin: origin } });
  try {
    expect((await otherOwner.post('/api/v1/auth/session', { data: { login: owner.login, password } })).status()).toBe(200);
    const headers = await authenticatedHeaders(otherOwner, origin);
    expect((await otherOwner.put(`${path}/${members[0].id}`, { headers, data: { can_approve: true } })).status()).toBe(200);
    let puts = 0;
    page.on('request', request => { if (request.method() === 'PUT') puts++; });
    await memberRow(page, members[0].id).getByRole('button', { name: 'Назначить Approver' }).click();
    await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ изменён в другой сессии' })).toBeVisible();
    expect(puts).toBe(0);
    await expect(memberRow(page, members[0].id).getByRole('button', { name: 'Отозвать Approver' })).toBeVisible();
  } finally { await otherOwner.dispose(); }
});

test('member focus reflects Approver change and membership revocation in another session', async ({ page, browser }) => {
  const { project, path, headers, members } = await setup(page, 1);
  const origin = new URL(page.url()).origin;
  const context = await browser.newContext({ baseURL: origin });
  try {
    expect((await context.request.post('/api/v1/auth/session', {
      headers: { Origin: origin }, data: { login: members[0].login, password },
    })).status()).toBe(200);
    const member = await context.newPage();
    await member.goto(`/#/projects/${project.id}`);
    await expect(member.getByText('Вы — участник этого проекта.', { exact: true })).toBeVisible();
    expect((await page.request.put(`${path}/${members[0].id}`, { headers, data: { can_approve: true } })).status()).toBe(200);
    await member.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(member.getByText('Право утверждения · Approver', { exact: true })).toBeVisible();
    expect((await page.request.delete(`${path}/${members[0].id}`, { headers })).status()).toBe(204);
    await member.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(member.getByRole('alert')).toContainText('Проект не найден');
    await expect(member.getByRole('heading', { name: project.name, exact: true })).toHaveCount(0);
  } finally { await context.close(); }
});

test('CSRF rejection preserves project and draft without claiming uncertain mutation', async ({ page }) => {
  const { path } = await setup(page);
  const user = await newUser(page); await addForm(page, user.id);
  await page.route(`**${path}/${user.id}`, route => route.fulfill({ status: 403, json: { error: { code: 'csrf_rejected' } } }));
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toContainText('Не удалось подтвердить запрос');
  await expect(page.getByLabel('ID пользователя', { exact: true })).toHaveValue(user.id);
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toHaveCount(0);
  await expect(panel(page).getByRole('listitem')).toHaveCount(1);
});

test('focus during committed pending PUT retains uncertainty until explicit verification', async ({ page }) => {
  const { path } = await setup(page, 1);
  const user = await newUser(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  let writes = 0;
  await page.route(`**${path}/${user.id}`, async route => {
    writes++;
    const response = await route.fetch(); expect(response.status()).toBe(200); reached(); await gate;
    await route.fulfill({ response }).catch(() => {});
  });
  await addForm(page, user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click(); await intercepted;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toBeVisible();
  release(); await page.unrouteAll({ behavior: 'wait' });
  await expect(panel(page).getByText('Доступ сохранён:', { exact: false })).toHaveCount(0);
  await page.getByRole('button', { name: 'Проверить текущее состояние', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Текущее состояние' })).toContainText('участник без права Approver');
  expect(writes).toBe(1);
});

test('confirmed mutation stays confirmed when subsequent list refresh fails', async ({ page }) => {
  const { path } = await setup(page);
  const user = await newUser(page); let saved = false;
  await page.route(`**${path}`, route => saved ? route.abort() : route.continue());
  await page.route(`**${path}/${user.id}`, async route => {
    const response = await route.fetch(); expect(response.status()).toBe(200); saved = true;
    await route.fulfill({ response });
  });
  await addForm(page, user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toBeVisible();
  await expect(panel(page).getByRole('alert')).toContainText('Не удалось связаться');
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toHaveCount(0);
});
