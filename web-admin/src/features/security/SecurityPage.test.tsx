import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import type { AdminApi } from '../../api/adminApi';
import { AdminApiProvider } from '../../api/AdminApiContext';
import { AdminSessionContext } from '../auth/adminSessionState';
import { SecurityPage } from './SecurityPage';

function renderPage(api: Partial<AdminApi>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminApiProvider api={api as AdminApi}>
        <AdminSessionContext.Provider
          value={{
            state: 'authenticated',
            session: { authenticated: true, expiresAt: new Date(), csrfToken: 'csrf' },
            login: vi.fn(),
            logout: vi.fn(),
            expire: vi.fn(),
          }}
        >
          <SecurityPage />
        </AdminSessionContext.Provider>
      </AdminApiProvider>
    </QueryClientProvider>,
  );
}

test('rotation shows the one-time token behind an acknowledgement', async () => {
  const rotate = vi.fn().mockResolvedValue({
    token: 'brand-new-app-token',
    tokenId: 'token-2',
    rotatedAt: new Date(),
  });
  const user = userEvent.setup();
  renderPage({
    appCredential: vi.fn().mockResolvedValue({
      tokenId: 'token-1',
      status: 'active',
      createdAt: new Date(),
    }),
    rotateAppCredential: rotate,
  });

  expect(await screen.findByText(/token-1/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '轮换 App Token' }));
  expect(screen.getByRole('dialog', { name: '轮换 App Token' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '确认轮换' }));

  expect(await screen.findByText('brand-new-app-token')).toBeInTheDocument();
  const close = screen.getByRole('button', { name: '关闭' });
  expect(close).toBeDisabled();
  await user.click(screen.getByRole('checkbox'));
  expect(close).toBeEnabled();
  expect(rotate).toHaveBeenCalledTimes(1);
});

test('admin token page never offers a web rotation control', async () => {
  renderPage({
    appCredential: vi.fn().mockResolvedValue({
      tokenId: 'token-1',
      status: 'active',
      createdAt: new Date(),
    }),
  });
  await waitFor(() => expect(screen.getByText(/token-1/)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /Admin Token.*轮换/ })).not.toBeInTheDocument();
});
