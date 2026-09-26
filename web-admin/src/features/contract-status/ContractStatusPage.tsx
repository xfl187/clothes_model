import { useQuery } from '@tanstack/react-query';

import { useContractGateway } from '../../app/ContractGatewayContext';
import styles from './ContractStatusPage.module.css';

function SupportValue({ supported }: { supported: boolean }) {
  return <span>{supported ? '支持' : '不支持'}</span>;
}

export function ContractStatusPage() {
  const gateway = useContractGateway();
  const status = useQuery({
    queryKey: ['contract-status'],
    queryFn: () => gateway.loadStatus(),
  });

  return (
    <main className={`page ${styles.page}`}>
      <header className={styles.heading}>
        <div>
          <p className="eyebrow">Contract proof</p>
          <h1>三端共享契约可以被 Web 消费。</h1>
        </div>
        <button type="button" onClick={() => void status.refetch()} disabled={status.isFetching}>
          {status.isFetching ? '正在检查…' : '重新检查'}
        </button>
      </header>

      {status.isPending ? (
        <section className={styles.notice} aria-live="polite">正在读取契约示例，不提前推断系统结论。</section>
      ) : null}

      {status.isError ? (
        <section className={styles.error} role="alert">
          <strong>契约读取失败</strong>
          <span>{status.error.message}</span>
        </section>
      ) : null}

      {status.data ? (
        <div className={styles.ledger} aria-live="polite">
          <section className={styles.row} aria-labelledby="health-title">
            <div>
              <p className="eyebrow">Health</p>
              <h2 id="health-title">服务健康结论</h2>
            </div>
            <dl>
              <div><dt>状态</dt><dd>{status.data.health.status}</dd></div>
              <div><dt>采样时间</dt><dd>{status.data.health.checkedAt}</dd></div>
            </dl>
          </section>

          <section className={styles.row} aria-labelledby="job-title">
            <div>
              <p className="eyebrow">JobState</p>
              <h2 id="job-title">任务状态样本</h2>
            </div>
            <dl>
              <div><dt>状态</dt><dd>{status.data.job.state}</dd></div>
              <div><dt>候选</dt><dd>{status.data.job.candidateCount}</dd></div>
              <div><dt>任务 ID</dt><dd className={styles.mono}>{status.data.job.id}</dd></div>
            </dl>
          </section>

          <section className={styles.row} aria-labelledby="capability-title">
            <div>
              <p className="eyebrow">Provider capability</p>
              <h2 id="capability-title">{status.data.capability.providerName}</h2>
            </div>
            <dl>
              <div><dt>可用性</dt><dd>{status.data.capability.availability}</dd></div>
              <div><dt>Schema</dt><dd>v{status.data.capability.schemaVersion}</dd></div>
              <div><dt>手动遮罩</dt><dd><SupportValue supported={status.data.capability.manualMask} /></dd></div>
              <div><dt>多候选</dt><dd><SupportValue supported={status.data.capability.multipleCandidates} /></dd></div>
            </dl>
          </section>
        </div>
      ) : null}
    </main>
  );
}
