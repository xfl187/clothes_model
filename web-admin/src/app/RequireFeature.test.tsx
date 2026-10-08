import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';

import type { AdminApi } from '../api/adminApi';
import { AdminApiProvider } from '../api/AdminApiContext';
import { AdminSessionContext } from '../features/auth/adminSessionState';
import { RequireFeature } from './RequireFeature';

test('direct navigation to a disabled V1.1 route redirects to overview', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const api = {
    overview: vi.fn().mockResolvedValue({
      verdict: 'ok',
      snapshotAt: new Date(),
      dependencies: [],
      blockers: [],
      actionItems: [],
      effectiveConfiguration: {
        productRelease: 'v1',
        enabledFeatures: new Set(['direct_model_try_on']),
      },
    }),
  } as Partial<AdminApi>;
  const router = createMemoryRouter([
    { path: '/overview', element: <p>overview-visible</p> },
    {
      path: '/comfy',
      element: <RequireFeature feature="comfyui"><p>comfy-visible</p></RequireFeature>,
    },
  ], { initialEntries: ['/comfy'] });

  render(
    <QueryClientProvider client={client}>
      <AdminApiProvider api={api as AdminApi}>
        <AdminSessionContext.Provider
          value={{
            state: 'authenticated',
            session: { authenticated: true, expiresAt: new Date(), csrfToken: 'csrf' },
            login: vi.fn(), logout: vi.fn(), expire: vi.fn(),
          }}
        >
          <RouterProvider router={router} />
        </AdminSessionContext.Provider>
      </AdminApiProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText('overview-visible')).toBeInTheDocument();
  expect(screen.queryByText('comfy-visible')).not.toBeInTheDocument();
});
