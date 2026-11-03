import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { unique } from './helpers';

// Synthetic credentials only; keep spaces and decomposed Unicode unchanged.
const longPassword = '  ' + '🧭'.repeat(1019) + 'е\u0301' + ' ';
const origin = (page: Page) => new URL(page.url()).origin;
async function enter(page: Page, label: string, value: string) {
  const field = page.getByLabel(label, { exact: true });
  await field.fill(''); await field.focus();
  // Native text insertion reproduces maxlength truncation during paste/typing.
  await page.keyboard.insertText(value);
}

test('API-created maximum Unicode password signs in without browser truncation', async ({ page }) => {
  await page.goto('/');
  expect([...longPassword]).toHaveLength(1024);
  const login = unique();
  const registered = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: origin(page) }, data: { login, password: longPassword },
  });
  expect(registered.status()).toBe(201);
  await page.getByLabel('Логин', { exact: true }).fill(login);
  await enter(page, 'Пароль', longPassword);
  expect((await page.getByLabel('Пароль', { exact: true }).inputValue()).length).toBe(longPassword.length);
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue(longPassword);
  const response = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/session') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  const signedIn = await response; expect(signedIn.status()).toBe(200);
  expect(signedIn.request().postDataJSON().password).toBe(longPassword);
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []]);
});

test('registration and login submit the full maximum Unicode password unchanged', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await page.getByLabel('Логин', { exact: true }).fill(unique());
  await enter(page, 'Пароль', longPassword);
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue(longPassword);
  const response = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/register'));
  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click();
  const registered = await response; expect(registered.status()).toBe(201);
  expect(registered.request().postDataJSON().password).toBe(longPassword);
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт', exact: true })).toBeVisible();
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('');
  await enter(page, 'Пароль', longPassword);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
});

test('valid raw Unicode login reaches server normalization without silent truncation', async ({ page }) => {
  await page.goto('/');
  const prefix = unique();
  const canonicalLogin = prefix + '🧭'.repeat(128 - prefix.length);
  const rawLogin = ' '.repeat(128) + canonicalLogin;
  expect([...rawLogin]).toHaveLength(256);
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await enter(page, 'Логин', rawLogin);
  expect((await page.getByLabel('Логин', { exact: true }).inputValue()).length).toBe(rawLogin.length);
  await expect(page.getByLabel('Логин', { exact: true })).toHaveValue(rawLogin);
  await page.getByLabel('Пароль', { exact: true }).fill('unicode-test-only-2026');
  const response = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/register'));
  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click();
  const registered = await response; expect(registered.status()).toBe(201);
  expect(registered.request().postDataJSON().login).toBe(rawLogin);
  expect((await registered.json()).login).toBe(canonicalLogin);
  await expect(page.getByLabel('Логин', { exact: true })).toHaveValue(canonicalLogin);
  await page.getByLabel('Пароль', { exact: true }).fill('unicode-test-only-2026');
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты', exact: true })).toBeVisible();
});

for (const registering of [true, false]) {
  test(`${registering ? 'registration' : 'login'} rejects over-limit Unicode password without cutting input`, async ({ page }) => {
    await page.goto('/');
    if (registering) await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
    await page.getByLabel('Логин', { exact: true }).fill(unique());
    const password = '🧭'.repeat(1025);
    await enter(page, 'Пароль', password);
    await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue(password);
    let posts = 0;
    page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/v1/auth/')) posts++; });
    await page.getByRole('button', { name: registering ? 'Создать аккаунт' : 'Войти', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Пароль должен содержать не более 1024 символов.');
    await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue(password); expect(posts).toBe(0);
  });
  test(`${registering ? 'registration' : 'login'} checks raw login length in code points`, async ({ page }) => {
    await page.goto('/');
    if (registering) await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
    const login = '🧭'.repeat(257);
    await enter(page, 'Логин', login);
    await expect(page.getByLabel('Логин', { exact: true })).toHaveValue(login);
    await page.getByLabel('Пароль', { exact: true }).fill('unicode-test-only-2026');
    let posts = 0;
    page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/v1/auth/')) posts++; });
    await page.getByRole('button', { name: registering ? 'Создать аккаунт' : 'Войти', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Логин должен содержать не более 256 символов.');
    await expect(page.getByLabel('Логин', { exact: true })).toHaveValue(login); expect(posts).toBe(0);
  });
}

test('registration minimum counts supplementary characters once each', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await page.getByLabel('Логин', { exact: true }).fill(unique());
  await enter(page, 'Пароль', '🧭'.repeat(11));
  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('не менее 12 символов');
  await enter(page, 'Пароль', '🧭'.repeat(12));
  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Учётная запись создана');
});
