FROM node:24.20.0-bookworm-slim

WORKDIR /app
COPY contracts/tooling/package.json contracts/tooling/pnpm-lock.yaml ./tooling/
RUN corepack pnpm@10.34.5 --dir /app/tooling install --frozen-lockfile
COPY contracts/generated/openapi.yaml ./contracts/openapi.yaml

EXPOSE 4010
CMD ["corepack", "pnpm@10.34.5", "--dir", "/app/tooling", "exec", "prism", "mock", "/app/contracts/openapi.yaml", "--host", "0.0.0.0", "--port", "4010"]
