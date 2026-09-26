#!/bin/sh
set -eu

python -m clothes_model.infrastructure.database.migrations

exec uvicorn clothes_model.main:app \
    --host "${CLOTHES_MODEL_BIND_HOST:-0.0.0.0}" \
    --port "${CLOTHES_MODEL_BIND_PORT:-8000}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "${CLOTHES_MODEL_FORWARDED_ALLOW_IPS:-*}"
