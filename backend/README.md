# Backend

Python 3.14 / FastAPI modular-monolith skeleton for the Clothes Model service.

Run quality commands from this directory with `uv sync --locked`, followed by
Ruff, Pyright, and Pytest through `uv run`. Development overrides are read from
the ignored `.env` file with the `CLOTHES_MODEL_` prefix.

All non-health routes are contract-shaped Phase 1 stubs. They return safe
`application/problem+json` responses and contain no business behavior.

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
