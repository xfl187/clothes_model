import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { problemFrom, problemSummary } from '../../api/adminApi';
import { Card, ModuleError, PageHeader, Section, StateBlock, StatusMark } from '../../components/ui';

export function DefaultBackendPage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string>();

  const providers = useAdminQuery(['providers'], () => api.listProviders());
  const current = useAdminQuery(['default-provider'], () => api.defaultProvider(), {
    enabled: true,
  });

  const setDefault = useMutation({
    mutationFn: (providerId: string) => api.setDefaultProvider(providerId),
    onSuccess: async () => {
      setMessage('默认后端已更新，仅影响之后创建的新任务。');
      await queryClient.invalidateQueries({ queryKey: ['default-provider'] });
      await queryClient.invalidateQueries({ queryKey: ['system-overview'] });
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });

  const currentId = current.data?.providerId;

  return (
    <div className="page">
      <PageHeader
        eyebrow="配置 / 默认后端"
        title="默认后端"
        description="显式选择新任务的默认后端。更改只影响新任务；等待中、运行中和 needs_attention 的任务继续使用其锁定配置。"
      />
      {message ? <p role="status">{message}</p> : null}
      {providers.isPending ? <StateBlock>正在加载后端…</StateBlock> : null}
      {providers.isError ? (
        <ModuleError message={problemSummary(providers.error)} onRetry={() => void providers.refetch()} />
      ) : null}
      {providers.data ? (
        <Section title="可选后端">
          {providers.data.length === 0 ? <StateBlock>尚未配置任何 Provider。</StateBlock> : null}
          {providers.data.map((provider) => {
            const selectable = provider.state === 'active' || provider.state === 'validated';
            const isDefault = provider.id === currentId;
            return (
              <Card key={provider.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}>
                  <div>
                    <StatusMark state={provider.state} label={provider.state} />
                    <strong style={{ marginLeft: 10 }}>{provider.displayName}</strong>
                    <p style={{ margin: '6px 0 0', color: 'var(--muted)', fontSize: 13 }}>
                      版本 {provider.configRef.revision} · 模型 {provider.model}
                    </p>
                    {!selectable ? (
                      <p style={{ margin: '6px 0 0', color: 'var(--warning-ink)', fontSize: 13 }}>
                        该配置未验证或已归档，不能被选择为默认后端。
                      </p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    disabled={!selectable || isDefault || setDefault.isPending}
                    onClick={() => setDefault.mutate(provider.id)}
                  >
                    {isDefault ? '当前默认' : '设为默认'}
                  </button>
                </div>
              </Card>
            );
          })}
        </Section>
      ) : null}
    </div>
  );
}
