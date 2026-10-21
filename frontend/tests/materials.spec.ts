import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';

const sources = (page: Page) => page.getByRole('region', { name: 'Отзывы', exact: true });
const documents = (page: Page) => page.getByRole('region', { name: 'Документы продукта', exact: true });
const detail = (page: Page) => page.getByRole('region', { name: 'Просмотр материала' });
const base = (id: string) => `/api/v1/projects/${id}`;
const sectionUrl = (id: string) => `#/projects/${id}/materials`;
const sample = '  Отзыв 🧭 е\u0301\tстрока\r\n  вторая строка\n\n<script>alert("пример")</script>  ';

async function openMaterials(page: Page) {
  await registerAndLogin(page);
  const project = await createProject(page, 'Проект текстовых материалов');
  await page.goto(`/${sectionUrl(project.id)}`);
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
  return project;
}

test('owner creates both materials, exact submitted JSON persists, selection reloads and text is safe', async ({ page }, testInfo) => {
  const project = await openMaterials(page);
  await expect(sources(page).getByText('Отзывов пока нет.')).toBeVisible();
  await expect(documents(page).getByText('Документов пока нет.')).toBeVisible();
  await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
  await page.getByLabel('Текст отзыва', { exact: true }).fill(sample);
  const entered = await page.getByLabel('Текст отзыва', { exact: true }).inputValue();
  expect(entered).toContain('е\u0301');
  expect(entered).not.toContain('\r'); // textarea normalizes CRLF before submission.
  const sourceResponse = page.waitForResponse(response => response.url().endsWith(`${base(project.id)}/sources`) && response.request().method() === 'POST');
  await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  const createdSource = await sourceResponse;
  expect(createdSource.status()).toBe(201);
  expect(createdSource.request().postDataJSON()).toEqual({ kind: 'text', text: entered });
  const source = await createdSource.json();
  expect(source.text).toBe(entered);
  await expect(sources(page).getByRole('status').filter({ hasText: 'Обратная связь сохранена' })).toBeVisible();
  await expect(detail(page).getByLabel('Сохранённый текст')).toHaveText(entered, { useInnerText: false });
  expect(await detail(page).getByLabel('Сохранённый текст').textContent()).toBe(entered);
  await expect(detail(page).locator('script')).toHaveCount(0);
  await page.reload();
  await expect(detail(page).getByLabel('Сохранённый текст')).toBeVisible();
  expect(await detail(page).getByLabel('Сохранённый текст').textContent()).toBe(entered);
  await documents(page).getByRole('button', { name: 'Добавить документацию' }).click();
  await page.getByLabel('Название документа', { exact: true }).fill('  Описание продукта 🧭 е\u0301  ');
  await page.getByLabel('Текст документа', { exact: true }).fill('  Контекст\tпродукта\n' + 'длинное_слово_'.repeat(100));
  await page.screenshot({ path: testInfo.outputPath('forms-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('forms-mobile.png'), fullPage: true });
  const documentResponse = page.waitForResponse(response => response.url().endsWith(`${base(project.id)}/documents`) && response.request().method() === 'POST');
  const documentText = await page.getByLabel('Текст документа', { exact: true }).inputValue();
  await documents(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  const createdDocument = await documentResponse;
  expect(createdDocument.status()).toBe(201);
  const document = await createdDocument.json();
  expect(document.title).toBe('  Описание продукта 🧭 е\u0301  ');
  expect(document.text).toBe(documentText);
  await expect(detail(page).getByRole('heading', { name: document.title, exact: true })).toBeVisible();
  expect(await detail(page).getByLabel('Сохранённый текст').textContent()).toBe(documentText);
  await page.reload();
  await expect(detail(page).getByLabel('Сохранённый текст')).toBeVisible();
  expect(await detail(page).getByLabel('Сохранённый текст').textContent()).toBe(documentText);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('materials-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.screenshot({ path: testInfo.outputPath('materials-desktop.png'), fullPage: true });
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []]);
  await page.getByRole('link', { name: 'Обзор проекта' }).click();
  await expect(page.getByRole('heading', { name: 'Ваши полномочия' })).toBeVisible();
  await page.getByRole('link', { name: 'Материалы', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
});

test('independent cursor pages, and a material outside the first page opens by ID with exact CRLF', async ({ page }) => {
  const project = await openMaterials(page);
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const seeded = [];
  for (let i = 0; i < 3; i++) {
    const source = await page.request.post(`${base(project.id)}/sources`, { headers, data: { kind: 'text', text: sample + i } });
    expect(source.status()).toBe(201);
    seeded.push(await source.json());
    expect((await page.request.post(`${base(project.id)}/documents`, { headers, data: { title: `Документ ${i}`, text: sample } })).status()).toBe(201);
  }
  await page.reload();
  await expect(sources(page).locator('.material-list li')).toHaveCount(2);
  await expect(documents(page).locator('.material-list li')).toHaveCount(2);
  await sources(page).getByRole('button', { name: 'Показать ещё' }).click();
  await expect(sources(page).locator('.material-list li')).toHaveCount(3);
  await expect(documents(page).locator('.material-list li')).toHaveCount(2);
  await documents(page).getByRole('button', { name: 'Показать ещё' }).click();
  await expect(documents(page).locator('.material-list li')).toHaveCount(3);
  const last = seeded.sort((a, b) => a.id.localeCompare(b.id))[2];
  await page.goto(`/${sectionUrl(project.id)}/sources/${last.id}`);
  await page.reload();
  await expect(sources(page).locator('.material-list li')).toHaveCount(2);
  await expect(detail(page).getByLabel('Сохранённый текст')).toBeVisible();
  expect(await detail(page).getByLabel('Сохранённый текст').textContent()).toBe(last.text);
  expect(last.text).toContain('\r\n'); // API setup preserves CRLF; textarea wasn't involved.
});

test('a new material is viewable even when its list fails; the other collection stays available', async ({ page }) => {
  const project = await openMaterials(page);
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  expect((await page.request.post(`${base(project.id)}/documents`, { headers, data: { title: 'Контекст доступен', text: 'Документация' } })).status()).toBe(201);
  await page.reload();
  await expect(documents(page).getByText('Контекст доступен', { exact: true })).toBeVisible();
  await page.route(`**${base(project.id)}/sources`, route => route.request().method() === 'GET' ? route.abort() : route.continue());
  await sources(page).getByRole('button', { name: 'Обновить список' }).click();
  await expect(sources(page).getByRole('alert')).toContainText('Не удалось связаться');
  await expect(documents(page).getByText('Контекст доступен', { exact: true })).toBeVisible();
  await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
  await page.getByLabel('Текст отзыва', { exact: true }).fill('Новый отзыв без первой страницы');
  await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(sources(page).getByRole('status').filter({ hasText: 'Обратная связь сохранена' })).toBeVisible();
  await expect(detail(page).getByLabel('Сохранённый текст')).toHaveText('Новый отзыв без первой страницы');
  await page.unroute(`**${base(project.id)}/sources`);
  await sources(page).getByRole('button', { name: 'Повторить загрузку' }).click();
  await expect(sources(page).locator('.material-list li')).toHaveCount(1);
  await page.route(`**${base(project.id)}/documents`, route => route.abort());
  await documents(page).getByRole('button', { name: 'Обновить список' }).click();
  await expect(documents(page).getByRole('alert')).toBeVisible();
  await expect(sources(page).locator('.material-list li')).toHaveCount(1);
});

test('server validation leaves draft intact and rejects configured text and body limits', async ({ page }) => {
  const project = await openMaterials(page);
  await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
  const input = page.getByLabel('Текст отзыва', { exact: true });
  for (const [text, code] of [['a'.repeat(8193), 'text_too_large'], ['ж'.repeat(8192), 'body_too_large'], ['bad\0text', 'invalid_text']]) {
    await input.fill(text);
    const response = page.waitForResponse(response => response.url().endsWith(`${base(project.id)}/sources`) && response.request().method() === 'POST');
    await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
    expect((await (await response).json()).error.code).toBe(code);
    await expect(sources(page).getByRole('alert')).toBeVisible();
    await expect(input).toHaveValue(text);
    await expect(sources(page).getByText('Обратная связь сохранена.')).toHaveCount(0);
  }
  await input.fill('  \t\n ');
  await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(sources(page).getByRole('alert')).toContainText('Заполните непустой текст');
  await documents(page).getByRole('button', { name: 'Добавить документацию' }).click();
  await page.getByLabel('Название документа', { exact: true }).fill('я'.repeat(201));
  await page.getByLabel('Текст документа', { exact: true }).fill('Контекст');
  const response = page.waitForResponse(response => response.url().endsWith(`${base(project.id)}/documents`) && response.request().method() === 'POST');
  await documents(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  expect((await (await response).json()).error.code).toBe('invalid_request');
  await expect(page.getByLabel('Название документа', { exact: true })).toHaveValue('я'.repeat(201));
});

test('lost POST response keeps draft, has no automatic retry or false success, and refresh finds saved material', async ({ page }) => {
  const project = await openMaterials(page);
  let posts = 0;
  await page.route(`**${base(project.id)}/sources`, async route => {
    if (route.request().method() !== 'POST') { await route.continue(); return; }
    posts++;
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.abort(); // Real backend saved it; the client did not receive success.
  });
  await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
  await page.getByLabel('Текст отзыва', { exact: true }).fill('Не повторять сохранение автоматически');
  await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(sources(page).getByText('Результат сохранения неизвестен:', { exact: false })).toBeVisible();
  await expect(page.getByLabel('Текст отзыва', { exact: true })).toHaveValue('Не повторять сохранение автоматически');
  await expect(sources(page).getByText('Обратная связь сохранена.')).toHaveCount(0);
  await sources(page).getByRole('button', { name: 'Обновить список перед повтором' }).click();
  await expect(sources(page).locator('.material-list li')).toHaveCount(1);
  expect(posts).toBe(1);
});

test('500 is an error with a retained document draft and sending disables duplicate submit', async ({ page }) => {
  const project = await openMaterials(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let posts = 0;
  await page.route(`**${base(project.id)}/documents`, async route => {
    if (route.request().method() !== 'POST') { await route.continue(); return; }
    posts++; await gate;
    await route.fulfill({ status: 500, json: { error: { code: 'internal_error' } } });
  });
  await documents(page).getByRole('button', { name: 'Добавить документацию' }).click();
  await page.getByLabel('Название документа', { exact: true }).fill('Черновик');
  await page.getByLabel('Текст документа', { exact: true }).fill(sample);
  await documents(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(documents(page).getByRole('button', { name: 'Сохраняем…', exact: true })).toBeDisabled();
  release();
  await expect(documents(page).getByRole('alert')).toContainText('Сервер не смог');
  await expect(page.getByLabel('Название документа', { exact: true })).toHaveValue('Черновик');
  expect(posts).toBe(1);
});

test('member and approver add materials, outsider is denied, and revoked membership hides every material', async ({ page, playwright }) => {
  await registerAndLogin(page);
  const origin = new URL(page.url()).origin;
  const member = await (await page.request.get('/api/v1/auth/session')).json();
  const owner = await playwright.request.newContext({ baseURL: origin, extraHTTPHeaders: { Origin: origin } });
  try {
    const login = unique();
    expect((await owner.post('/api/v1/auth/register', { data: { login, password } })).status()).toBe(201);
    expect((await owner.post('/api/v1/auth/session', { data: { login, password } })).status()).toBe(200);
    const headers = await authenticatedHeaders(owner, origin);
    const project = await (await owner.post('/api/v1/projects', { headers, data: { name: 'Участник и материалы' } })).json();
    await page.goto(`/${sectionUrl(project.id)}`);
    await expect(page.getByRole('alert')).toContainText('Проект не найден');
    await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toHaveCount(0);
    const access = `${base(project.id)}/access/${member.user.id}`;
    expect((await owner.put(access, { headers, data: { can_approve: false } })).status()).toBe(200);
    await page.getByRole('button', { name: 'Повторить запрос' }).click();
    await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
    await page.getByLabel('Текст отзыва', { exact: true }).fill('Материал участника');
    await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect(detail(page).getByLabel('Сохранённый текст')).toHaveText('Материал участника');
    expect((await owner.put(access, { headers, data: { can_approve: true } })).status()).toBe(200);
    await documents(page).getByRole('button', { name: 'Добавить документацию' }).click();
    await page.getByLabel('Название документа', { exact: true }).fill('Контекст участника');
    await page.getByLabel('Текст документа', { exact: true }).fill('Текст контекста');
    await documents(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect(detail(page).getByLabel('Сохранённый текст')).toHaveText('Текст контекста');
    expect((await owner.delete(access, { headers })).status()).toBe(204);
    await sources(page).getByRole('button', { name: 'Обновить список' }).click();
    await expect(page.getByRole('alert')).toContainText('Доступ мог быть отозван');
    await expect(page.getByText('Текст контекста', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Контекст участника', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Повторить запрос' }).click();
    await expect(page.getByRole('alert')).toContainText('Проект не найден');
  } finally { await owner.dispose(); }
});

for (const action of ['logout', 'switch project'] as const) {
  test(`late material response cannot return data after ${action}`, async ({ page }) => {
    const project = await openMaterials(page);
    const other = await createProject(page, 'Другой проект');
    const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
    const response = await page.request.post(`${base(project.id)}/sources`, { headers, data: { kind: 'text', text: 'Прежний материал' } });
    const material = await response.json();
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let reached!: () => void;
    const intercepted = new Promise<void>(resolve => { reached = resolve; });
    await page.route(`**${base(project.id)}/sources/${material.id}`, async route => {
      const response = await route.fetch(); reached(); await gate;
      await route.fulfill({ response }).catch(() => {});
    });
    await page.evaluate(hash => { location.hash = hash; }, `${sectionUrl(project.id)}/sources/${material.id}`);
    await intercepted;
    if (action === 'logout') {
      await page.getByRole('button', { name: 'Выйти', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
    } else {
      await page.evaluate(hash => { location.hash = hash; }, sectionUrl(other.id));
      await expect(page.getByRole('heading', { name: other.name, exact: true })).toBeVisible();
      await expect(sources(page).getByText('Отзывов пока нет.')).toBeVisible();
    }
    release();
    await page.unrouteAll({ behavior: 'wait' });
    await expect(page.getByText('Прежний материал', { exact: true })).toHaveCount(0);
    await expect(detail(page)).toHaveCount(0);
  });
}

test('401 on a material request clears all protected screens', async ({ page }) => {
  const project = await openMaterials(page);
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await sources(page).getByRole('button', { name: 'Обновить список' }).click();
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveCount(0);
});

test('rechecking a valid session retains an errored draft and hides project data until access is checked', async ({ page }) => {
  const project = await openMaterials(page);
  await sources(page).getByRole('button', { name: 'Добавить обратную связь' }).click();
  const text = 'Черновик после ошибки 🧭 е\u0301';
  await page.getByLabel('Текст отзыва', { exact: true }).fill(text);
  await page.route(`**${base(project.id)}/sources`, route => route.request().method() === 'POST'
    ? route.fulfill({ status: 500, json: { error: { code: 'internal_error' } } }) : route.continue());
  await sources(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(sources(page).getByRole('alert')).toBeVisible();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let reached!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  await page.route(`**${base(project.id)}`, async route => {
    const response = await route.fetch(); reached(); await gate;
    await route.fulfill({ response });
  });
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await intercepted;
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).not.toBeVisible();
  release();
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
  await expect(page.getByLabel('Текст отзыва', { exact: true })).toHaveValue(text);
  await expect(sources(page).getByRole('alert')).toBeVisible();
  const session = await (await page.request.get('/api/v1/auth/session')).json();
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  expect((await page.request.delete('/api/v1/auth/session', { headers })).status()).toBe(204);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await page.getByLabel('Логин', { exact: true }).fill(session.user.login);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toBeVisible();
  await expect(page.getByLabel('Текст отзыва', { exact: true })).toHaveCount(0);
  const otherLogin = unique();
  const origin = new URL(page.url()).origin;
  expect((await page.request.post('/api/v1/auth/register', { headers: { Origin: origin }, data: { login: otherLogin, password } })).status()).toBe(201);
  expect((await page.request.post('/api/v1/auth/session', { headers: { Origin: origin }, data: { login: otherLogin, password } })).status()).toBe(200);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('alert')).toContainText('Проект не найден');
  await expect(page.getByRole('heading', { name: 'Материалы', exact: true })).toHaveCount(0);
});
