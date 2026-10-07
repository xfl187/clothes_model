import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { isOffline, problemFrom, problemSummary } from '../../api/adminApi';
import { Card, ConfirmDialog, ModuleError, PageHeader, Section, StateBlock, StatusMark, VerificationRail } from '../../components/ui';

export function ComfyNodePage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [endpoint, setEndpoint] = useState('');
  const [timeoutSeconds, setTimeoutSeconds] = useState(30);
  const [enabled, setEnabled] = useState(false);
  const [credential, setCredential] = useState('');
  const [message, setMessage] = useState<string>();
  const [pendingDisable, setPendingDisable] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const node = useAdminQuery(['comfy-node'], () => api.comfyNode(), { enabled: true });
  const config = node.data;

  if (!loaded && config) {
    setLoaded(true);
    setEndpoint(config.endpoint);
    setTimeoutSeconds(config.timeoutSeconds);
    setEnabled(config.enabled);
  }

  const save = useMutation({
    mutationFn: () =>
      api.updateComfyNode({
        endpoint,
        timeoutSeconds,
        enabled,
        credential: credential.trim() ? credential : undefined,
      }),
    onSuccess: async () => {
      setCredential('');
      setMessage('节点配置已保存。');
      await queryClient.invalidateQueries({ queryKey: ['comfy-node'] });
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });

  const test = useMutation({
    mutationFn: () => api.testComfyNode(),
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });

  const offline = isOffline(node.error ?? save.error ?? test.error);

  if (node.isError && !(isOffline(node.error))) {
    const status = (node.error as { response?: { status?: number } })?.response?.status;
    if (status !== 404) {
      return (
        <div className="page">
          <PageHeader eyebrow="配置 / ComfyUI 节点" title="ComfyUI 节点" />
          <ModuleError message={problemSummary(node.error)} onRetry={() => void node.refetch()} />
        </div>
      );
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="配置 / ComfyUI 节点"
        title="ComfyUI 节点"
        description="维护单个可替换节点。当前生效配置、编辑草稿与实时健康结论分层展示；启用前请先完成连接测试与最小试运行。"
      />
      {offline ? <p role="status">后端离线，写操作已停用；显示最近一次已知状态。</p> : null}
      {message ? <p role="status">{message}</p> : null}

      <div className="grid" data-columns="2">
        <Section title="当前生效与编辑">
          <Card>
            <label>
              节点地址
              <input
                type="url"
                value={endpoint}
                onChange={(event) => setEndpoint(event.target.value)}
                disabled={offline}
              />
            </label>
            <label>
              超时（秒）
              <input
                type="number"
                min={1}
                max={3600}
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
                disabled={offline}
              />
            </label>
            <label>
              认证覆盖（留空保留已保存值）
              <input
                type="password"
                value={credential}
                onChange={(event) => setCredential(event.target.value)}
                placeholder={config?.credentialConfigured ? '已配置，留空保留' : '未配置'}
                disabled={offline}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                disabled={offline}
              />
              启用节点
            </label>
            <div className="dialog-actions">
              <button type="button" onClick={() => test.mutate()} disabled={offline || test.isPending}>
                测试连接
              </button>
              <button type="button" onClick={() => save.mutate()} disabled={offline || save.isPending}>
                保存配置
              </button>
              {config?.enabled ? (
                <button type="button" className="danger" onClick={() => setPendingDisable(true)} disabled={offline}>
                  停用节点
                </button>
              ) : null}
            </div>
          </Card>
        </Section>

        <Section title="实时健康与验证">
          <Card>
            {config ? (
              <p>
                健康：
                <StatusMark state={config.health} label={config.health} />
                {' '}· 活动 Workflow 兼容性：
                <StatusMark
                  state={config.activeWorkflowCompatibility?.status ?? 'unknown'}
                  label={config.activeWorkflowCompatibility?.status ?? 'unknown'}
                />
              </p>
            ) : (
              <StateBlock>节点尚未配置。</StateBlock>
            )}
            {test.data ? (
              <>
                <VerificationRail
                  steps={[
                    { key: '连接与节点依赖', status: test.data.status, detail: test.data.detail },
                  ]}
                />
                <p>
                  连接测试：
                  <StatusMark state={test.data.status} label={test.data.status} />
                </p>
              </>
            ) : (
              <StateBlock>尚未执行连接测试。</StateBlock>
            )}
          </Card>
        </Section>
      </div>

      {pendingDisable ? (
        <ConfirmDialog
          title="停用 ComfyUI 节点"
          impact="停用后新的 ComfyUI 任务可能进入等待；等待中的任务仍需按锁定 Workflow 做兼容性检查。历史锁定配置不会被改写。"
          confirmLabel="停用节点"
          onCancel={() => setPendingDisable(false)}
          onConfirm={() => {
            setEnabled(false);
            setPendingDisable(false);
            save.mutate();
          }}
        />
      ) : null}
    </div>
  );
}
