import { expect } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';

export const password = 'frontend-test-only-2026';
export const unique = () => `f1_${crypto.randomUUID()}`;

export async function registerAndLogin(page: Page, login = unique()) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Зарегистрироваться', exact: false }).click();
  await page.getByLabel('Логин', { exact: true }).fill(login);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('status')).toContainText('Учётная запись создана');
  await expect(page.getByRole('heading', { name: 'Вход в аккаунт' })).toBeVisible();
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваши проекты' })).toBeVisible();
  return login;
}

export async function authenticatedHeaders(request: APIRequestContext, origin: string) {
  const response = await request.get('/api/v1/auth/session');
  expect(response.status()).toBe(200);
  const session = await response.json();
  return { Origin: origin, 'X-CSRF-Token': session.csrf_token };
}

export async function createProject(page: Page, name = unique()) {
  const headers = await authenticatedHeaders(page.request, new URL(page.url()).origin);
  const response = await page.request.post('/api/v1/projects', { headers, data: { name } });
  expect(response.status()).toBe(201);
  return response.json();
}
