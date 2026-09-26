FROM node:24.20.0-bookworm-slim AS web-build

WORKDIR /workspace
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web-admin/package.json ./web-admin/package.json
RUN corepack pnpm@10.34.5 install --frozen-lockfile --filter @clothes-model/web-admin...
COPY web-admin ./web-admin
RUN corepack pnpm@10.34.5 --filter @clothes-model/web-admin build

FROM python:3.14.7-slim-bookworm AS backend-build

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY backend ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.14.7-slim-bookworm AS runtime

RUN groupadd --gid 10001 clothes-model \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin clothes-model \
    && mkdir -p /app/backend /app/web \
        /var/lib/clothes-model/db \
        /var/lib/clothes-model/storage \
        /var/lib/clothes-model/runtime \
    && chown -R clothes-model:clothes-model /app /var/lib/clothes-model

COPY --from=backend-build --chown=10001:10001 /app/backend /app/backend
COPY --from=web-build --chown=10001:10001 /workspace/web-admin/dist /app/web
COPY --chown=10001:10001 --chmod=755 infra/docker/entrypoint.sh /usr/local/bin/clothes-model-entrypoint

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/clothes-model-entrypoint"]
