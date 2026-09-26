# Web Admin engineering skeleton

The only Phase 1 route is `/contract-status`. It proves that the Web shell can
consume health, JobState, and Provider capability examples through a stable API
adapter. Formal A00–A12 administration pages remain out of scope.

From the repository root:

```powershell
corepack pnpm@10.34.5 install --frozen-lockfile
corepack pnpm@10.34.5 web:lint
corepack pnpm@10.34.5 web:typecheck
corepack pnpm@10.34.5 web:test
corepack pnpm@10.34.5 web:build
corepack pnpm@10.34.5 --filter @clothes-model/web-admin check:bundle
corepack pnpm@10.34.5 web:test:e2e
```

The Vite development proxy injects mock-only placeholder authentication while
talking to Prism. No token or mock credential is read by application source or
included in the production bundle. `VITE_API_BASE_URL` is optional; same-origin
is the default.
