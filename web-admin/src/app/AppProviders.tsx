import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import type { PropsWithChildren } from 'react';

import type { ContractGateway } from '../api/contractGateway';
import { ContractGatewayProvider } from './ContractGatewayContext';
import { AdminSessionProvider } from '../features/auth/AdminSessionContext';

export function AppProviders({
  children,
  gateway,
}: PropsWithChildren<{ gateway?: ContractGateway }>) {
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
      <ContractGatewayProvider gateway={gateway}><AdminSessionProvider>{children}</AdminSessionProvider></ContractGatewayProvider>
    </QueryClientProvider>
  );
}
