# Infrastructure

Docker Compose is the fixed Linux deployment model for V1. This directory owns local orchestration, the production application image, Caddy, persistent volumes, migration-first startup, and the secret-injection boundary. It does not introduce Kubernetes, Redis, Kafka, PostgreSQL, an independent worker fleet, or multiple ComfyUI nodes.

## Profiles

| Profile | Services | Intended use |
|---|---|---|
| `contract` | `contract-mock` | OpenAPI-backed client development on port 4010 |
| `development` | `backend` | Backend-only development on port 8000 with explicit Web dev CORS |
| `production` | `app`, `caddy` | Production-shaped single-instance application behind Caddy TLS |

Profiles are independent. Starting `production` never starts the mock server.

## Production-shaped startup

PowerShell:

```powershell
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY='<local-secret>'
docker compose -f infra/compose.yaml --profile production up --build
```

The host environment value is mounted at `/run/secrets/encryption_master_key`; only that file path is passed to Backend configuration. The container entrypoint runs Alembic before starting exactly one Uvicorn worker. The same process owns scheduler startup, and the scheduler uses the persistent runtime lock to reject a second owner.

Persistent named volumes are intentionally split:

- `app-sqlite` for `/var/lib/clothes-model/sqlite`;
- `app-private-storage` for `/var/lib/clothes-model/private`;
- `app-runtime` for `/var/lib/clothes-model/runtime` and the scheduler lock.

`docker compose down` removes containers and the network but preserves these volumes. Do not add `--volumes` when validating restart persistence.

## Verification

```powershell
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY='phase1-local-verification-only'
docker compose -f infra/compose.yaml --profile contract --profile production build --no-cache contract-mock app
docker compose -f infra/compose.yaml --profile production config --services
docker compose -f infra/compose.yaml --profile production up -d
curl.exe --insecure https://localhost:8443/health/live
curl.exe --insecure https://localhost:8443/
docker compose -f infra/compose.yaml --profile production restart app
```

Expected production services are exactly `app` and `caddy`. After restart, the SQLite file remains on `app-sqlite`. Starting another `app` container while the first is healthy must terminate with the scheduler ownership error. Use the secret value above only for disposable local verification; it is not a deployable credential.
