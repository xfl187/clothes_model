import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { problemFrom, problemSummary } from '../../api/adminApi';
import { Card, DataTable, ModuleError, PageHeader, Section, StateBlock, StatusMark } from '../../components/ui';

const STATES = [
  'queued',
  'waiting_provider',
  'preparing',
  'running',
  'needs_attention',
  'succeeded',
  'partially_succeeded',
  'failed',
  'cancelled',
];

export function DiagnosticsPage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [state, setState] = useState('');
  const [selectedId, setSelectedId] = useState<string>();
  const [message, setMessage] = useState<string>();

  const jobs = useAdminQuery(['diagnostic-jobs', state], () =>
    api.listDiagnosticJobs({ state: state || undefined, limit: 50 }),
  );
  const detail = useAdminQuery(
    ['diagnostic-job', selectedId],
    () => api.diagnosticJob(selectedId as string),
    { enabled: Boolean(selectedId) },
  );

  const refresh = async () => {
    setMessage(undefined);
    await queryClient.invalidateQueries({ queryKey: ['diagnostic-jobs'] });
    await queryClient.invalidateQueries({ queryKey: ['diagnostic-job', selectedId] });
  };
  const onError = async (error: unknown) => setMessage((await problemFrom(error)).detail);

  const cancelJob = useMutation({ mutationFn: (id: string) => api.cancelJob(id), onSuccess: refresh, onError });
  const cancelItem = useMutation({ mutationFn: (id: string) => api.cancelJobItem(id), onSuccess: refresh, onError });
  const retryItem = useMutation({ mutationFn: (id: string) => api.retryJobItem(id), onSuccess: refresh, onError });
  const requeryItem = useMutation({ mutationFn: (id: string) => api.requeryJobItem(id), onSuccess: refresh, onError });
  const finishFailed = useMutation({
    mutationFn: (id: string) => api.finishJobItemFailed(id, '管理员结束为失败'),
    onSuccess: refresh,
    onError,
  });

  const busy =
    cancelJob.isPending || cancelItem.isPending || retryItem.isPending ||
    requeryItem.isPending || finishFailed.isPending;
  const job = detail.data?.job;

  return (
    <div className="page">
      <PageHeader
        eyebrow="运行维护 / 任务诊断"
        title="任务诊断"
        description="高密度表格与右侧详情。操作由任务状态决定；终态不显示取消，也不允许把重新提交显示为原执行继续。"
      />
      {message ? <p role="alert">{message}</p> : null}
      <div style={{ margin: '16px 0' }}>
        <label>
          状态筛选{' '}
          <select value={state} onChange={(event) => setState(event.target.value)}>
            <option value="">全部</option>
            {STATES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      {jobs.isPending ? <StateBlock>正在加载任务…</StateBlock> : null}
      {jobs.isError ? (
        <ModuleError message={problemSummary(jobs.error)} onRetry={() => void jobs.refetch()} />
      ) : null}
      {jobs.data && jobs.data.items.length === 0 ? <StateBlock>没有符合条件的任务。</StateBlock> : null}
      {jobs.data && jobs.data.items.length > 0 ? (
        <DataTable columns={['任务 ID', '状态', 'Provider', '候选数', '更新时间', '阻塞']}>
          {jobs.data.items.map((item) => (
            <tr key={item.jobId} data-selected={item.jobId === selectedId} onClick={() => setSelectedId(item.jobId)}>
              <td>{item.jobId}</td>
              <td>
                <StatusMark state={item.state} label={item.state} />
              </td>
              <td>{item.providerLabel}</td>
              <td>{item.itemCount}</td>
              <td>{item.updatedAt.toLocaleString()}</td>
              <td>—</td>
            </tr>
          ))}
        </DataTable>
      ) : null}

      {selectedId ? (
        <Section title="任务详情（Inspector）">
          {detail.isPending ? <StateBlock>正在加载详情…</StateBlock> : null}
          {detail.isError ? (
            <ModuleError message={problemSummary(detail.error)} onRetry={() => void detail.refetch()} />
          ) : null}
          {job ? (
            <Card>
              <p>
                当前结论：<StatusMark state={job.state} label={job.state} />
                {job.blockReason ? ` · 阻塞：${job.blockReason}` : ''}
              </p>
              {job.blockedDetail ? <p>{job.blockedDetail}</p> : null}
              <p>
                锁定 Provider：{job.providerConfigRef.providerId} 版本 {job.providerConfigRef.revision}
              </p>
              <p>
                锁定 Workflow：
                {job.workflowVersionRef ? `${job.workflowVersionRef.workflowId} v${job.workflowVersionRef.version}` : '无'}
              </p>
              {['queued', 'waiting_provider', 'preparing', 'running'].includes(job.state) ? (
                <button type="button" className="danger" disabled={busy} onClick={() => cancelJob.mutate(job.id)}>
                  取消未完成候选
                </button>
              ) : null}
              <h3>候选子任务</h3>
              <DataTable columns={['候选', '状态', '尝试', '操作']}>
                {job.items.map((item) => (
                  <tr key={item.id}>
                    <td>#{item.candidateIndex}</td>
                    <td>
                      <StatusMark state={item.state} label={item.state} />
                    </td>
                    <td>{item.attempt}</td>
                    <td>
                      {['queued', 'waiting_provider', 'preparing', 'running'].includes(item.state) ? (
                        <button type="button" disabled={busy} onClick={() => cancelItem.mutate(item.id)}>
                          取消
                        </button>
                      ) : null}
                      {item.state === 'needs_attention' ? (
                        <>
                          <button type="button" disabled={busy} onClick={() => requeryItem.mutate(item.id)}>
                            重新查询
                          </button>{' '}
                          <button type="button" disabled={busy} onClick={() => retryItem.mutate(item.id)}>
                            创建重试
                          </button>{' '}
                          <button type="button" disabled={busy} onClick={() => finishFailed.mutate(item.id)}>
                            结束为失败
                          </button>
                        </>
                      ) : null}
                      {['failed', 'partially_succeeded'].includes(item.state) ? (
                        <button type="button" disabled={busy} onClick={() => retryItem.mutate(item.id)}>
                          按原参数重试
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </DataTable>
              <h3>脱敏外部事件</h3>
              <ul>
                {detail.data?.redactedExternalEvents.map((event, index) => (
                  <li key={`${event.at.toString()}-${index}`}>
                    {event.at.toLocaleString()} · {event.category} · {event.conclusion}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </Section>
      ) : null}
    </div>
  );
}
