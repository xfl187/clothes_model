# Backend

Python 3.14 / FastAPI modular-monolith skeleton for the Clothes Model service.

Run quality commands from this directory with `uv sync --locked`, followed by
Ruff, Pyright, and Pytest through `uv run`. Development overrides are read from
the ignored `.env` file with the `CLOTHES_MODEL_` prefix.

All non-health routes are contract-shaped Phase 1 stubs. They return safe
`application/problem+json` responses and contain no business behavior.
