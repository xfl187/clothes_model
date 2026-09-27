import { expect, test } from '@playwright/test';

test('protects routes, restores the cookie session, and logs out', async ({ page }) => {
  let authenticated = false;
  await page.route('**/api/v1/admin/auth/session', async route => {
    const method = route.request().method();
    if (method === 'POST') {
      authenticated = true;
      await route.fulfill({
        status: 201,
        headers: { 'content-type': 'application/json', 'set-cookie': 'admin_session=test; Path=/; HttpOnly; SameSite=Strict' },
        json: { authenticated: true, csrf_token: 'memory-only', created_at: '2026-09-27T00:00:00Z', expires_at: '2026-09-27T01:00:00Z' },
      });
      return;
    }
    if (method === 'DELETE') {
      expect(route.request().headers()['x-csrf-token']).toBe('refreshed-in-memory');
      authenticated = false;
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill(authenticated ? {
      status: 200,
      json: { authenticated: true, csrf_token: 'refreshed-in-memory', created_at: '2026-09-27T00:00:00Z', expires_at: '2026-09-27T01:00:00Z' },
    } : { status: 401, json: { code: 'unauthorized' } });
  });

  await page.goto('/contract-status');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Admin Token').fill('a'.repeat(48));
  await page.getByRole('button', { name: '安全登录' }).click();
  await expect(page).toHaveURL(/\/contract-status$/);
  await expect(page.getByRole('heading', { name: '三端共享契约可以被 Web 消费。' })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/contract-status$/);
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => ({ ...localStorage, ...sessionStorage }))).toEqual({});
});
