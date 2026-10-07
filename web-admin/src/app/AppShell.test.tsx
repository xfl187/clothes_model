import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';

import { AppShell } from './AppShell';
import { AdminSessionContext } from '../features/auth/adminSessionState';

function renderShell() {
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
    </AdminSessionContext.Provider>,
  );
}

test('shell exposes the confirmed three-group navigation', () => {
  renderShell();
  expect(screen.getByRole('link', { name: '概览' })).toBeInTheDocument();
  expect(screen.getByText('配置')).toBeInTheDocument();
  expect(screen.getByText('运行维护')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'ComfyUI 节点' })).toHaveAttribute('href', '/comfy');
  expect(screen.getByRole('link', { name: 'Token / Security' })).toHaveAttribute('href', '/security');
  expect(screen.getByText('overview-content')).toBeInTheDocument();
});
