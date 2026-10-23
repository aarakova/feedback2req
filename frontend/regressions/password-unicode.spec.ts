import { expect, test } from '@playwright/test';
import { unique } from '../tests/helpers';

test('AUD-03: inserting a server-valid non-BMP password must preserve every code point', async ({ page }) => {
  await page.goto('/');
  const login = unique();
  const password = 'X'.repeat(500) + '\u{1f9ed}'.repeat(300);
  expect([...password]).toHaveLength(800);
  const origin = new URL(page.url()).origin;
  expect((await page.request.post('/api/v1/auth/register', {
    headers: { Origin: origin }, data: { login, password },
  })).status()).toBe(201);
  // Browser text insertion, not locator.fill(), exercises the HTML maxlength.
  await page.getByLabel('Логин', { exact: true }).fill(login);
  const input = page.getByLabel('Пароль', { exact: true });
  await input.focus();
  await page.keyboard.insertText(password);
  const inserted = await input.inputValue();
  expect([...inserted].length, 'The browser must preserve all password code points').toBe([...password].length);
  expect(inserted === password, 'Password text must remain identical').toBe(true);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toBeVisible();
});
