# Backend

Python 3.14 / FastAPI modular-monolith skeleton for the Clothes Model service.

Run quality commands from this directory with `uv sync --locked`, followed by
Ruff, Pyright, and Pytest through `uv run`. Development overrides are read from
the ignored `.env` file with the `CLOTHES_MODEL_` prefix.

Phase 1–2 routes and the Phase 3 Jobs/Providers routes are implemented. Remaining
Workflows, Cleanup, ComfyNode, Retention, and storage-scan routes stay
contract-shaped stubs that return safe `application/problem+json` responses.

## Phase 3 durable jobs and providers

- A single in-process scheduler owns durable claims. `CLOTHES_MODEL_SCHEDULER_ENABLED`
  enables it; it must never be enabled on more than one replica or worker (ADR-0005,
  ADR-0008). A second owner fails closed through the instance lock.
- `CLOTHES_MODEL_SCHEDULER_POLL_INTERVAL_SECONDS`, `CLOTHES_MODEL_SCHEDULER_BATCH_SIZE`,
  and `CLOTHES_MODEL_SCHEDULER_LEASE_MINUTES` bound polling, concurrency, and leases.
- Restart reconciliation re-queues safe pre-submission `preparing` work, releases
  stale claims, and moves uncertain prior-`running` work to `needs_attention`. It
  never blindly resubmits work whose external outcome is unknown.
- `waiting_provider` waits indefinitely and does not consume the retry budget.
  Transient failures use persisted exponential backoff; configuration failures stop
  automatic execution.
- The deterministic `fake_image_edit` adapter exists only for test/development and is
  rejected in `production`. The first real LLM adapter belongs to Phase 4.
- Provider credentials are stored as AES-256-GCM envelopes and are never returned by
  any API, snapshot, event, or log. `/health/ready` and the admin diagnostics routes
  expose only redacted counts and labels.

## Security operator commands

After configuring the database, initialize missing credentials with
`uv run clothes-model-security bootstrap`. Each new App/Admin Token is printed
exactly once; repeating the command preserves active credentials and prints no
secret. Recover a lost Admin credential with
`uv run clothes-model-security reset-admin`. The reset revokes active Admin
credentials and their browser-session lineage before issuing the replacement.

`CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE` must point to a read-only file whose
entire content is URL-safe base64 (padding optional) for exactly 32 random
bytes. Preserve this file with the SQLite database and private storage; the
Backend fails closed when the key is missing, malformed, changed, or does not
authenticate an encrypted value.
