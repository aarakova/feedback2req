import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { authenticatedHeaders, createProject, password, registerAndLogin, unique } from './helpers';
import type { TextSource } from '../src/api';
import type { InputRef, RunDTO } from '../src/processing/dto';
import { findingHref, processingInputHref, runHref } from '../src/routes';

const runPanel = (page: Page) => page.getByRole('region', { name: 'Выбранное задание', exact: true });
const form = (page: Page) => page.getByRole('form', { name: 'Запуск обработки текста', exact: true });
const noProvider = process.env.F2R_E2E_NO_PROVIDER === 'true';
const apiRoot = (id: string) => `/api/v1/projects/${id}`;
async function source(page: Page, projectId: string, text: string): Promise<TextSource> {
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const response = await page.request.post(`${apiRoot(projectId)}/sources`, { headers, data: { kind: 'text', text } });
  expect(response.status()).toBe(201); return response.json();
}
async function startApi(page: Page, projectId: string, inputs: InputRef[], operation = 'extract_feedback') {
  const key = crypto.randomUUID(); const headers = { ...await authenticatedHeaders(page.request, new URL(page.url()).origin), 'Idempotency-Key': key };
  const response = await page.request.post(`${apiRoot(projectId)}/runs`, { headers, data: { operation, inputs } });
  expect(response.status()).toBe(202); return { run: await response.json() as RunDTO, key };
}
const ref = (value: TextSource): InputRef => ({ kind: 'source', id: value.id, state_id: value.state_id });
async function terminal(page: Page, projectId: string, id: string): Promise<RunDTO> {
  let value: RunDTO | undefined;
  await expect.poll(async () => { const response = await page.request.get(`${apiRoot(projectId)}/runs/${id}`); expect(response.status()).toBe(200); value = await response.json(); return value!.state; }, { timeout: 45000 })
    .toMatch(/^(completed|failed|partial|cancelled)$/);
  return value!;
}
async function setup(page: Page, text = 'F1 тестовый текст ' + unique()) {
  await registerAndLogin(page); const project = await createProject(page, 'Обработка F1');
  const material = await source(page, project.id, text);
  await page.goto('/' + processingInputHref(project.id, ref(material)));
  await expect(form(page).getByRole('button', { name: 'Создать задание', exact: true })).toBeEnabled();
  return { project, material };
}

test.describe('real synthetic F1', () => {
  test.skip(noProvider, 'Positive paths require the explicitly synthetic test worker.');

  test('saved feedback explicitly creates a real task, displays running/completed and traces exact Unicode evidence', async ({ page }) => {
    test.setTimeout(90000); await registerAndLogin(page); const project = await createProject(page, 'Путь от текста к находке');
    await page.goto(`/#/projects/${project.id}/materials`);
    const text = 'F1-REPEAT 🧭 до ёж🙂\r\n снова ёж🙂\r\n конец е\u0301';
    await page.getByRole('region', { name: 'Отзывы', exact: true }).getByRole('button', { name: 'Добавить обратную связь', exact: true }).click();
    await page.getByLabel('Текст отзыва', { exact: true }).fill(text);
    const saved = page.waitForResponse(response => response.url().endsWith('/sources') && response.request().method() === 'POST');
    await page.getByRole('form', { name: 'Новая обратная связь', exact: true }).getByRole('button', { name: 'Сохранить', exact: true }).click();
    const material: TextSource = await (await saved).json();
    expect((await (await page.request.get(`${apiRoot(project.id)}/runs`)).json()).items).toEqual([]);
    await page.getByRole('region', { name: 'Просмотр материала', exact: true }).getByRole('link', { name: 'Обработать этот отзыв', exact: true }).click();
    const created = page.waitForResponse(response => response.url().endsWith('/runs') && response.request().method() === 'POST');
    await form(page).getByRole('button', { name: 'Создать задание', exact: true }).click();
    const response = await created; expect(response.status()).toBe(202);
    expect(response.request().postDataJSON()).toEqual({ operation: 'extract_feedback', inputs: [ref(material)] });
    expect((await response.request().allHeaders())['idempotency-key']).toMatch(/^[\da-f-]{36}$/);
    const run: RunDTO = await response.json(); expect(run.state).toBe('queued');
    const completed = await terminal(page, project.id, run.id); expect(completed.state).toBe('completed');
    await expect(runPanel(page)).toContainText('Синтетический результат', { timeout: 12000 });
    await expect(runPanel(page)).toContainText('Реальный AI-вызов не выполнялся.');
    await page.reload(); await expect(runPanel(page)).toContainText(run.id);
    await runPanel(page).getByRole('link', { name: 'Находки этой попытки →', exact: true }).click();
    await page.getByRole('link', { name: 'Открыть находку ↗', exact: true }).first().click();
    const detail = page.getByRole('region', { name: 'Выбранная находка', exact: true });
    for (const type of ['Проблема', 'Пожелание', 'Наблюдение', 'Потребность']) await expect(detail).toContainText(type);
    await expect(detail).toContainText('Синтетический результат');
    await detail.getByRole('link', { name: 'Открыть точное состояние фрагмента ↗', exact: true }).click();
    const fragment = page.getByRole('region', { name: 'Точное состояние исходного фрагмента', exact: true });
    const quote = material.text.includes('\r\n') ? 'ёж🙂\r\n' : 'ёж🙂\n';
    await expect(fragment.locator('blockquote p')).toHaveText(`«${quote}»`, { useInnerText: false });
    await expect(fragment).toContainText('Цитата точно соответствует границам');
    const found = await (await page.request.get(`${apiRoot(project.id)}/findings/${completed.units[0].attempt!.finding_ids[0]}`)).json();
    expect(found.evidence[0].quote).toBe(quote);
    expect(Array.from(material.text).slice(found.evidence[0].locator.start, found.evidence[0].locator.end).join('')).toBe(quote);
    await fragment.getByRole('link', { name: 'Перейти к исходному материалу', exact: true }).click();
    await expect(page.locator('.material-text')).toHaveText(material.text, { useInnerText: false });
    expect(await page.locator('.material-text').textContent()).toBe(material.text);
    await expect(page.getByRole('progressbar')).toHaveCount(0);
  });

  test('inspect_text accepts a document without AI, while extract never silently drops document selection', async ({ page }) => {
    await registerAndLogin(page); const project = await createProject(page); const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
    const text = 'Документ 🙂\r\nе\u0301'; const response = await page.request.post(`${apiRoot(project.id)}/documents`, { headers, data: { title: 'Контекст', text } });
    const document = await response.json();
    await page.goto('/' + processingInputHref(project.id, { kind: 'document', id: document.id, state_id: document.state_id }));
    await expect(form(page).getByLabel('Операция', { exact: true })).toHaveValue('inspect_text');
    await form(page).getByLabel('Операция', { exact: true }).selectOption('extract_feedback');
    await expect(form(page)).toContainText('Выбор не изменён автоматически');
    await expect(form(page).getByRole('button', { name: 'Создать задание', exact: true })).toBeDisabled();
    await form(page).getByLabel('Операция', { exact: true }).selectOption('inspect_text');
    await form(page).getByRole('button', { name: 'Создать задание', exact: true }).click();
    await expect(runPanel(page)).toContainText(`символов ${Array.from(text).length}`, { timeout: 20000 });
    await expect(runPanel(page)).toContainText(`UTF-8 байт ${Buffer.byteLength(text, 'utf8')}`);
    await expect(runPanel(page).getByRole('link', { name: 'Находки этой попытки →' })).toHaveCount(0);
  });

  test('unknown committed POST remains locked after reload and same-key replay resolves exactly one task', async ({ page }) => {
    const { project } = await setup(page); const path = `**${apiRoot(project.id)}/runs`; const keys: string[] = []; let createdId = '';
    await page.route(path, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      keys.push((await route.request().allHeaders())['idempotency-key']);
      const result = await route.fetch(); createdId = (await result.json()).id; await route.abort();
    });
    await form(page).getByRole('button', { name: 'Создать задание', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Неопределённый результат команды', exact: true })).toContainText('Результат команды неизвестен');
    const other = await createProject(page, 'Другой проект при неизвестном результате');
    await page.goto(`/#/projects/${other.id}/processing`);
    await expect(page.getByRole('region', { name: 'Неопределённый результат команды', exact: true })).toHaveCount(0);
    await page.goto(`/#/projects/${project.id}/processing`);
    await expect(page.getByRole('region', { name: 'Неопределённый результат команды', exact: true })).toContainText(keys[0]);
    await page.reload(); await expect(form(page).getByRole('button', { name: 'Создать задание', exact: true })).toBeDisabled();
    expect(keys).toHaveLength(1); await page.unroute(path);
    const replayed = page.waitForResponse(response => response.url().endsWith('/runs') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Повторить ту же команду с прежним ключом', exact: true }).click();
    const replay = await replayed; expect((await replay.json()).id).toBe(createdId); expect((await replay.request().allHeaders())['idempotency-key']).toBe(keys[0]);
    const runs = (await (await page.request.get(`${apiRoot(project.id)}/runs`)).json()).items;
    expect(runs).toHaveLength(1); expect(runs[0].id).toBe(createdId);
    await expect(page.getByRole('region', { name: 'Неопределённый результат команды', exact: true })).toHaveCount(0);
  });

  test('manual retry uses exact expected attempt and its own idempotency key without rewriting failure history', async ({ page }) => {
    const { project, material } = await setup(page, 'F1-ONCE ' + unique());
    const first = await startApi(page, project.id, [ref(material)]); const failed = await terminal(page, project.id, first.run.id); expect(failed.state).toBe('failed');
    await page.goto('/' + runHref(project.id, failed.id));
    await expect(runPanel(page)).toContainText('provider_error');
    const response = page.waitForResponse(response => response.url().endsWith('/retries') && response.request().method() === 'POST');
    await runPanel(page).getByRole('button', { name: 'Повторить неудачную операцию', exact: true }).click();
    const accepted = await response; expect(accepted.status()).toBe(202);
    expect(accepted.request().postDataJSON()).toEqual({ expected_attempt_id: failed.units[0].attempt!.id });
    expect((await accepted.request().allHeaders())['idempotency-key']).not.toBe(first.key);
    const retry: RunDTO = await accepted.json(); expect(retry.id).not.toBe(first.run.id);
    expect(retry.units[0].retry_of_attempt_id).toBe(failed.units[0].attempt!.id);
    expect((await terminal(page, project.id, retry.id)).state).toBe('completed');
    expect((await (await page.request.get(`${apiRoot(project.id)}/runs/${failed.id}`)).json()).state).toBe('failed');
  });

  test('partial runs keep failed and completed units distinct and expose annotations and empty coverage', async ({ page }) => {
    const { project, material } = await setup(page, 'F1-FAIL ' + unique());
    const good = await source(page, project.id, 'F1-ANNOTATED ' + unique());
    const value = await startApi(page, project.id, [ref(material), ref(good)]); const result = await terminal(page, project.id, value.run.id); expect(result.state).toBe('partial');
    await page.goto('/' + runHref(project.id, result.id));
    await expect(runPanel(page)).toContainText('Частично завершено'); await expect(runPanel(page)).toContainText('provider_error');
    await expect(runPanel(page)).toContainText('Какое ожидание нужно уточнить?');
    await expect(runPanel(page)).toContainText('Синтетическая неопределённость интерпретации');
    const empty = await source(page, project.id, 'F1-INSUFFICIENT ' + unique()); const noFindings = await startApi(page, project.id, [ref(empty)]);
    await terminal(page, project.id, noFindings.run.id); await page.goto('/' + runHref(project.id, noFindings.run.id));
    await expect(runPanel(page)).toContainText('недостаточно информации'); await expect(runPanel(page)).toContainText('находки не опубликованы');
  });

  test('overview uses authoritative material counts and newest run without replacing semantic KPI', async ({ page }) => {
    const { project, material } = await setup(page);
    for (let index = 0; index < 4; index++) await source(page, project.id, `Материал ${index}`);
    const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
    for (let index = 0; index < 3; index++) await page.request.post(`${apiRoot(project.id)}/documents`, { headers, data: { title: `Документ ${index}`, text: 'Контекст' } });
    let latest = '';
    for (let index = 0; index < 3; index++) latest = (await startApi(page, project.id, [ref(material)], 'inspect_text')).run.id;
    const paths: string[] = []; page.on('request', request => { if (request.url().includes('/api/')) paths.push(new URL(request.url()).pathname); });
    await page.goto(`/#/projects/${project.id}`);
    const panel = page.getByRole('region', { name: 'Материалы и обработка', exact: true });
    await expect(panel.locator('dd').nth(0)).toHaveText('5'); await expect(panel.locator('dd').nth(1)).toHaveText('3');
    await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
    await expect(panel.getByRole('link', { name: 'Последний запуск →' })).toHaveAttribute('href', `#/projects/${project.id}/processing/runs/${latest}`);
    expect(paths.some(path => /\/(sources|documents)$/.test(path))).toBe(false);
    await panel.getByRole('link', { name: 'Последний запуск →' }).click(); await expect(runPanel(page)).toContainText(latest);
    await page.reload(); await expect(runPanel(page)).toContainText(latest);
    await page.getByRole('button', { name: 'Показать ещё запуски', exact: true }).click(); await expect(page.locator('.run-list li')).toHaveCount(3);
  });

  test('stale evidence stays historical and failed old input requires an explicit new-state command', async ({ page }) => {
    const data = JSON.parse(readFileSync(resolve('..', '.local/frontend-f1/seed-manifest.json'), 'utf8'));
    await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(data.login); await page.getByLabel('Пароль', { exact: true }).fill(password); await page.getByRole('button', { name: 'Войти', exact: true }).click();
    await page.goto('/' + findingHref(data.projectId, data.findingId));
    const detail = page.getByRole('region', { name: 'Выбранная находка', exact: true }); await expect(detail).toContainText('Требует актуализации');
    await detail.getByRole('link', { name: 'Открыть точное состояние фрагмента ↗', exact: true }).click();
    const fragment = page.getByRole('region', { name: 'Точное состояние исходного фрагмента', exact: true }); await expect(fragment).toContainText('Источник изменился');
    await fragment.getByRole('link', { name: 'Перейти к исходному материалу', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Просмотр материала', exact: true })).toContainText('Новый текст не подменяет сохранённую цитату');
    await expect(page.locator('.material-text')).toHaveCount(0);
    await page.goto('/' + runHref(data.projectId, data.failedRunId)); let retries = 0;
    page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/retries')) retries++; });
    await runPanel(page).getByRole('button', { name: 'Повторить неудачную операцию', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Состояние материала изменилось'); expect(retries).toBe(0);
    await page.getByRole('button', { name: 'Перечитать материалы и сбросить выбор', exact: true }).click();
    const choices = form(page).getByRole('group', { name: 'Текстовые отзывы', exact: true });
    await choices.getByRole('checkbox').check();
    const created = page.waitForResponse(response => response.url().endsWith('/runs') && response.request().method() === 'POST');
    await form(page).getByRole('button', { name: 'Создать задание', exact: true }).click();
    expect((await created).request().postDataJSON().inputs[0].state_id).toBe(data.current.state_id);
  });

  test('running status is real and automatic polling stops once the run is terminal', async ({ page }) => {
    const { project, material } = await setup(page, 'F1-SLOW ' + unique());
    const value = await startApi(page, project.id, [ref(material)]); let reads = 0;
    page.on('request', request => { if (new URL(request.url()).pathname.endsWith(`/runs/${value.run.id}`) && request.method() === 'GET') reads++; });
    await page.goto('/' + runHref(project.id, value.run.id));
    // Queue waiting is independent of execution time; the previous run waited 9.6s before claim.
    await expect(runPanel(page)).toContainText('Выполняется', { timeout: 30000 });
    await expect(runPanel(page)).toContainText('Завершено', { timeout: 20000 });
    const stopped = reads; await page.waitForTimeout(2500); expect(reads).toBe(stopped);
    await expect(page.getByRole('progressbar')).toHaveCount(0);
  });

  test('exact CRLF evidence uses code points and opens the same source state without text search', async ({ page }) => {
    const text = 'F1-REPEAT 🙂 до ёж🙂\r\n затем ёж🙂\r\n после';
    const { project, material } = await setup(page, text);
    const value = await startApi(page, project.id, [ref(material)]); const result = await terminal(page, project.id, value.run.id);
    const item = await (await page.request.get(`${apiRoot(project.id)}/findings/${result.units[0].attempt!.finding_ids[0]}`)).json();
    const evidence = item.evidence[0]; expect(evidence.quote).toBe('ёж🙂\r\n');
    expect(Array.from(text).slice(evidence.locator.start, evidence.locator.end).join('')).toBe(evidence.quote);
    await page.goto(`/#/projects/${project.id}/findings/fragments/${evidence.id}/states/${evidence.state_id}`);
    const fragment = page.getByRole('region', { name: 'Точное состояние исходного фрагмента', exact: true });
    await expect(fragment).toContainText('Цитата точно соответствует границам');
    await fragment.getByRole('link', { name: 'Перейти к исходному материалу', exact: true }).click();
    expect(await page.locator('.material-text').textContent()).toBe(text);
  });

  test('lost retry response replays the identical retry command and preserves a single successor', async ({ page }) => {
    const { project, material } = await setup(page, 'F1-ONCE ' + unique());
    const value = await startApi(page, project.id, [ref(material)]); const failed = await terminal(page, project.id, value.run.id);
    await page.goto('/' + runHref(project.id, failed.id)); const target = `**${apiRoot(project.id)}/units/${failed.units[0].id}/retries`;
    let key = ''; let successor = '';
    await page.route(target, async route => { key = (await route.request().allHeaders())['idempotency-key']; const response = await route.fetch(); successor = (await response.json()).id; await route.abort(); });
    await runPanel(page).getByRole('button', { name: 'Повторить неудачную операцию', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Неопределённый результат команды', exact: true })).toContainText('Результат команды неизвестен');
    await page.reload(); await page.unroute(target);
    const response = page.waitForResponse(response => response.url().endsWith('/retries') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Повторить ту же команду с прежним ключом', exact: true }).click(); const repeated = await response;
    expect((await repeated.request().allHeaders())['idempotency-key']).toBe(key); expect((await repeated.json()).id).toBe(successor);
    const firstPage = await (await page.request.get(`${apiRoot(project.id)}/runs`)).json(); expect(firstPage.items).toHaveLength(2); expect(firstPage.next_cursor).toBeNull();
  });

  test('material pagination exposes every choice and the explicit 32-input limit blocks the 33rd without submission', async ({ page }) => {
    test.setTimeout(90000); const { project } = await setup(page);
    for (let index = 1; index < 33; index++) await source(page, project.id, `Материал ${index}`);
    await page.goto(`/#/projects/${project.id}/processing`);
    const group = form(page).getByRole('group', { name: 'Текстовые отзывы', exact: true });
    for (let count = 2; count <= 32; count += 2) {
      await expect(group.getByRole('checkbox')).toHaveCount(count);
      await group.getByRole('checkbox').nth(count - 2).check(); await group.getByRole('checkbox').nth(count - 1).check();
      await group.getByRole('button', { name: 'Показать ещё материалы', exact: true }).click();
    }
    await expect(group.getByRole('checkbox')).toHaveCount(33); await expect(group.getByRole('checkbox').nth(32)).toBeDisabled();
    await expect(form(page)).toContainText('Выбрано 32 из допустимых 32');
    expect((await (await page.request.get(`${apiRoot(project.id)}/runs`)).json()).items).toEqual([]);
  });

  test('findings paginate without fabricating F2 groups or requirement relationships', async ({ page }) => {
    const { project, material } = await setup(page); const inputs = [ref(material)];
    for (let index = 0; index < 2; index++) inputs.push(ref(await source(page, project.id, 'F1-INFERRED ' + unique())));
    const value = await startApi(page, project.id, inputs); await terminal(page, project.id, value.run.id);
    await page.goto(`/#/projects/${project.id}/findings`);
    const groups = page.getByRole('region', { name: 'Группы находок', exact: true });
    await expect(groups).toContainText('Группировка F2 пока не подключена'); await expect(groups).not.toContainText('Загружено 0');
    const all = page.getByRole('region', { name: 'Все находки', exact: true }); await expect(all.locator('.finding-card')).toHaveCount(2);
    await page.getByRole('button', { name: 'Показать ещё находки', exact: true }).click(); await expect(all.locator('.finding-card')).toHaveCount(3);
    await expect(all).toContainText('Интерпретация'); await expect(all).toContainText('Связи с требованиями пока не подключены');
  });

  test('late run responses and saved command metadata cannot leak into another project', async ({ page }) => {
    const { project, material } = await setup(page, 'F1 старый проект ' + unique()); const other = await createProject(page, 'Новый контекст');
    const value = await startApi(page, project.id, [ref(material)], 'inspect_text');
    let release!: () => void; let requested!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; }); const arrived = new Promise<void>(resolve => { requested = resolve; });
    await page.route(`**${apiRoot(project.id)}/runs/${value.run.id}`, async route => { const response = await route.fetch(); requested(); await gate; try { await route.fulfill({ response }); } catch { /* The old page aborts the request. */ } });
    await page.goto('/' + runHref(project.id, value.run.id)); await arrived;
    await page.evaluate(id => { location.hash = `/projects/${id}/processing`; }, other.id);
    await expect(page.getByRole('heading', { name: other.name, exact: true })).toBeVisible(); release();
    await expect(page.locator('main')).not.toContainText(value.run.id); await expect(page.locator('main')).not.toContainText(material.text);
    await expect(form(page).getByRole('button', { name: 'Создать задание', exact: true })).toBeDisabled();
  });

  test('membership revoked during processing removes protected run and material data', async ({ page, browser }) => {
    const { project, material } = await setup(page, 'F1-SLOW закрытая обратная связь ' + unique());
    const origin = new URL(page.url()).origin; const context = await browser.newContext({ baseURL: origin }); const member = await context.newPage();
    try {
      await registerAndLogin(member); const actor = (await (await member.request.get('/api/v1/auth/session')).json()).user;
      const headers = await authenticatedHeaders(page.request, origin);
      expect((await page.request.put(`${apiRoot(project.id)}/access/${actor.id}`, { headers, data: { can_approve: false } })).status()).toBe(200);
      await member.goto('/' + processingInputHref(project.id, ref(material)));
      const response = member.waitForResponse(response => response.url().endsWith('/runs') && response.request().method() === 'POST');
      await form(member).getByRole('button', { name: 'Создать задание', exact: true }).click(); const run: RunDTO = await (await response).json();
      await expect(runPanel(member)).toContainText(run.id);
      expect((await page.request.delete(`${apiRoot(project.id)}/access/${actor.id}`, { headers })).status()).toBe(204);
      await expect(member.locator('.processing-runtime')).toHaveCount(0, { timeout: 15000 });
      await expect(member.getByRole('heading', { name: project.name, exact: true })).toHaveCount(0);
      await expect(member.locator('main')).not.toContainText(material.text);
      expect((await member.request.get(`${apiRoot(project.id)}/runs/${run.id}`)).status()).toBe(404);
    } finally { await context.close(); }
  });

  test('polling is bounded even for repeated delayed queued snapshots and manual refresh resumes a real read', async ({ page }) => {
    test.setTimeout(90000); const { project, material } = await setup(page); const value = await startApi(page, project.id, [ref(material)]);
    const path = `**${apiRoot(project.id)}/runs/${value.run.id}`; let reads = 0;
    await page.route(path, async route => { reads++; await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value.run) }); });
    await page.clock.install(); await page.goto('/' + runHref(project.id, value.run.id)); await expect(runPanel(page)).toContainText('В очереди'); await page.clock.pauseAt(new Date());
    const initialReads = reads; expect(initialReads).toBeGreaterThanOrEqual(1); expect(initialReads).toBeLessThanOrEqual(2); // StrictMode can abort its first setup read.
    for (let index = 1; index < 60; index++) {
      const response = page.waitForResponse(response => response.url().endsWith(`/runs/${value.run.id}`));
      await page.clock.runFor(2000); await (await response).finished(); await page.evaluate(() => Promise.resolve()); await page.clock.runFor(1);
    }
    await expect(page.getByText('Автообновление приостановлено.', { exact: false })).toBeVisible(); expect(reads).toBe(initialReads + 59);
    await page.clock.runFor(20000); expect(reads).toBe(initialReads + 59); await page.unroute(path);
    await runPanel(page).getByRole('button', { name: 'Обновить состояние', exact: true }).dispatchEvent('click');
    await page.clock.resume(); await expect(runPanel(page)).toContainText('Завершено', { timeout: 15000 });
  });

  test('terminal backend reason codes remain explicit and cancelled units cannot be retried', async ({ page }) => {
    const data = JSON.parse(readFileSync(resolve('..', '.local/frontend-f1/seed-manifest.json'), 'utf8'));
    await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(data.login); await page.getByLabel('Пароль', { exact: true }).fill(password); await page.getByRole('button', { name: 'Войти', exact: true }).click();
    for (const [reason, id] of Object.entries(data.reasons)) {
      await page.goto('/' + runHref(data.projectId, String(id))); await expect(runPanel(page)).toContainText(reason);
      if (reason === 'input_changed' || reason === 'access_revoked') await expect(runPanel(page).getByRole('button', { name: 'Повторить неудачную операцию' })).toHaveCount(0);
    }
  });
});

test('unconfigured provider fails honestly instead of generating demo findings', async ({ page }) => {
  test.skip(!noProvider, 'Run separately with the task-owned worker configured without a provider.');
  const { project, material } = await setup(page);
  const response = await startApi(page, project.id, [ref(material)]); const result = await terminal(page, project.id, response.run.id);
  expect(result.state).toBe('failed'); expect(result.units[0].attempt!.reason_code).toBe('provider_not_configured');
  expect(result.units[0].attempt!.ai_performed).toBe(false); expect(result.units[0].attempt!.finding_ids).toEqual([]);
  await page.goto('/' + runHref(project.id, result.id)); await expect(runPanel(page)).toContainText('AI-провайдер не настроен');
  expect((await (await page.request.get(`${apiRoot(project.id)}/findings`)).json()).items).toEqual([]);
});
