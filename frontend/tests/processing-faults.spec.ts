import { expect, test } from '@playwright/test';
import { authenticatedHeaders, createProject, registerAndLogin } from './helpers';

test('temporary run read errors stop after bounded backoff and manual refresh reads the real task', async ({ page }) => {
  await registerAndLogin(page);
  const project = await createProject(page, 'Временная недоступность F1');
  const root = `/api/v1/projects/${project.id}`;
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const saved = await page.request.post(root + '/sources', { headers, data: { kind: 'text', text: 'Технический тест восстановления чтения.' } });
  expect(saved.status()).toBe(201); const input = await saved.json();
  const started = await page.request.post(root + '/runs', {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
    data: { operation: 'inspect_text', inputs: [{ kind: 'source', id: input.id, state_id: input.state_id }] },
  });
  expect(started.status()).toBe(202); const run = await started.json();
  await expect.poll(async () => (await (await page.request.get(root + '/runs/' + run.id)).json()).state, { timeout: 45000 }).toBe('completed');
  const path = `**${root}/runs/${run.id}`; let reads = 0;
  await page.route(path, async route => { reads++; await route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":{"code":"http_error"}}' }); });
  await page.clock.install(); await page.goto(`/#/projects/${project.id}/processing/runs/${run.id}`);
  const panel = page.getByRole('region', { name: 'Выбранное задание', exact: true });
  await expect(panel.getByRole('alert')).toBeVisible(); await page.clock.pauseAt(new Date());
  for (const delay of [5000, 10000]) {
    const response = page.waitForResponse(response => response.url().endsWith('/runs/' + run.id));
    await page.clock.runFor(delay); await (await response).finished(); await page.evaluate(() => Promise.resolve()); await page.clock.runFor(1);
  }
  await expect(panel).toContainText('Автообновление приостановлено.');
  const stopped = reads; expect(stopped).toBeGreaterThanOrEqual(3); expect(stopped).toBeLessThanOrEqual(4);
  await page.clock.runFor(30000); expect(reads).toBe(stopped);
  await page.unroute(path); await panel.getByRole('button', { name: 'Обновить состояние', exact: true }).dispatchEvent('click');
  await page.clock.resume(); await expect(panel).toContainText('Завершено'); await expect(panel.getByRole('alert')).toHaveCount(0);
});
