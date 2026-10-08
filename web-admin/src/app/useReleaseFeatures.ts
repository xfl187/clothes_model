import { useAdminApi } from '../api/AdminApiContext';
import { useAdminQuery } from '../api/useAdminQuery';
import type { ProductFeature } from '../api/adminApi';

export function useReleaseFeatures() {
  const api = useAdminApi();
  const query = useAdminQuery(['system-overview'], () => api.overview());
  const enabled = query.data?.effectiveConfiguration.enabledFeatures ?? new Set<ProductFeature>();
  return {
    ...query,
    productRelease: query.data?.effectiveConfiguration.productRelease,
    hasFeature: (feature: ProductFeature) => enabled.has(feature),
  };
}
