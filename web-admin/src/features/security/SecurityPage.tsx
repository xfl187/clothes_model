import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { problemFrom, problemSummary } from '../../api/adminApi';
import { Card, ConfirmDialog, ModuleError, OneTimeSecretDialog, PageHeader, Section, StateBlock, StatusMark } from '../../components/ui';

export function SecurityPage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string>();
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [newToken, setNewToken] = useState<string>();
  const [acknowledged, setAcknowledged] = useState(false);

  const credential = useAdminQuery(['app-credential'], () => api.appCredential());

  const rotate = useMutation({
    mutationFn: () => api.rotateAppCredential(),
    onSuccess: async (rotation) => {
      setNewToken(rotation.token);
      setAcknowledged(false);
      setConfirmRotate(false);
      await queryClient.invalidateQueries({ queryKey: ['app-credential'] });
    },
    onError: async (error) => {
      setConfirmRotate(false);
      setMessage((await problemFrom(error)).detail);
    },
  });

  return (
    <div className="page">
      <PageHeader
        eyebrow="运行维护 / Token & Security"
        title="Token / Security"
        description="查看 App Token 标识与轮换时间。完整现值不显示；Admin Token 丢失只能通过服务器 SSH 重置。"
      />
      {message ? <p role="alert">{message}</p> : null}

      <Section title="App Token">
        {credential.isPending ? <StateBlock>正在读取 App Token 元数据…</StateBlock> : null}
        {credential.isError ? (
          <ModuleError message={problemSummary(credential.error)} onRetry={() => void credential.refetch()} />
        ) : null}
        {credential.data ? (
          <Card>
            <p>
              状态：<StatusMark state={credential.data.status} label={credential.data.status} />
            </p>
            <p>标识：{credential.data.tokenId}</p>
            <p>创建时间：{credential.data.createdAt.toLocaleString()}</p>
            <p>最近轮换：{credential.data.rotatedAt ? credential.data.rotatedAt.toLocaleString() : '从未轮换'}</p>
            <button type="button" className="danger" onClick={() => setConfirmRotate(true)}>
              轮换 App Token
            </button>
          </Card>
        ) : null}
      </Section>

      <Section title="Admin Token">
        <Card>
          <p>
            当前管理会话由安全 HttpOnly Cookie 维持。Admin Token 不提供网页轮换；丢失时必须通过服务器 SSH
            使用运维命令重置。
          </p>
        </Card>
      </Section>

      {confirmRotate ? (
        <ConfirmDialog
          busy={rotate.isPending}
          title="轮换 App Token"
          impact="旧 App Token 将立即失效，Android 需要重新认证；服务端已有任务不会被取消。新 Token 只会显示一次。"
          confirmLabel="确认轮换"
          onCancel={() => setConfirmRotate(false)}
          onConfirm={() => rotate.mutate()}
        />
      ) : null}

      {newToken ? (
        <OneTimeSecretDialog
          token={newToken}
          acknowledged={acknowledged}
          onAcknowledge={setAcknowledged}
          onClose={() => setNewToken(undefined)}
        />
      ) : null}
    </div>
  );
}
