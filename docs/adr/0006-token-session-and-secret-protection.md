# ADR-0006: Token, browser session, and secret protection

- Status: Accepted
- Date: 2026-09-26

## Context

V1 has no user account or password system. The Android application connects with an App Token, while an operator uses a separate Admin Token to establish a browser session. These credentials must remain scope-isolated, revocable, and recoverable through the fixed-server operator boundary. Future provider credentials also require encryption at rest without leaking a master key into SQLite, source code, client bundles, or logs.

The deployment is intentionally a single Backend process with SQLite. The security model must be strong without introducing an identity provider, Redis session store, JWT infrastructure, or a separate secret service.

## Decision

### App and Admin tokens

- Generate tokens from cryptographically secure random bytes. The external value contains a non-secret public identifier plus a high-entropy secret.
- Store the public identifier, scope, lifecycle metadata, and an Argon2id encoded hash. Never store or log the full token.
- Select the candidate record by public identifier, then perform bounded Argon2id verification. Encoded parameters support verification and rehash-on-success after policy changes.
- App and Admin scopes are explicit and non-interchangeable. An App Token cannot access Admin resources, and an Admin browser session is not accepted as App bearer authentication.
- First-deploy tooling creates missing credentials and displays each full value once. Re-running bootstrap neither replaces active credentials nor redisplays their values.
- Admin Token loss is recovered through an operator-only command on the server. App Token rotation/revocation is a Backend application service; its Web management UI is implemented in its later roadmap phase.

### Admin browser session

- Admin Token login creates a new random opaque session identifier. Store only a SHA-256 or keyed digest of this random session value.
- Deliver the identifier in a bounded `Secure`, `HttpOnly`, `SameSite=Strict` cookie. Production refuses unsafe cookie configuration; localhost HTTP support is an explicit development-only policy.
- Each session has a separate random CSRF value whose digest is stored with the session. Session creation and inspection return the current CSRF value for memory-only Web use.
- State-changing Admin requests require both the session cookie and CSRF header and pass same-origin/Origin validation where the browser supplies it.
- Logout, expiry, explicit revocation, and the relevant Admin Token reset invalidate sessions.
- Failed Admin login throttling is persisted in SQLite so restart does not erase it. Throttle records contain safe network/key metadata only, never attempted token values.

### Secret encryption

- Load a 256-bit master key through the deployment secret-file boundary.
- Encrypt each value with AES-256-GCM using a fresh 96-bit nonce.
- Bind ciphertext to its purpose, record identifier, and envelope-format version with authenticated additional data.
- Persist a versioned envelope containing algorithm/version, nonce, and ciphertext only.
- Missing keys, wrong keys, malformed envelopes, unknown versions, nonce/ciphertext modification, or AAD mismatch fail closed.
- Security audit events contain action, actor/token identifiers, timestamps, result, and safe context only.

## Alternatives rejected

- Plaintext or reversibly encrypted App/Admin tokens: a database or encryption-key compromise would expose reusable credentials, and token verification does not require recovery of the original value.
- JWT browser sessions: V1 needs immediate logout/reset revocation and already has SQLite; signed self-contained sessions add key/claim complexity without removing server state.
- Admin secrets in localStorage or sessionStorage: browser script access unnecessarily broadens exposure. The session remains HttpOnly and CSRF state remains in memory.
- Slow hashing of random session identifiers: random high-entropy session values do not have the offline-guessing properties of human passwords; a digest plus short lifetime and revocation is sufficient and avoids avoidable CPU cost.
- Per-provider ad hoc encryption: a single versioned encryption boundary prevents incompatible formats and inconsistent AAD/key handling.
- Redis-backed sessions or rate limiting: the confirmed V1 runtime is single-instance and SQLite-backed; adding Redis would create an unjustified operational dependency.

## Consequences

- Operator bootstrap and recovery must be documented and tested as security-sensitive commands.
- Argon2id parameters must be benchmarked for the deployment class and concurrent verification must remain bounded.
- Web reload restores the cookie session through the session-inspection endpoint and receives a fresh memory-only CSRF value.
- Master-key preservation becomes part of deployment backup/restore. Losing it makes encrypted provider secrets unrecoverable by design.
- Horizontal scaling remains prohibited until a later ADR replaces the single-instance persistence and coordination assumptions.
