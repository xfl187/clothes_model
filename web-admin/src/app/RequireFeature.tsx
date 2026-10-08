import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import type { ProductFeature } from '../api/generated/models/ProductFeature';
import { ModuleError, StateBlock } from '../components/ui';
import { useReleaseFeatures } from './useReleaseFeatures';

export function RequireFeature({ feature, children }: { feature: ProductFeature; children: ReactNode }) {
  const release = useReleaseFeatures();
  if (release.isPending) return <main className="page"><StateBlock>正在读取版本能力…</StateBlock></main>;
  if (release.isError) {
    return <main className="page"><ModuleError message="无法读取版本能力。" onRetry={() => void release.refetch()} /></main>;
  }
  return release.hasFeature(feature) ? children : <Navigate replace to="/overview" />;
}
