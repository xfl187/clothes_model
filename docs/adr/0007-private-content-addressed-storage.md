# ADR-0007: Private local content-addressed storage

- Status: Accepted
- Date: 2026-09-26

## Context

V1 stores private person and garment images on one fixed server. Uploads must survive interruption and process restart, strip sensitive metadata, prevent public URL access, avoid duplicate immutable bytes, and preserve referenced history when content deletion is blocked. SQLite and the filesystem cannot participate in one atomic transaction, so their boundary needs explicit states and reconciliation.

The confirmed deployment does not require S3-compatible object storage, database blobs, a separate upload service, or distributed workers.

## Decision

### Storage ownership and layout

- Define a Backend-owned `FileStorage` port with a private local-disk adapter.
- Keep temporary upload content outside the immutable object namespace. Paths are derived only from server-generated identifiers; user filenames remain metadata and never become path components.
- Do not mount the storage root as static/public content. Authenticated API handlers stream private bytes with safe response headers and never disclose filesystem paths or internal object hashes.

### Normalization and object identity

- Accept the Phase 2 image formats declared by the API boundary, initially JPEG and PNG.
- Before durable placement, decode the image, enforce byte/pixel/dimension limits, normalize EXIF orientation, remove EXIF/GPS metadata, and serialize a normalized image.
- Compute SHA-256 over the normalized stored bytes. Use that digest internally as the immutable content-addressed object identity and deduplication key; it is not a public asset identifier or API version.
- Write to a confined temporary file, flush and fsync, then atomically rename into the immutable object path. A `stored_objects` database record owns metadata and durable reference accounting.

### Upload and reconciliation lifecycle

- Persist a confirmed upload offset only after corresponding bytes are flushed. Serialize writes per upload in the single Backend process.
- On restart, reconcile temporary bytes to the database-confirmed offset by truncating uncommitted trailing data.
- Upload completion validates declared size/checksum, normalizes content, places the immutable object, and creates the asset through an idempotent application workflow.
- Cancellation moves the upload to a terminal state before temporary deletion; repeated cancellation and cleanup are safe.
- A single in-process maintenance owner performs bounded expiry and reconciliation work under the V1 single-instance constraint.

### Assets, references, and deletion

- Asset IDs are independent from stored-object identity. Multiple assets may reference one immutable object.
- Future modules register and release asset references through an application port. Active references block private-content deletion and are inspectable through a paginated API resource.
- When deletion is allowed, remove the asset-to-content association and retain the required metadata placeholder. Delete physical bytes only after no durable content reference remains.
- Ambiguous database/file mismatches fail safely and are surfaced for diagnostics; reconciliation does not silently delete potentially durable data.

## Alternatives rejected

- Public upload/static directories: unguessable filenames are not authorization and would violate the authenticated-download requirement.
- Original-file passthrough: it retains EXIF/GPS data, inconsistent orientation, and attacker-controlled encoding details.
- Database BLOB storage: large streamed content would increase SQLite contention and backup coupling without providing cross-resource atomicity.
- Mutable per-asset files: they duplicate identical normalized bytes and make safe shared retention harder.
- Premature external object storage: V1 is a personal single-server deployment and does not need its operational/API complexity.
- Treating SQLite plus filesystem as one atomic transaction: this is not technically true; explicit states, immutable objects, idempotency, and reconciliation make failures recoverable instead.

## Consequences

- Backups must preserve SQLite, the private storage root, and the encryption master key as one deployment set.
- Normalization can make the stored checksum differ from the client checksum; the client checksum validates uploaded input, while the internal object hash identifies normalized bytes.
- Disk-capacity checks must reserve normalization and atomic-write overhead and may reject new writes before the filesystem is full.
- Filesystem behavior used by atomic rename and fsync must be verified on supported development and deployment filesystems.
- Moving to external object storage or multi-instance writers requires a later ADR and a replacement coordination model.
