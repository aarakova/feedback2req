import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';

const panel = (page: Page) => page.getByRole('region', { name: 'Участники', exact: true });
const row = (page: Page, id: string) => panel(page).getByRole('listitem', { name: `Участник ${id}`, exact: true });

async function setup(page: Page, count = 0) {
  const login = await registerAndLogin(page);
  const origin = new URL(page.url()).origin;
  const project = await createProject(page, 'Independent Access QA');
  const headers = await authenticatedHeaders(page.request, origin);
  const path = `/api/v1/projects/${project.id}/access`;
  const members: { id: string; login: string }[] = [];
  for (let index = 0; index < count; index++) {
    const user = await newUser(page);
    members.push(user);
    expect((await page.request.put(`${path}/${user.id}`, { headers, data: { can_approve: false } })).status()).toBe(200);
  }
  await page.goto(`/#/projects/${project.id}/access`);
  await expect(panel(page).getByRole('button', { name: 'Добавить участника', exact: true })).toBeEnabled();
  return { login, origin, project, path, headers, members };
}

async function newUser(page: Page) {
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: new URL(page.url()).origin }, data: { login: unique(), password },
  });
  expect(response.status()).toBe(201);
  return response.json() as Promise<{ id: string; login: string }>;
}

async function pages(page: Page) {
  while (await panel(page).getByRole('button', { name: 'Показать ещё', exact: true }).count()) {
    await panel(page).getByRole('button', { name: 'Показать ещё', exact: true }).click();
    await expect(panel(page).getByRole('button', { name: 'Добавить участника', exact: true })).toBeEnabled();
  }
}

async function ownerHeaders(context: APIRequestContext, origin: string, login: string) {
  expect((await context.post('/api/v1/auth/session', {
    headers: { Origin: origin }, data: { login, password },
  })).status()).toBe(200);
  return authenticatedHeaders(context, origin);
}

test('UUID spelling is canonicalized before the one real add request', async ({ page }) => {
  const { path } = await setup(page);
  const user = await newUser(page);
  await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).click();
  await page.getByLabel('ID пользователя', { exact: true }).fill(`  ${user.id.toUpperCase()}  `);
  const puts: string[] = [];
  page.on('request', request => { if (request.method() === 'PUT') puts.push(request.url()); });
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toBeVisible();
  await expect(row(page, user.id)).toBeVisible();
  expect(puts).toHaveLength(1);
  expect(new URL(puts[0]).pathname).toBe(`${path}/${user.id}`);
});

test('a failed middle page retries that page without dropping or duplicating real participants', async ({ page }) => {
  const { path, members } = await setup(page, 4);
  let failNext = true;
  await page.route(`**${path}?cursor=*`, async route => {
    if (failNext) { failNext = false; await route.abort(); }
    else await route.continue();
  });
  await panel(page).getByRole('button', { name: 'Показать ещё', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toBeVisible();
  await expect(panel(page).getByRole('listitem')).toHaveCount(2);
  await panel(page).getByRole('button', { name: 'Повторить загрузку участников' }).click();
  await expect(panel(page).getByRole('listitem')).toHaveCount(4);
  await pages(page);
  await expect(panel(page).getByRole('listitem')).toHaveCount(5);
  for (const member of members) await expect(row(page, member.id)).toHaveCount(1);
});

test('removal after successful preflight follows the disclosed upsert limitation with exactly one PUT', async ({ page, playwright }) => {
  const { path, login, origin, members } = await setup(page, 1);
  const other = await playwright.request.newContext({ baseURL: origin });
  try {
    const headers = await ownerHeaders(other, origin, login);
    const user = members[0];
    let writes = 0;
    await expect(panel(page).getByText('может вернуть доступ', { exact: false })).toBeVisible();
    await page.route(`**${path}/${user.id}`, async route => {
      if (route.request().method() !== 'PUT') { await route.continue(); return; }
      writes++;
      // Another actual owner session deletes AFTER the browser's successful GET preflight.
      expect((await other.delete(`${path}/${user.id}`, { headers })).status()).toBe(204);
      await route.continue();
    });
    await row(page, user.id).getByRole('button', { name: 'Назначить Approver', exact: true }).click();
    await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toContainText('Approver назначено');
    await expect(row(page, user.id).getByRole('button', { name: 'Отозвать Approver' })).toBeVisible();
    expect(writes).toBe(1);
    const access = await other.get(path);
    expect(access.status()).toBe(200);
    expect((await access.json()).items.find((item: { user_id: string }) => item.user_id === user.id).can_approve).toBe(true);
  } finally { await other.dispose(); }
});

test('concurrent add after absence preflight applies disclosed replacement once', async ({ page, playwright }) => {
  const { path, login, origin } = await setup(page);
  const user = await newUser(page);
  const other = await playwright.request.newContext({ baseURL: origin });
  try {
    const headers = await ownerHeaders(other, origin, login);
    let writes = 0;
    await page.route(`**${path}/${user.id}`, async route => {
      if (route.request().method() !== 'PUT') { await route.continue(); return; }
      writes++;
      expect((await other.put(`${path}/${user.id}`, { headers, data: { can_approve: true } })).status()).toBe(200);
      await route.continue();
    });
    await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).click();
    await page.getByLabel('ID пользователя', { exact: true }).fill(user.id);
    await expect(panel(page).getByText('выбранные права заменят существующие', { exact: false })).toBeVisible();
    await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
    await expect(panel(page).getByRole('status').filter({ hasText: 'Доступ сохранён' })).toContainText('Право Approver отсутствует');
    await expect(row(page, user.id).getByRole('button', { name: 'Назначить Approver' })).toBeVisible();
    expect(writes).toBe(1);
    const access = await other.get(path);
    expect((await access.json()).items.find((item: { user_id: string }) => item.user_id === user.id).can_approve).toBe(false);
  } finally { await other.dispose(); }
});

test('failed reconciliation keeps uncertainty and the draft until a real read succeeds', async ({ page }) => {
  const { path } = await setup(page);
  const user = await newUser(page);
  let writes = 0;
  await page.route(`**${path}/${user.id}`, async route => {
    writes++;
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    await route.abort();
  });
  await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).click();
  await page.getByLabel('ID пользователя', { exact: true }).fill(user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toBeVisible();
  await page.route(`**${path}`, route => route.abort());
  await page.getByRole('button', { name: 'Проверить текущее состояние', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toBeVisible();
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toBeVisible();
  await expect(page.getByLabel('ID пользователя', { exact: true })).toHaveValue(user.id);
  await expect(page.getByRole('button', { name: 'Добавить в проект', exact: true })).toBeDisabled();
  await page.unroute(`**${path}`);
  await page.getByRole('button', { name: 'Проверить текущее состояние', exact: true }).click();
  await expect(panel(page).getByRole('status').filter({ hasText: 'Текущее состояние' })).toContainText('участник без права Approver');
  await expect(panel(page).getByRole('group', { name: 'Неопределённый результат' })).toHaveCount(0);
  expect(writes).toBe(1);
});

test('a committed late add cannot navigate or display success in another project', async ({ page }) => {
  const { path } = await setup(page);
  const other = await createProject(page, 'Other independent QA project');
  const user = await newUser(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void;
  const committed = new Promise<void>(resolve => { reached = resolve; });
  let writes = 0;
  await page.route(`**${path}/${user.id}`, async route => {
    writes++;
    const response = await route.fetch();
    expect(response.status()).toBe(200); reached(); await gate;
    await route.fulfill({ response }).catch(() => {});
  });
  await panel(page).getByRole('button', { name: 'Добавить участника', exact: true }).click();
  await page.getByLabel('ID пользователя', { exact: true }).fill(user.id);
  await page.getByRole('button', { name: 'Добавить в проект', exact: true }).click();
  await committed;
  await page.evaluate(id => { location.hash = `/projects/${id}/access`; }, other.id);
  await expect(page.getByRole('heading', { name: other.name, exact: true })).toBeVisible();
  release(); await page.unrouteAll({ behavior: 'wait' });
  await expect(row(page, user.id)).toHaveCount(0);
  await expect(panel(page).getByText('Доступ сохранён:', { exact: false })).toHaveCount(0);
  expect(writes).toBe(1);
});
