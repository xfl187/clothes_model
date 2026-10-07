/* eslint-disable react-refresh/only-export-components -- provider and hook form one boundary */
import { createContext, useContext, useMemo } from 'react';
import type { PropsWithChildren } from 'react';

import { createAdminApi } from './adminApi';
import type { AdminApi } from './adminApi';

const AdminApiContext = createContext<AdminApi | null>(null);

export function AdminApiProvider({ children, api }: PropsWithChildren<{ api?: AdminApi }>) {
  const value = useMemo(() => api ?? createAdminApi(), [api]);
  return <AdminApiContext.Provider value={value}>{children}</AdminApiContext.Provider>;
}

export function useAdminApi(): AdminApi {
  const api = useContext(AdminApiContext);
  if (!api) {
    throw new Error('AdminApiProvider is missing.');
  }
  return api;
}
