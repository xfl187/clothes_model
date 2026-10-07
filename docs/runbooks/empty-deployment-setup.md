# Runbook: Empty deployment setup

Goal: turn a fresh checkout into a running V1 system with Web Admin and Android connected.

## Prerequisites

- Docker Desktop (Linux containers), Node.js 24 + Corepack, Python 3.14 + `uv` (or the locked
  `backend/.venv`), JDK 17 + Android SDK for the device.
- A host secret for `CLOTHES_MODEL_ENCRYPTION_MASTER_KEY`.
- Repository host/domain and TLS termination (Caddy in the production profile).

## Procedure

```powershell
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY='<host-held-secret>'
docker compose -f infra/compose.yaml --profile production build --no-cache app
docker compose -f infra/compose.yaml --profile production up -d --no-build
curl.exe --fail --insecure https://localhost:8443/health/ready
```

1. Bootstrap the one-time credentials from the running container:
   `docker compose -f infra/compose.yaml --profile production exec -T app clothes-model-security bootstrap`
2. Save both tokens in one operator-owned file outside the repository (see
   [credential lifecycle](credential-lifecycle.md)).
3. Configure generation infrastructure: [provider configuration](provider-configuration.md) and
   [workflow publish and rollback](workflow-publish-rollback.md).
4. Connect Android with the App Token; connect Web Admin with the Admin Token.

## Expected signals

- `/health/ready` returns `status=ok` with `checks.scheduler=owned`.
- Web Admin login reaches the `概览` page; the overview verdict is `ok` or `limited` with an
  explanation.

## Recovery

- If readiness never becomes `ok`, inspect `docker compose ... logs app` for migration or scheduler-lock
  failures.
- If credentials are lost, rotate or reset them in [credential lifecycle](credential-lifecycle.md).
