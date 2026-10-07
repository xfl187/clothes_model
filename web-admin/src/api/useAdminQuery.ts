import { useQuery } from '@tanstack/react-query';

import { useAdminSession } from '../features/auth/adminSessionState';
import { isUnauthorized } from './adminApi';

export function useAdminQuery<T>(
  key: readonly unknown[],
  queryFn: () => Promise<T>,
  options?: { enabled?: boolean },
) {
  const session = useAdminSession();
  return useQuery({
    queryKey: key,
    queryFn: async () => {
      try {
        return await queryFn();
      } catch (error) {
        if (isUnauthorized(error)) {
          session.expire();
        }
        throw error;
      }
    },
    enabled: options?.enabled ?? true,
    retry: false,
    staleTime: 30_000,
  });
}
