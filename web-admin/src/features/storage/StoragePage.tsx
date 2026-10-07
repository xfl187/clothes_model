import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { isOffline, problemFrom, problemSummary } from '../../api/adminApi';
import { Card, ConfirmDialog, ModuleError, PageHeader, Section, StateBlock, StatusMark } from '../../components/ui';

function formatBytes(value: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
}

export function StoragePage() {
  const api = useAdminApi();
  const queryClient = useQueryClient();
  const [outputDays, setOutputDays] = useState<number>();
  const [intermediateDays, setIntermediateDays] = useState<number>();
  const [message, setMessage] = useState<string>();
  const [confirmCleanup, setConfirmCleanup] = useState(false);

  const status = useAdminQuery(['storage-status'], () => api.storageStatus());
  const retention = useAdminQuery(['retention'], () => api.retention());

  const outputs = outputDays ?? retention.data?.unfavoritedOutputDays ?? 30;
  const intermediates = intermediateDays ?? retention.data?.intermediateFileDays ?? 7;
  const offline = isOffline(status.error ?? retention.error);

  const saveRetention = useMutation({
    mutationFn: () => api.updateRetention(outputs, intermediates),
    onSuccess: async () => {
      setMessage('保留期限已更新。');
      await queryClient.invalidateQueries({ queryKey: ['retention'] });
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });
  const scan = useMutation({
    mutationFn: () => api.scanStorage(),
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });
  const cleanup = useMutation({
    mutationFn: () => api.cleanup(scan.data?.scanId as string),
    onSuccess: async () => {
      setMessage('清理完成；因空间不足入队的任务将自动继续调度。');
      setConfirmCleanup(false);
      await queryClient.invalidateQueries({ queryKey: ['storage-status'] });
    },
    onError: async (error) => setMessage((await problemFrom(error)).detail),
  });

  return (
    <div className="page">
      <PageHeader
        eyebrow="运行维护 / 存储"
        title="存储管理"
        description="容量结论、受保护与可清理分类，以及受 Product Spec 约束的保留期限。手动清理不可撤销，受引用保护的文件会被跳过。"
      />
      {offline ? <p role="status">后端离线，写操作已停用。</p> : null}
      {message ? <p role="status">{message}</p> : null}

      <Section title="容量">
        {status.isPending ? <StateBlock>正在读取容量…</StateBlock> : null}
        {status.isError ? (
          <ModuleError message={problemSummary(status.error)} onRetry={() => void status.refetch()} />
        ) : null}
        {status.data ? (
          <Card>
            <p>
              结论：<StatusMark state={status.data.state} label={status.data.state} />
            </p>
            <p>
              总量 {formatBytes(status.data.capacityBytes)} · 已用 {formatBytes(status.data.usedBytes)} · 可用{' '}
              {formatBytes(status.data.availableBytes)}
            </p>
            <p>{status.data.acceptingNewWork ? '正在接收新上传和新任务。' : `已停止接收：${status.data.blockReason ?? '空间不足'}`}</p>
          </Card>
        ) : null}
      </Section>

      <Section title="保留期限">
        {retention.isError ? (
          <ModuleError message={problemSummary(retention.error)} onRetry={() => void retention.refetch()} />
        ) : null}
        <Card>
          <label>
            未收藏结果保留天数
            <input
              type="number"
              min={1}
              value={outputs}
              onChange={(event) => setOutputDays(Number(event.target.value))}
              disabled={offline}
            />
          </label>
          <label>
            中间文件保留天数
            <input
              type="number"
              min={1}
              value={intermediates}
              onChange={(event) => setIntermediateDays(Number(event.target.value))}
              disabled={offline}
            />
          </label>
          <div className="dialog-actions">
            <button type="button" onClick={() => saveRetention.mutate()} disabled={offline || saveRetention.isPending}>
              保存保留期限
            </button>
          </div>
        </Card>
      </Section>

      <Section title="扫描与清理">
        <Card>
          <button type="button" onClick={() => scan.mutate()} disabled={offline || scan.isPending}>
            扫描可清理文件
          </button>
          {scan.data ? (
            <div style={{ marginTop: 12 }}>
              <p>
                可清理 {scan.data.reclaimableFiles} 个文件（{formatBytes(scan.data.reclaimableBytes)}），受保护{' '}
                {scan.data.protectedFiles} 个。
              </p>
              <button type="button" className="danger" onClick={() => setConfirmCleanup(true)}>
                执行清理
              </button>
            </div>
          ) : null}
        </Card>
      </Section>

      {confirmCleanup && scan.data ? (
        <ConfirmDialog
          busy={cleanup.isPending}
          title="执行存储清理"
          impact={`将删除 ${scan.data.reclaimableFiles} 个已到期文件，跳过 ${scan.data.protectedFiles} 个受引用保护或收藏的文件。文件删除不可恢复；历史元数据与删除占位保留。`}
          confirmLabel="确认清理"
          onCancel={() => setConfirmCleanup(false)}
          onConfirm={() => cleanup.mutate()}
        />
      ) : null}
    </div>
  );
}
