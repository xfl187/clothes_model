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
const gateway: ProviderAdminGateway = {
  list, save, validate,
  enable: vi.fn().mockResolvedValue(provider),
  setDefault: vi.fn().mockResolvedValue(undefined),
};

function renderPage() {
  return render(<AdminSessionContext.Provider value={{
    state: 'authenticated', session: { authenticated: true, expiresAt: new Date(), csrfToken: 'csrf' },
    login: vi.fn(), logout: vi.fn(),
  }}><ProviderAdminPage gateway={gateway} /></AdminSessionContext.Provider>);
}

beforeEach(() => { list.mockClear(); save.mockClear(); validate.mockClear(); });

test('retains redacted secret and requires explicit paid validation confirmation', async () => {
  renderPage();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: /Seedream/ }));
  expect(screen.getByPlaceholderText('留空以保留现有密钥')).toHaveValue('');

  await user.click(screen.getByRole('button', { name: '保存配置' }));
  expect(save).toHaveBeenCalledWith(expect.not.objectContaining({ apiKey: expect.anything() }), 'provider-1');

  await user.click(screen.getByRole('button', { name: '验证连接与生成' }));
  expect(screen.getByRole('dialog', { name: '确认一次付费验证' })).toBeInTheDocument();
  expect(validate).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '确认并验证一次' }));
  expect(await screen.findByText('验证：passed')).toBeInTheDocument();
  expect(validate).toHaveBeenCalledWith('provider-1');
  expect(screen.getByText('output_decode: passed')).toBeInTheDocument();
});
