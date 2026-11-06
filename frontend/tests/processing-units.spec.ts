import { expect, test } from '@playwright/test';
const deployed = ['compose', 'built'].includes(process.env.F2R_E2E_MODE ?? '');
test.skip(deployed, 'Browser unit checks import source modules only in Vite; production entry excludes them.');

test('F1 adapters preserve exact Unicode coordinates, provenance and unavailable F2', async ({ page }) => {
  await page.goto('/tests/fixtures/observer.html?section=findings');
  const value = await page.evaluate(async () => {
    const path = '/src/processing/adapters.ts'; const adapter = await import(/* @vite-ignore */ path);
    const source = { id: 's', state_id: 's1', text: 'до🙂ёж\r\nпосле' };
    const fragment = { id: 'f', state_id: 'f1', attempt_id: 'a', source_ref: { kind: 'feedback_source', id: 's', state_id: 's1' },
      text_ref: { kind: 'feedback_source', id: 's', state_id: 's1' }, quote: '🙂ёж\r\n', locator: { start: 2, end: 7 }, reliability: 'usable' };
    const finding = { id: 'n', state_id: 'n1', text: 'Тестовая интерпретация', types: ['problem', 'request', 'observation', 'need'], mode: 'inferred', authorship: 'ai',
      synthetic: true, attempt_id: 'a', created_at: '2026-01-01T00:00:00Z', freshness: 'requires_update', evidence: [fragment],
      coverage: [{ input_key: 's1', reviewed: true, disposition: 'insufficient_information', reason: 'Нужно уточнение' }],
      annotations: { questions: [], uncertainties: [] }, provider: 'test', model: 'synthetic', ai_performed: false };
    return { exact: adapter.exactFragmentText(fragment, source), staleMatch: adapter.exactFragmentText(fragment, { ...source, state_id: 's2' }),
      wrongCoordinates: adapter.exactFragmentText({ ...fragment, locator: { start: 2, end: 8 } }, source), view: adapter.findingsView([finding]),
      unconfirmed: adapter.aiLabel(null), notPerformed: adapter.aiLabel(false), noLeak: adapter.reasonMessage('private-provider-stacktrace') };
  });
  expect(value.exact).toBe(true); expect(value.staleMatch).toBe(false); expect(value.wrongCoordinates).toBe(false);
  expect(value.view.groupsAvailable).toBe(false); expect(value.view.relationsAvailable).toBe(false); expect(value.view.groups).toEqual([]);
  const finding = value.view.findings[0];
  expect(finding.types).toEqual(['Проблема', 'Пожелание', 'Наблюдение', 'Потребность']); expect(finding.originLabel).toBe('Интерпретация');
  expect(finding.extraction.synthetic).toBe(true); expect(finding.extraction.stale).toBe(true);
  expect(finding.extraction.coverage.join(' ')).toContain('недостаточно информации');
  expect(finding.evidence[0].quote).toBe('🙂ёж\r\n'); expect(finding.evidence[0].fragment.sourceStateId).toBe('s1');
  expect(value.unconfirmed).toContain('не подтверждён'); expect(value.notPerformed).toContain('не выполнялся'); expect(value.noLeak).not.toContain('private-provider-stacktrace');
});

test('command metadata is scoped, validated and cleared without storing input text or credentials', async ({ page }) => {
  await page.goto('/tests/fixtures/observer.html');
  const value = await page.evaluate(async () => {
    const path = '/src/processing/pending.ts'; const store = await import(/* @vite-ignore */ path);
    const apiPath = '/src/api.ts'; const { ApiClient } = await import(/* @vite-ignore */ apiPath);
    const id = '11111111-1111-4111-8111-111111111111';
    const command = { kind: 'start', key: crypto.randomUUID(), createdAt: new Date().toISOString(), body: { operation: 'extract_feedback', inputs: [{ kind: 'source', id, state_id: id }] } };
    store.writePending('u1', 'p1', command);
    const own = store.readPending('u1', 'p1'); const otherUser = store.readPending('u2', 'p1'); const otherProject = store.readPending('u1', 'p2');
    const serialized = sessionStorage.getItem('f2r.pending-run/u1/p1');
    sessionStorage.setItem('f2r.pending-run/u1/p2', JSON.stringify({ ...command, body: { operation: 'extract_feedback', inputs: [{ kind: 'document', id, state_id: id }] } }));
    const invalid = store.readPending('u1', 'p2'); new ApiClient(() => {}).clearSession();
    return { own, otherUser, otherProject, serialized, invalid, remaining: Object.keys(sessionStorage) };
  });
  expect(value.own.command?.kind).toBe('start'); expect(value.otherUser.command).toBeNull(); expect(value.otherProject.command).toBeNull();
  expect(value.serialized).not.toMatch(/"text"|password|csrf|cookie/); expect(value.invalid.command).toBeNull(); expect(value.remaining).toEqual([]);
});

test('new scoped routes and opaque legacy routes retain exact IDs and reject ambiguous query parameters', async ({ page }) => {
  await page.goto('/tests/fixtures/observer.html');
  const values = await page.evaluate(async () => {
    const path = '/src/routes.ts'; const r = await import(/* @vite-ignore */ path); const id = '11111111-1111-4111-8111-111111111111';
    return [r.parseRoute(r.processingInputHref(id, { kind: 'source', id, state_id: id })), r.parseRoute(r.runHref(id, id)),
      r.parseRoute(r.fragmentHref(id, id, id)), r.parseRoute(r.materialStateHref(id, 'sources', id, id)),
      r.parseRoute(r.findingsAttemptHref(id, id)), r.parseRoute(r.requirementHref(id, 'Требование / 🧭')),
      r.parseRoute(`#/projects/${id}/processing?kind=source&id=${id}&state_id=${id}&kind=document`),
      r.parseRoute(`#/projects/${id}/findings?attempt_id=bad`), r.parseRoute(`#/projects/${id}/requirements?filter=all&filter=lost`),
      r.parseRoute(r.processingInputHref(id, { kind: 'source', id: 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', state_id: 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB' }))];
  });
  expect(values[0].processingInput?.state_id).toBe('11111111-1111-4111-8111-111111111111'); expect(values[1].runId).toBeTruthy();
  expect(values[2].fragment?.stateId).toBeTruthy(); expect(values[3].selected?.stateId).toBeTruthy(); expect(values[4].attemptId).toBeTruthy();
  expect(values[5].requirementId).toBe('Требование / 🧭'); expect(values.slice(6, 9).map(value => value.kind)).toEqual(['missing', 'missing', 'missing']);
  expect(values[9].processingInput).toEqual({ kind: 'source', id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', state_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' });
});
