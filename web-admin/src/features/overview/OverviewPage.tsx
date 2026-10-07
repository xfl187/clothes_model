import { useAdminApi } from '../../api/AdminApiContext';
import { useAdminQuery } from '../../api/useAdminQuery';
import { problemSummary } from '../../api/adminApi';
import {
  Card,
  Ledger,
  LedgerRow,
  ModuleError,
  PageHeader,
  Section,
  StateBlock,
  StatusMark,
  VerdictStrip,
} from '../../components/ui';

const VERDICT_LABEL: Record<string, string> = {
  ok: '系统正常',
  limited: '系统受限',
  action_required: '需要管理员处理',
  unknown: '状态未知',
};

const DEPENDENCY_LABEL: Record<string, string> = {
  business_service: '业务服务',
  database: '数据库',
  storage: '存储',
  comfyui: 'ComfyUI',
};

const BLOCKER_LABEL: Record<string, string> = {
  waiting_provider: '等待 Provider 的任务',
  storage_blocked_queue: '因存储阻塞的队列',
  needs_attention: '需要人工处理的任务',
  configuration_fault: '配置故障阻止的任务',
};

export function OverviewPage() {
  const api = useAdminApi();
  const query = useAdminQuery(['system-overview'], () => api.overview());

  return (
    <div className="page">
      <PageHeader
        eyebrow="概览"
        title="系统状态与当前阻塞"
        description="回答三个问题：系统能否接收新任务、已有任务能否继续调度、管理员现在是否需要采取行动。"
      />
      {query.isPending ? <StateBlock>正在加载系统状态…</StateBlock> : null}
      {query.isError ? (
        <ModuleError message={problemSummary(query.error)} onRetry={() => void query.refetch()} />
      ) : null}
      {query.data ? (
        <>
          <VerdictStrip
            verdict={query.data.verdict}
            label={VERDICT_LABEL[query.data.verdict] ?? '状态未知'}
            snapshotAt={query.data.snapshotAt}
          />
          <Section title="四项系统依赖">
            <Ledger>
              {query.data.dependencies.map((dependency) => (
                <LedgerRow
                  key={dependency.key}
                  label={DEPENDENCY_LABEL[dependency.key] ?? dependency.key}
                  state={dependency.state}
                  value={dependency.detail ?? '—'}
                />
              ))}
            </Ledger>
          </Section>
          <Section title="运行阻塞">
            {query.data.blockers.length === 0 ? (
              <StateBlock>当前没有阻塞项。</StateBlock>
            ) : (
              <Ledger>
                {query.data.blockers.map((blocker) => (
                  <LedgerRow
                    key={blocker.kind}
                    label={BLOCKER_LABEL[blocker.kind] ?? blocker.kind}
                    state="needs_attention"
                    value={`${blocker.count} 项`}
                  />
                ))}
              </Ledger>
            )}
          </Section>
          <Section title="需要处理">
            {query.data.actionItems.length === 0 ? (
              <StateBlock>暂无需要处理的事项。</StateBlock>
            ) : (
              <Card>
                <ul>
                  {query.data.actionItems.map((item) => (
                    <li key={item.id}>
                      <StatusMark state={item.severity === 'critical' ? 'failed' : 'warning'} label={item.severity} />
                      {' '}
                      {item.summary}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </Section>
          <Section title="当前生效摘要">
            <Card>
              <p>默认 Provider：{query.data.effectiveConfiguration.defaultProvider?.providerId ?? '未设置'}</p>
              <p>活动 LLM 配置：{query.data.effectiveConfiguration.activeLlmProvider?.providerId ?? '无'}</p>
              <p>
                活动 Workflow：
                {query.data.effectiveConfiguration.activeWorkflow
                  ? `${query.data.effectiveConfiguration.activeWorkflow.workflowId} v${query.data.effectiveConfiguration.activeWorkflow.version}`
                  : '无'}
              </p>
            </Card>
          </Section>
        </>
      ) : null}
    </div>
  );
}
