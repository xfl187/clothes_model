import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';

import { AppShell } from './AppShell';
import type { AdminApi } from '../api/adminApi';
import { AdminApiProvider } from '../api/AdminApiContext';
import { AdminSessionContext } from '../features/auth/adminSessionState';

function renderShell(enabledFeatures: Set<'direct_model_try_on' | 'comfyui' | 'layered_outfits'>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const api = {
    overview: vi.fn().mockResolvedValue({
      verdict: 'ok',
      snapshotAt: new Date(),
      dependencies: [],
      blockers: [],
      actionItems: [],
      effectiveConfiguration: { enabledFeatures },
    }),
  } as Partial<AdminApi>;
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <AppShell />,
        children: [
          { path: 'overview', element: <p>overview-content</p> },
          { path: 'diagnostics', element: <p>diagnostics-content</p> },
        ],
      },
    ],
    { initialEntries: ['/overview'] },
  );
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
          <RouterProvider router={router} />
        </AdminSessionContext.Provider>
      </AdminApiProvider>
    </QueryClientProvider>,
  );
}

test('V1.1 shell exposes the confirmed three-group navigation', async () => {
  renderShell(new Set(['direct_model_try_on', 'comfyui', 'layered_outfits']));
  expect(screen.getByRole('link', { name: '概览' })).toBeInTheDocument();
  expect(screen.getByText('配置')).toBeInTheDocument();
  expect(screen.getByText('运行维护')).toBeInTheDocument();
  expect(await screen.findByRole('link', { name: 'ComfyUI 节点' })).toHaveAttribute('href', '/comfy');
  expect(screen.getByRole('link', { name: 'Token / Security' })).toHaveAttribute('href', '/security');
  expect(screen.getByText('overview-content')).toBeInTheDocument();
});

test('V1 shell hides ComfyUI and Workflow navigation', async () => {
  renderShell(new Set(['direct_model_try_on']));
  expect(await screen.findByRole('link', { name: 'LLM Provider' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'ComfyUI 节点' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Workflows' })).not.toBeInTheDocument();
});
