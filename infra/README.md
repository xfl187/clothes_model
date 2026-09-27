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
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE_SOURCE='C:\secure\encryption_master_key'
docker compose -f infra/compose.yaml --profile production up --build
```

The host environment value is mounted at `/run/secrets/encryption_master_key`; only that file path is passed to Backend configuration. The container entrypoint runs Alembic before starting exactly one Uvicorn worker. The same process owns scheduler startup, and the scheduler uses the persistent runtime lock to reject a second owner.

Persistent named volumes are intentionally split:

- `sqlite_data` for `/var/lib/clothes-model/db`;
- `private_storage` for `/var/lib/clothes-model/storage`;
- `instance_runtime` for `/var/lib/clothes-model/runtime` and the scheduler lock.

The SQLite volume, private-storage volume, and encryption master-key source are
one backup set. Quiesce the single application process before copying them.
Restore all three from the same snapshot; restoring only SQLite or storage can
leave referenced content missing, while restoring encrypted configuration
without its original 32-byte master key makes those secrets unrecoverable by
design. Never place token values or the decoded master key in diagnostic logs.

First deployment runs `uv run clothes-model-security bootstrap` inside the
application image after migrations. It prints missing App/Admin credentials
once. `reset-admin` is the server-side recovery boundary for a lost Admin
Token; `rotate-app` immediately revokes the previous App credential without
cancelling persisted server work.

`docker compose down` removes containers and the network but preserves these volumes. Do not add `--volumes` when validating restart persistence.

## Verification

```powershell
./contracts/tooling/verify-phase2.ps1
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE_SOURCE='C:\secure\encryption_master_key'
docker compose -f infra/compose.yaml --profile contract --profile production build --no-cache contract-mock app
docker compose -f infra/compose.yaml --profile production config --services
docker compose -f infra/compose.yaml --profile production up -d
curl.exe --insecure https://localhost:8443/health/live
curl.exe --insecure https://localhost:8443/
docker compose -f infra/compose.yaml --profile production restart app
```

Expected production services are exactly `app` and `caddy`. After restart, the SQLite file remains on `sqlite_data`. Starting another `app` container while the first is healthy must terminate with the scheduler ownership error. Generate the verification file outside the repository; never place its contents in `.env` or command history.

## Phase 4 Seedream boundary

The production adapter is fixed to `https://ark.cn-beijing.volces.com/api/v3`
and model `doubao-seedream-4-5-251128`. Activate the model in Volcengine Ark,
then enter the API Key only in Web Admin. The key is encrypted with the existing
master key; it is deliberately absent from Compose and `.env`.

Admin validation performs one billable synthetic generation and discards its
output. Enabling and selecting the Provider as default remain separate actions.
The regular Phase 4 check is deterministic and free:

```powershell
./infra/verify-phase4-deployment.ps1
```

The credentialed adapter smoke is opt-in and creates exactly one image. Inject
the key through a temporary environment secret, never a command argument:

```powershell
$env:CLOTHES_MODEL_PHASE4_ARK_API_KEY='<securely supplied>'
./infra/verify-phase4-deployment.ps1 -Credentialed
Remove-Item Env:CLOTHES_MODEL_PHASE4_ARK_API_KEY
```

This smoke verifies credentials, model access, request construction, and output
decoding. The clean-deployment product loop is then checked through Web Admin
and Android so its result is persisted through the authenticated app path.

## Phase 5 ComfyUI boundary

Raw ComfyUI exposes an unauthenticated, implementation-facing server protocol
for image upload, prompt submission, queue/history lookup, output viewing, and
queue deletion. It must never be reachable directly from the public internet.
Deploy it behind an authenticated reverse proxy or a private tunnel/VPN, and
register only that protected endpoint as the singleton `ComfyNodeConfig`. The
Backend refuses non-HTTPS endpoints and any host that is not in the deployment
allowlist, so it cannot be used as an unrestricted network proxy.

The deterministic Phase 5 gate needs no GPU, network, or paid service. It uses
an in-process ComfyUI fixture and runs in normal CI:

```powershell
./infra/verify-phase5-deployment.ps1
```

It configures a node, creates/validates/activates an immutable Workflow, locks
it at job creation, executes a mocked prompt, persists the private output,
recovers a storage-blocked remote completion without resubmitting, and requeries
a known `prompt_id` after a simulated restart. A credentialed AutoDL/Comfy run is
manual until the target node is provisioned; it must stay bounded and must never
run on ordinary pull requests.
