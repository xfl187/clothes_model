import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import type { ProviderAdminGateway, ProviderConfig } from '../../api/adminProviderGateway';
import { AdminSessionContext } from '../auth/adminSessionState';
import { ProviderAdminPage } from './ProviderAdminPage';

const provider = {
  id: 'provider-1', displayName: 'Seedream', type: 'llm_image_edit',
  adapterType: 'volcengine_ark_seedream', endpoint: 'https://ark.cn-beijing.volces.com/api/v3',
  model: 'doubao-seedream-4-5-251128', timeoutSeconds: 120, state: 'inactive',
  secretConfigured: true, configRef: { providerId: 'provider-1', configVersionId: 'revision-1', revision: 1 },
  capabilities: {}, updatedAt: new Date(),
} as ProviderConfig;

const list = vi.fn().mockResolvedValue([provider]);
const save = vi.fn().mockResolvedValue(provider);
const validate = vi.fn().mockResolvedValue({
  status: 'passed', checkedAt: new Date(), capabilities: {},
  steps: [{ key: 'generation', status: 'passed' }, { key: 'output_decode', status: 'passed' }],
});
const remove = vi.fn().mockResolvedValue(undefined);
const archive = vi.fn();
const restore = vi.fn();
const gateway: ProviderAdminGateway = {
  list, save, validate,
  connectionTest: vi.fn().mockResolvedValue({ status: 'passed', checkedAt: new Date(), steps: [] }),
  enable: vi.fn().mockResolvedValue(provider),
  archive,
  restore,
  setDefault: vi.fn().mockResolvedValue(undefined),
  remove,
};

function renderPage() {
  return render(<AdminSessionContext.Provider value={{
    state: 'authenticated', session: { authenticated: true, expiresAt: new Date(), csrfToken: 'csrf' },
    login: vi.fn(), logout: vi.fn(), expire: vi.fn(),
  }}><ProviderAdminPage gateway={gateway} /></AdminSessionContext.Provider>);
}

beforeEach(() => {
  list.mockReset().mockResolvedValue([provider]);
  save.mockClear(); validate.mockClear(); archive.mockReset(); restore.mockReset();
  remove.mockReset().mockResolvedValue(undefined);
});

test('archives a provider into read-only history and restores it as inactive', async () => {
  const archived = { ...provider, state: 'disabled' } as ProviderConfig;
  archive.mockResolvedValue(archived);
  restore.mockResolvedValue(provider);
  list.mockReset()
    .mockResolvedValueOnce([provider])
    .mockResolvedValueOnce([archived])
    .mockResolvedValueOnce([provider]);
  renderPage();
  const user = userEvent.setup();

  await user.click(await screen.findByRole('button', { name: '归档 Seedream' }));
  expect(screen.getByRole('dialog', { name: '确认归档配置' })).toBeInTheDocument();
  expect(archive).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '确认归档' }));
  expect(await screen.findByText('已归档 · 密钥已保存')).toBeInTheDocument();
  expect(archive).toHaveBeenCalledWith('provider-1');

  await user.click(screen.getByRole('button', { name: '查看 Seedream' }));
  expect(screen.getByText('此 Provider 已归档，仅保留历史关联。恢复后才能修改、验证或再次启用。')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '保存配置' })).toBeDisabled();
  expect(screen.queryByRole('button', { name: '最小生成测试（付费）' })).not.toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: '恢复 Seedream' }));
  expect(await screen.findByText('未启用 · 密钥已保存')).toBeInTheDocument();
  expect(restore).toHaveBeenCalledWith('provider-1');
});

test('retains redacted secret and requires explicit paid validation confirmation', async () => {
  renderPage();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '编辑 Seedream' }));
  expect(screen.getByPlaceholderText('留空以保留现有密钥')).toHaveValue('');

  await user.click(screen.getByRole('button', { name: '保存配置' }));
  expect(save).toHaveBeenCalledWith(expect.not.objectContaining({ apiKey: expect.anything() }), 'provider-1');

  await user.type(screen.getByLabelText('API Key'), '  ark-test-key  ');
  await user.click(screen.getByRole('button', { name: '保存配置' }));
  expect(save).toHaveBeenLastCalledWith(expect.objectContaining({ apiKey: 'ark-test-key' }), 'provider-1');

  await user.click(screen.getByRole('button', { name: '最小生成测试（付费）' }));
  expect(screen.getByRole('dialog', { name: '确认一次付费验证' })).toBeInTheDocument();
  expect(validate).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '确认并验证一次' }));
  expect(await screen.findByText('验证：passed')).toBeInTheDocument();
  expect(validate).toHaveBeenCalledWith('provider-1');
  expect(screen.getByText('output_decode: passed')).toBeInTheDocument();
});

test('requires confirmation before permanently deleting a provider configuration', async () => {
  list.mockResolvedValueOnce([provider]).mockResolvedValueOnce([]);
  renderPage();
  const user = userEvent.setup();

  await user.click(await screen.findByRole('button', { name: '删除 Seedream' }));
  expect(screen.getByRole('dialog', { name: '确认删除配置' })).toBeInTheDocument();
  expect(remove).not.toHaveBeenCalled();

  await user.click(screen.getByRole('button', { name: '永久删除' }));
  expect(await screen.findByText('尚无配置。')).toBeInTheDocument();
  expect(remove).toHaveBeenCalledWith('provider-1');
});
