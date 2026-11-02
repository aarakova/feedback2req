import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const deployed = ['compose', 'built'].includes(process.env.F2R_E2E_MODE ?? '');
test.skip(deployed, 'Изолированный стенд обслуживается только Vite и не входит в production entry.');
const fixture = (section: string, state = 'ready', extra = '') => `/tests/fixtures/observer.html?section=${section}&state=${state}${extra}`;
const inspector = (page: Page) => page.getByRole('region', { name: 'Карточка выбранного требования', exact: true });

for (const section of ['findings', 'requirements', 'processing']) {
  for (const state of ['loading', 'error', 'empty', 'unavailable', 'partial']) {
    test(`${section}: renders ${state} without replacing missing data with business results`, async ({ page }) => {
      await page.goto(fixture(section, state));
      await expect(page.getByRole('note')).toContainText('Изолированный визуальный стенд');
      const screen = page.locator(`.${section}-screen`);
      if (state === 'loading') await expect(screen.getByRole('status').filter({ hasText: 'Загружаем данные раздела' })).toBeVisible();
      if (state === 'error') await expect(screen.getByRole('alert').filter({ hasText: 'Тестовая ошибка загрузки' })).toBeVisible();
      if (state === 'empty') await expect(screen.getByText('В загруженном наборе нет записей').first()).toBeVisible();
      if (state === 'unavailable') await expect(screen.getByText('Функция не подключена', { exact: true })).toBeVisible();
      if (state === 'partial') await expect(screen.getByRole('status')).toContainText('только часть тестовых результатов');
      if (state !== 'partial') {
        await expect(screen.getByText('Сохранение изменений', { exact: true })).toHaveCount(0);
        await expect(screen.getByText('Нужно автоматическое сохранение.', { exact: true })).toHaveCount(0);
      }
    });
  }
}

test('overview separates unknown aggregates from explicit zero aggregates', async ({ page }) => {
  await page.goto(fixture('overview', 'unavailable'));
  await expect(page.getByRole('group', { name: 'Показатели проекта' }).locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
  await expect(page.getByRole('img', { name: 'Распределение решений: данные пока недоступны', exact: true })).toBeVisible();
  await page.getByLabel('Состояние стенда').selectOption('zero');
  await expect(page.getByRole('group', { name: 'Показатели проекта' }).locator('.metric-value')).toHaveText(['0', '0', '0', '0']);
  await expect(page.locator('.donut-center strong')).toHaveText('0');
  expect(await page.locator('.decision-donut svg circle').count()).toBe(1); // No made-up segment proportions for an empty set.
});

test('partial datasets cannot turn loaded records into exact project metrics', async ({ page }) => {
  await page.goto(fixture('overview', 'partial'));
  await expect(page.locator('.group-summary')).toHaveCount(1);
  await expect(page.getByRole('group', { name: 'Показатели проекта' }).locator('.metric-value')).toHaveText(['—', '—', '—', '—']);
  await expect(page.locator('.donut-center strong')).toHaveText('—');
});

test('requirements search, filters, selection and keyboard tabs work on loaded data', async ({ page }) => {
  await page.goto(fixture('requirements'));
  await page.getByLabel('Поиск требования', { exact: true }).fill('Подтверждение');
  await expect(page.locator('.requirement-register .req-row')).toHaveCount(1);
  await expect(inspector(page).getByRole('heading', { name: 'Подтверждение завершения', exact: true })).toBeVisible();
  await expect(inspector(page).getByText('Отдельная предлагаемая формулировка.', { exact: true })).toBeVisible();
  const states = inspector(page).getByRole('group', { name: 'Независимые состояния требования' });
  await expect(states).toContainText('Основания доступны');
  await expect(states).not.toContainText('Утверждено'); // The proposal does not inherit the historical decision.
  await expect(inspector(page).getByRole('button', { name: 'Редактировать предложение' })).toBeEnabled();
  await page.getByRole('button', { name: 'Сбросить фильтр', exact: true }).click();
  await page.getByLabel('Фильтр требований').selectOption('blocker');
  await expect(page.locator('.requirement-register .req-row')).toHaveCount(1);
  const basis = inspector(page).getByRole('tab', { name: 'Основания', exact: true });
  await basis.focus(); await page.keyboard.press('ArrowRight');
  await expect(inspector(page).getByRole('tab', { name: 'Проверка', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(inspector(page).getByText('Сохранять сразу.', { exact: true })).toBeVisible();
  await expect(inspector(page).getByText('Только после моего подтверждения.', { exact: true })).toBeVisible();
  await expect(inspector(page).getByRole('heading', { name: 'Открытые вопросы', exact: true })).toBeVisible();
  await page.keyboard.press('End');
  await expect(inspector(page).getByRole('tab', { name: 'История', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(inspector(page).getByRole('heading', { name: 'Создана тестовая редакция r1', exact: true })).toBeVisible();
});

test('local draft never simulates saving or human approval and cancel preserves source wording', async ({ page }) => {
  let writes = 0;
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') writes++; });
  await page.goto(fixture('requirements'));
  await inspector(page).getByRole('button', { name: 'Редактировать требование', exact: true }).click();
  await expect(inspector(page).getByText('Локальный черновик · не сохранён.', { exact: false })).toBeVisible();
  await inspector(page).getByLabel('Формулировка требования', { exact: true }).fill('НЕ СОХРАНЯТЬ ТЕСТОВУЮ ПРАВКУ');
  await expect(inspector(page).getByRole('button', { name: 'Сохранить новую редакцию', exact: true })).toBeDisabled();
  await inspector(page).getByRole('button', { name: 'Отменить правки', exact: true }).click();
  await expect(inspector(page).getByText('НЕ СОХРАНЯТЬ ТЕСТОВУЮ ПРАВКУ', { exact: true })).toHaveCount(0);
  await expect(inspector(page).getByRole('button', { name: 'Утвердить', exact: true })).toBeDisabled();
  await expect(inspector(page).getByRole('button', { name: 'Отклонить', exact: true })).toBeDisabled();
  expect(writes).toBe(0);
});

test('deleted evidence never exposes its old quote while historical approval stays visible', async ({ page }) => {
  await page.goto(fixture('requirements'));
  await page.locator('.requirement-register .req-row').filter({ hasText: 'REQ-04' }).click();
  await expect(inspector(page).getByText('Историческое утверждение сохранено.', { exact: false })).toBeVisible();
  await expect(inspector(page).getByText('Утверждено', { exact: true })).toBeVisible();
  await expect(inspector(page).getByText('Источник удалён.', { exact: false })).toBeVisible();
  await expect(page.getByText('НЕ_ПОКАЗЫВАТЬ_УДАЛЁННУЮ_ЦИТАТУ', { exact: false })).toHaveCount(0);
  await expect(inspector(page).getByRole('article', { name: 'Свидетельство: Удалённый тестовый отзыв', exact: true }).getByRole('link')).toHaveCount(0);
  await expect(inspector(page).getByRole('article', { name: 'Контекст: Описание сервиса заявок', exact: true })).toContainText('не является самостоятельным основанием');
});

test('requirement controls use project permissions and Approver never gains administration', async ({ page }) => {
  await page.goto(fixture('requirements', 'ready', '&actor=member'));
  await expect(inspector(page).getByRole('button', { name: 'Утвердить', exact: true })).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Разделы проекта' }).getByRole('link', { name: 'Доступ', exact: true })).toHaveCount(0);
  await page.goto(fixture('requirements', 'ready', '&actor=approver'));
  await expect(inspector(page).getByRole('button', { name: 'Утвердить', exact: true })).toBeDisabled();
  await expect(page.getByRole('navigation', { name: 'Разделы проекта' }).getByRole('link', { name: 'Доступ', exact: true })).toHaveCount(0);
  await page.locator('.requirement-register .req-row').filter({ hasText: 'REQ-03' }).click();
  await expect(inspector(page).getByRole('button', { name: 'Редактировать требование', exact: true })).toBeDisabled();
});

test('group composition keeps conflicting positions and links requirements and real-shaped evidence', async ({ page }) => {
  await page.goto(fixture('findings'));
  await page.getByRole('link').filter({ has: page.getByRole('heading', { name: 'Сохранение и подтверждение', exact: true }) }).click();
  const group = page.getByRole('region', { name: 'Состав группы', exact: true });
  await expect(group.getByRole('heading', { name: 'Нужно автоматическое сохранение.', exact: true })).toBeVisible();
  await expect(group.getByRole('heading', { name: 'Нужно ручное подтверждение.', exact: true })).toBeVisible();
  await expect(group.getByRole('link', { name: 'Открыть источник ↗' }).first()).toHaveAttribute('href', /\/materials\/sources\/22222222/);
  await group.getByRole('tab', { name: 'Требования', exact: true }).click();
  await expect(group.getByRole('link').filter({ hasText: 'Сохранение изменений' })).toBeVisible();
  await group.getByRole('tab', { name: 'Замечания требований', exact: true }).click();
  await expect(group.getByRole('heading', { name: 'Противоположные ожидания', exact: true })).toBeVisible();
  await expect(group.getByText('Замечания принадлежат проверкам требований, а не самой группе.', { exact: true })).toBeVisible();
});

test('partial group distinguishes missing opponents and incomplete composition', async ({ page }) => {
  await page.goto(fixture('findings', 'partial'));
  await page.locator('.group-card').click();
  await expect(page.getByText('Часть состава группы не загружена.', { exact: true })).toBeVisible();
  await expect(page.getByText('Часть конфликтующих позиций не загружена.', { exact: true })).toBeVisible();
});

test('technical inspection cannot mark semantic processing complete and unreliable material data stays distinct', async ({ page }) => {
  await page.goto(fixture('processing', 'technical'));
  await expect(page.getByRole('group', { name: 'Этапы обработки' }).locator('.badge')).toHaveText(['Данные недоступны', 'Данные недоступны', 'Данные недоступны', 'Данные недоступны']);
  await expect(page.getByRole('region', { name: 'Техническая проверка текста', exact: true })).toContainText('inspect_text');
  await expect(page.getByText('Ненадёжные участки распознавания', { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await page.getByLabel('Состояние стенда').selectOption('failure');
  await page.getByRole('region', { name: 'Формирование требований', exact: true }).getByRole('button', { name: 'Детали этапа', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Ошибка независимой части.' })).toBeVisible();
});

for (const section of ['overview', 'requirements', 'findings', 'processing']) {
  test(`${section}: rejects a dataset belonging to another project`, async ({ page }) => {
    await page.goto(fixture(section, 'ready', '&scope=wrong'));
    await expect(page.getByText('Данные другого проекта не отображаются.', { exact: true })).toBeVisible();
    await expect(page.getByText('Нужно автоматическое сохранение.', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Сохранение изменений', { exact: true })).toHaveCount(0);
  });
}

test('loaded Observer visual compositions are isolated, explicitly marked and stable', async ({ page }) => {
  test.setTimeout(90000);
  const destination = resolve('..', 'docs', 'qa', 'observer-v3', 'screenshots');
  mkdirSync(destination, { recursive: true });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const section of ['overview', 'requirements', 'findings', 'processing']) {
      await page.goto(fixture(section));
      await expect(page.getByRole('note')).toContainText('вымышленные данные');
      await page.mouse.move(0, 0);
      await expect(page).toHaveScreenshot(`fixture-${section}-${width}.png`, { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.001 });
      await page.screenshot({ path: resolve(destination, `fixture-${section}-${width}.png`), fullPage: true, animations: 'disabled' });
    }
  }
});
