import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import type { PropsWithChildren } from 'react';

import type { ContractGateway } from '../api/contractGateway';
import { ContractGatewayProvider } from './ContractGatewayContext';
import { AdminApiProvider } from '../api/AdminApiContext';
import { AdminSessionProvider } from '../features/auth/AdminSessionContext';
import type { AdminApi } from '../api/adminApi';

export function AppProviders({
  children,
  gateway,
  adminApi,
}: PropsWithChildren<{ gateway?: ContractGateway; adminApi?: AdminApi }>) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, staleTime: 30_000 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ContractGatewayProvider gateway={gateway}>
        <AdminApiProvider api={adminApi}>
          <AdminSessionProvider>{children}</AdminSessionProvider>
        </AdminApiProvider>
      </ContractGatewayProvider>
    </QueryClientProvider>
  );
}
