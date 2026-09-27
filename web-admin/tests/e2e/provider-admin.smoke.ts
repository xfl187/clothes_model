import { expect, test } from '@playwright/test';

const capabilities = {
  schema_version: 1,
  garment_categories: { values: ['upper_body', 'lower_body', 'dress'], source: 'adapter', verification: 'declared' },
  manual_mask: { supported: false, source: 'adapter', verification: 'declared' },
  multiple_candidates: { supported: false, source: 'adapter', verification: 'declared' },
  multi_person_reference: { supported: false, source: 'adapter', verification: 'declared' },
  batch_input: { supported: false, source: 'adapter', verification: 'declared' },
  interrupt_running: { supported: false, source: 'adapter', verification: 'declared' },
  sequential_layering: { supported: false, source: 'adapter', verification: 'declared' },
  supported_layer_roles: { values: [], source: 'adapter', verification: 'declared' },
  preserve_existing_garments: { supported: false, source: 'adapter', verification: 'declared' },
  outfit_context: { supported: false, source: 'adapter', verification: 'declared' },
  region_mask: { supported: false, source: 'adapter', verification: 'declared' },
  input_constraints: { content_types: ['image/png'], max_size_bytes: 20971520 },
  output_constraints: { max_candidates: 1 },
};

test('creates, confirms paid validation, enables, and selects Seedream', async ({ page }) => {
  let state = 'inactive';
  let exists = false;
  let defaultSelected = false;
  const config = () => ({
    id: 'provider-1', display_name: '火山方舟 Seedream 4.5', type: 'llm_image_edit',
    adapter_type: 'volcengine_ark_seedream', endpoint: 'https://ark.cn-beijing.volces.com/api/v3',
    model: 'doubao-seedream-4-5-251128', timeout_seconds: 120, state,
    secret_configured: true, config_ref: { provider_id: 'provider-1', config_version_id: 'revision-1', revision: 1 },
    capabilities, updated_at: '2026-09-27T00:00:00Z',
  });
  await page.route('**/api/v1/admin/auth/session', route => route.fulfill({
    status: 200, json: { authenticated: true, csrf_token: 'csrf-token', created_at: '2026-09-27T00:00:00Z', expires_at: '2026-09-27T01:00:00Z' },
  }));
  await page.route('**/api/v1/admin/provider-configs**', async route => {
    const url = route.request().url();
    const method = route.request().method();
    if (method !== 'GET') {
      expect(route.request().headers()['x-csrf-token']).toBe('csrf-token');
    }
    if (url.endsWith('/validate')) {
      state = 'validated';
      await route.fulfill({ status: 200, json: { status: 'passed', checked_at: '2026-09-27T00:00:00Z', steps: [{ key: 'generation', status: 'passed' }, { key: 'output_decode', status: 'passed' }], capabilities } });
    } else if (url.endsWith('/enable')) {
      state = 'active'; await route.fulfill({ status: 200, json: config() });
    } else if (method === 'POST') {
      exists = true;
      expect((await route.request().postDataJSON()).api_key).toBe('secret-value');
      await route.fulfill({ status: 201, json: config() });
    } else {
      await route.fulfill({ status: 200, json: { items: exists ? [config()] : [], next_cursor: null, has_more: false } });
    }
  });
  await page.route('**/api/v1/admin/configuration/default-provider', async route => {
    defaultSelected = true;
    await route.fulfill({ status: 200, json: { provider_id: 'provider-1', config_version_id: 'revision-1', updated_at: '2026-09-27T00:00:00Z' } });
  });

  await page.goto('/providers');
  await page.getByLabel('API Key').fill('secret-value');
  await page.getByRole('button', { name: '保存配置' }).click();
  await page.getByRole('button', { name: '验证连接与生成' }).click();
  await expect(page.getByRole('dialog', { name: '确认一次付费验证' })).toBeVisible();
  await page.getByRole('button', { name: '确认并验证一次' }).click();
  await expect(page.getByText('output_decode: passed')).toBeVisible();
  await page.getByRole('button', { name: '启用' }).click();
  await page.getByRole('button', { name: '设为默认' }).click();
  expect(defaultSelected).toBe(true);
});
