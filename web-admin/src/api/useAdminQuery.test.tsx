import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';

import { ResponseError } from './generated/runtime';
import { AdminSessionContext } from '../features/auth/adminSessionState';
import { useAdminQuery } from './useAdminQuery';

function Probe() {
  const query = useAdminQuery(['probe'], async () => {
    throw new ResponseError(new Response(null, { status: 401 }), 'unauthorized');
  });
  return <span>{query.isError ? 'error' : 'pending'}</span>;
}

test('a 401 response expires the admin session', async () => {
  const expire = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AdminSessionContext.Provider
        value={{
          state: 'authenticated',
          session: { authenticated: true, expiresAt: new Date(), csrfToken: 'csrf' },
          login: vi.fn(),
          logout: vi.fn(),
          expire,
        }}
      >
        <Probe />
      </AdminSessionContext.Provider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText('error')).toBeInTheDocument();
  expect(expire).toHaveBeenCalledTimes(1);
});
