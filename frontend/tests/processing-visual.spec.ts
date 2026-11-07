import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { authenticatedHeaders, createProject, registerAndLogin } from './helpers';
import type { RunDTO } from '../src/processing/dto';

test('F1 Observer keeps real result, provenance, overview and responsive compositions', async ({ page }) => {
  test.skip(process.env.F2R_E2E_NO_PROVIDER === 'true', 'The visual result comes from the isolated synthetic backend worker.');
  test.setTimeout(120000);
  await registerAndLogin(page); const project = await createProject(page, 'F1 · проверка Observer');
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin); const root = `/api/v1/projects/${project.id}`;
  const sourceResponse = await page.request.post(root + '/sources', { headers, data: { kind: 'text', text: 'F1-ANNOTATED СИНТЕТИЧЕСКИЙ ТЕСТ: сохранять изменения. ё🙂\r\n' } });
  expect(sourceResponse.status()).toBe(201); const source = await sourceResponse.json();
  expect((await page.request.post(root + '/documents', { headers, data: { title: 'Контекст продукта', text: 'Синтетическая документация. Контекст, не отзыв.' } })).status()).toBe(201);
  const start = await page.request.post(root + '/runs', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
    data: { operation: 'extract_feedback', inputs: [{ kind: 'source', id: source.id, state_id: source.state_id }] } });
  expect(start.status()).toBe(202); let run: RunDTO = await start.json();
  await expect.poll(async () => { run = await (await page.request.get(root + '/runs/' + run.id)).json(); return run.state; }, { timeout: 45000 }).toBe('completed');
  expect(run.units[0].attempt!.synthetic).toBe(true); expect(run.units[0].attempt!.ai_performed).toBe(false);
  const finding = await (await page.request.get(root + '/findings/' + run.units[0].attempt!.finding_ids[0])).json();
  const evidence = finding.evidence[0]; const destination = resolve('..', 'docs', 'qa', 'frontend-text-processing'); mkdirSync(destination, { recursive: true });
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [section, suffix] of [
      ['overview', ''], ['processing', `/processing/runs/${run.id}`], ['findings', `/findings/${finding.id}`],
      ['fragment', `/findings/fragments/${evidence.id}/states/${evidence.state_id}`],
    ]) {
      await page.goto(`/#/projects/${project.id}${suffix}`);
      await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible();
      if (section === 'overview') {
        await expect(page.getByRole('region', { name: 'Материалы и обработка', exact: true }).locator('dd').first()).toHaveText('1');
        await expect(page.locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
      } else {
        if (section !== 'processing') await expect(page.getByRole('region', { name: 'Группы находок', exact: true })).toContainText('Сохранённых групп в этой выборке нет');
        if (section === 'processing') {
          await expect(page.getByRole('region', { name: 'Выбранное задание', exact: true })).toContainText('Синтетический результат');
          await expect(page.locator('.run-list li')).toHaveCount(1);
          await expect(page.getByRole('form', { name: 'Запуск обработки текста', exact: true }).getByRole('group', { name: 'Текстовые отзывы', exact: true }).getByRole('checkbox')).toHaveCount(1);
        } else if (section === 'findings') await expect(page.getByRole('region', { name: 'Выбранная находка', exact: true })).toContainText('Синтетический результат');
        else {
          const fragment = page.getByRole('region', { name: 'Точное состояние исходного фрагмента', exact: true });
          await expect(fragment).toContainText('Цитата точно соответствует границам');
          await expect(fragment).toContainText('Синтетический результат');
        }
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.mouse.move(0, 0);
      await expect(page).toHaveScreenshot(`f1-${section}-${width}.png`, {
        fullPage: true, animations: 'disabled', caret: 'hide',
        stylePath: resolve('tests', 'support', 'visual.css'), maxDiffPixelRatio: 0.001,
      });
      await page.screenshot({ path: resolve(destination, `${section}-${width}.png`), fullPage: true, animations: 'disabled' });
    }
  }
});
