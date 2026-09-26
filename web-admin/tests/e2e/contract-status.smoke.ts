import { expect, test } from '@playwright/test';

test('reads health, job state, and provider capabilities from the contract mock', async ({ page }) => {
  await page.goto('/contract-status');

  await expect(page.getByRole('heading', { name: '三端共享契约可以被 Web 消费。' })).toBeVisible();
  await expect(page.getByText('partially_succeeded')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'ComfyUI · precise-vton' })).toBeVisible();
  await expect(page.getByText('支持')).toHaveCount(2);
  await expect(page.getByText('契约读取失败')).toHaveCount(0);
});
