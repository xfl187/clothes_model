import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { problemFrom, problemSummary } from '../../api/adminApi';
import { Card, ConfirmDialog, DataTable, ModuleError, PageHeader, Section, StateBlock, StatusMark } from '../../components/ui';
import type { WorkflowVersion } from '../../api/adminApi';

export function WorkflowsPage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();
  const [message, setMessage] = useState<string>();
  const [confirmAction, setConfirmAction] = useState<'activate' | 'retire'>();

  const workflows = useAdminQuery(['workflows'], () => api.listWorkflows());
  const selected = useMemo(
    () => workflows.data?.find((item) => item.id === selectedId),
    [workflows.data, selectedId],
  );

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['workflows'] });
    await queryClient.invalidateQueries({ queryKey: ['system-overview'] });
  };

  const validate = useMutation({
    mutationFn: (id: string) => api.validateWorkflow(id),
    onSuccess: async () => {
      setMessage('结构校验与最小试运行已完成。');
      await refresh();
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });
  const activate = useMutation({
    mutationFn: (workflow: WorkflowVersion) => api.activateWorkflow(workflow.id),
    onSuccess: async () => {
      setMessage('版本已激活；只影响之后创建的新任务。');
      await refresh();
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });
  const retire = useMutation({
    mutationFn: (workflow: WorkflowVersion) => api.retireWorkflow(workflow.id),
    onSuccess: async () => {
      setMessage('版本已停用，旧活动版本保留为 retired。');
      await refresh();
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });

  const busy = validate.isPending || activate.isPending || retire.isPending;

  return (
    <div className="page">
      <PageHeader
        eyebrow="配置 / Workflows"
        title="Workflow 版本"
        description="按 workflow_id + mode 分组展示不可变版本；激活与回滚只影响新任务，已创建任务保持锁定版本。"
      />
      {message ? <p role="status">{message}</p> : null}
      {workflows.isPending ? <StateBlock>正在加载 Workflow…</StateBlock> : null}
      {workflows.isError ? (
        <ModuleError message={problemSummary(workflows.error)} onRetry={() => void workflows.refetch()} />
      ) : null}
      {workflows.data && workflows.data.length === 0 ? <StateBlock>尚未上传任何 Workflow。</StateBlock> : null}
      {workflows.data && workflows.data.length > 0 ? (
        <Section title="版本列表">
          <DataTable columns={['Workflow', '版本', '模式', '状态', '校验', '操作']}>
            {workflows.data.map((workflow) => (
              <tr
                key={workflow.id}
                data-selected={workflow.id === selectedId}
                onClick={() => setSelectedId(workflow.id)}
              >
                <td>{workflow.workflowId}</td>
                <td>v{workflow.version}</td>
                <td>{workflow.mode}</td>
                <td>
                  <StatusMark state={workflow.state} label={workflow.state} />
                </td>
                <td>{workflow.validationStatus ?? 'not_run'}</td>
                <td>
                  <button type="button" disabled={busy} onClick={() => validate.mutate(workflow.id)}>
                    校验
                  </button>{' '}
                  <button
                    type="button"
                    disabled={busy || workflow.state === 'active'}
                    onClick={() => {
                      setSelectedId(workflow.id);
                      setConfirmAction('activate');
                    }}
                  >
                    激活
                  </button>{' '}
                  <button
                    type="button"
                    disabled={busy || workflow.state !== 'active'}
                    onClick={() => {
                      setSelectedId(workflow.id);
                      setConfirmAction('retire');
                    }}
                  >
                    停用
                  </button>
                </td>
              </tr>
            ))}
          </DataTable>
        </Section>
      ) : null}

      {selected ? (
        <Section title="版本详情（Inspector）">
          <Card>
            <p>
              状态：<StatusMark state={selected.state} label={selected.state} />
            </p>
            <p>Workflow SHA256：{selected.artifacts?.workflowSha256 ?? '—'}</p>
            <p>Manifest SHA256：{selected.artifacts?.manifestSha256 ?? '—'}</p>
            <p>输出数量：{selected.manifestSummary?.outputCount ?? '—'}</p>
            {selected.validationMessages?.length ? (
              <ul>
                {selected.validationMessages.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <StateBlock>尚无校验信息。</StateBlock>
            )}
          </Card>
        </Section>
      ) : null}

      {confirmAction && selected ? (
        <ConfirmDialog
          busy={busy}
          title={confirmAction === 'activate' ? '激活 Workflow 版本' : '停用 Workflow 版本'}
          impact={
            confirmAction === 'activate'
              ? `将把 v${selected.version} 设为活动版本，新任务将使用该版本；旧活动版本保留为 retired。已创建任务不受影响。`
              : `将停用 v${selected.version}；新任务不再使用它，历史任务保持锁定。`
          }
          confirmLabel={confirmAction === 'activate' ? '确认激活' : '确认停用'}
          onCancel={() => setConfirmAction(undefined)}
          onConfirm={() => {
            const action = confirmAction;
            setConfirmAction(undefined);
            if (action === 'activate') activate.mutate(selected);
            else retire.mutate(selected);
          }}
        />
      ) : null}
    </div>
  );
}
