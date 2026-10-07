import type { PropsWithChildren, ReactNode } from 'react';

import styles from './ui.module.css';

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}

export function Section({ title, children }: PropsWithChildren<{ title: string }>) {
  return (
    <section className={styles.section} aria-label={title}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function StatusMark({ state, label }: { state: string; label: string }) {
  return (
    <span className={styles.statusMark} data-state={state}>
      {label}
    </span>
  );
}

export function VerdictStrip({
  verdict,
  label,
  snapshotAt,
}: {
  verdict: string;
  label: string;
  snapshotAt?: Date;
}) {
  return (
    <div className={styles.verdict} data-verdict={verdict} role="status">
      <span className={styles.verdictLabel}>{label}</span>
      {snapshotAt ? (
        <span className={styles.verdictMeta}>最近刷新 {snapshotAt.toLocaleTimeString()}</span>
      ) : null}
    </div>
  );
}

export function LedgerRow({
  label,
  state,
  value,
}: {
  label: string;
  state: string;
  value: ReactNode;
}) {
  return (
    <div className={styles.ledgerRow}>
      <span className={styles.ledgerLabel}>{label}</span>
      <StatusMark state={state} label={state} />
      <span>{value}</span>
    </div>
  );
}

export function Ledger({ children }: PropsWithChildren) {
  return <div className={styles.ledger}>{children}</div>;
}

export function VerificationRail({
  steps,
}: {
  steps: Array<{ key: string; status: string; detail?: string | null }>;
}) {
  return (
    <ol className={styles.rail}>
      {steps.map((step, index) => (
        <li key={step.key} className={styles.railStep}>
          <span className={styles.railIndex}>{index + 1}</span>
          <StatusMark state={step.status} label={step.key} />
          {step.detail ? <span>{step.detail}</span> : null}
        </li>
      ))}
    </ol>
  );
}

export function Card({ children }: PropsWithChildren) {
  return <div className={styles.card}>{children}</div>;
}

export function StateBlock({ children }: PropsWithChildren) {
  return <div className={styles.stateBlock}>{children}</div>;
}

export function ModuleError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={styles.moduleError} role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          重试
        </button>
      ) : null}
    </div>
  );
}

export function DataTable({
  columns,
  children,
}: PropsWithChildren<{ columns: string[] }>) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column} scope="col">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

export function ConfirmDialog({
  title,
  impact,
  confirmLabel,
  onConfirm,
  onCancel,
  busy,
}: {
  title: string;
  impact: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={title}>
      <div className="dialog">
        <p className="eyebrow">危险操作确认</p>
        <h2>{title}</h2>
        <div className="dialog-impact">{impact}</div>
        <div className="dialog-actions">
          <button type="button" onClick={onCancel} disabled={busy}>
            取消
          </button>
          <button type="button" className="danger" onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function OneTimeSecretDialog({
  token,
  onClose,
  acknowledged,
  onAcknowledge,
}: {
  token: string;
  onClose: () => void;
  acknowledged: boolean;
  onAcknowledge: (value: boolean) => void;
}) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="新的 App Token">
      <div className="dialog">
        <p className="eyebrow">敏感值一次性显示</p>
        <h2>新的 App Token</h2>
        <p className="dialog-impact">
          完整 Token 只会显示这一次。旧 Token 已立即失效，Android 需重新认证；服务端已有任务不受影响。
        </p>
        <code className="secret-value">{token}</code>
        <label className="dialog-check">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => onAcknowledge(event.target.checked)}
          />
          我已安全保存该 Token
        </label>
        <div className="dialog-actions">
          <button type="button" onClick={onClose} disabled={!acknowledged}>
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
