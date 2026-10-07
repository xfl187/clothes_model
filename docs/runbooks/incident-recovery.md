# Runbook: Incident recovery

Goal: recover from the confirmed V1 failure modes without re-executing work, re-charging, or losing
successful results.

## Backend offline / unreachable

- Android keeps local assets/drafts and pauses sync; server jobs continue.
- Web Admin shows the offline banner and disables writes; the last snapshot is timestamped.
- Restore connectivity; refresh. No job is cancelled or re-pointed.

## `needs_attention`

- Cause: external state could not be proven. The system stops auto-advancing.
- In Web Admin → `任务诊断`, open the item and choose: **requery** (sync known external state),
  **retry** (creates a new traceable item), or **finish as failed** (retains history/lineage).
- Never restart the same external execution; retry always creates a new item.

## Storage full / blocked `queued`

- New uploads and jobs are rejected; persisted `queued` work stays blocked with a reason and is not
  failed.
- Free space, then run Web Admin → `运行维护 / 存储` → scan → cleanup (protected references are skipped).
- Blocked tasks resume automatically; do not retry them one by one.

## Late result after cancel

- A result arriving after cancellation never enters history and is cleaned up.

## App Token invalid

- Android preserves the server address and prompts re-authentication; server jobs continue.
- Enter the current App Token (or rotate and use the new one); history re-syncs.

## Backup and disaster recovery

- Take a consistent backup with `infra/backup.ps1`; verify restores with
  `infra/verify-backup-restore.ps1`.
- Restore with `infra/restore.ps1` after stopping the Backend; never commit backups or secrets.

## Expected signals

- No duplicate external executions, no lost successful outputs, and no silent Provider changes.
