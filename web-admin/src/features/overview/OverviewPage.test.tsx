import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';

import type { AdminApi } from '../../api/adminApi';
import { AdminApiProvider } from '../../api/AdminApiContext';
import { AdminSessionContext } from '../auth/adminSessionState';
import { OverviewPage } from './OverviewPage';

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
          <OverviewPage />
        </AdminSessionContext.Provider>
      </AdminApiProvider>
    </QueryClientProvider>,
  );
}

test('overview renders verdict, dependencies, and blockers', async () => {
  renderPage({
    overview: vi.fn().mockResolvedValue({
      verdict: 'limited',
      snapshotAt: new Date(),
      dependencies: [
        { key: 'business_service', state: 'ok' },
        { key: 'database', state: 'ok' },
        { key: 'storage', state: 'degraded' },
        { key: 'comfyui', state: 'unknown' },
      ],
      blockers: [{ kind: 'needs_attention', count: 2 }],
      actionItems: [
        { id: 'needs_attention', severity: 'critical', summary: '需要人工处理的任务，共 2 项', targetKind: 'job' },
      ],
      effectiveConfiguration: {},
    }),
  });

  expect(await screen.findByText('系统受限')).toBeInTheDocument();
  expect(screen.getByText('数据库')).toBeInTheDocument();
  expect(screen.getByText('需要人工处理的任务')).toBeInTheDocument();
});
