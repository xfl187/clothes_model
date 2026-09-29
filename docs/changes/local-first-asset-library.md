# Proposed Change — Local-first Asset Library

status: merged  
updated: 2026-09-29  
merged: 2026-09-29  
merged_into: docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md  
affected_sections: 1, 4.1, 4.3-4.5, 5.1, 9-11, 16-18, docs/product-flow.md  
next_action: Run an Android UI/UX pass for local, offline, synchronization, migration, deletion-protection, and storage states before implementation planning.

## Goal

Let the user browse and select person and garment material while the fixed Backend is offline, without implying that generation can run without the Backend.

## Current Behavior

- The user imports from the Android system photo picker.
- A selected local file is retained only while its upload is incomplete, so upload can resume after interruption or App restart.
- After upload succeeds, the fixed Backend's private asset and asset ID are authoritative and reusable.
- Android reads the reusable asset library, thumbnails, availability, references, and deletion state from the Backend.
- Job creation submits Backend asset IDs; generation, history, and outputs require the Backend.

## Proposed Behavior

The confirmed brainstorming direction is a device-first library for imported person and garment originals:

- Importing creates a reusable local material immediately, including category/source metadata and a locally available preview. Until Backend upload and validation completes, server-side quality status is shown as not yet checked rather than guessed locally.
- Android retains its own full private copy of the imported original; the system picker URI is not the long-term source of truth.
- The user can browse, filter, and select locally available materials while the Backend is offline.
- Offline selections can be saved in a try-on draft, but generation remains unavailable until the Backend reconnects.
- When the user starts generation, Android uploads any selected material that does not yet have a usable Backend asset, then creates the job with Backend asset IDs.
- Successful upload records the local-to-Backend relationship so unchanged content is not uploaded again unnecessarily.
- A successful upload does not discard the local original. The Backend asset is a reusable uploaded copy, not the authoritative home of the imported material.
- Deleting an otherwise unreferenced device material deletes only the local material. It never silently deletes a Backend copy or rewrites task history. A material still selected by a saved draft or required by a retained layered-outfit session must first be removed, replaced, or have that reference deleted under the existing protected-deletion rules.
- The Backend keeps logical asset metadata and historical references even when the uploaded input image binary is cleaned. Uploaded person and garment input binaries become automatically cleanable after every job that references them reaches a terminal state. Cleanup never deletes generated outputs, task metadata, lineage, or the logical asset record.
- Cleanup starts after a fixed 24-hour grace period measured from the final referencing job entering a terminal state. A new active reference before expiry cancels and later restarts the countdown.
- If cleanup removes a Backend input binary, its local-to-Backend relationship becomes unsynced; using the still-present local material again uploads and reattaches a usable binary before creating the next job, without inventing a duplicate logical library item.
- A Backend copy referenced by any `queued`, `waiting_provider`, `preparing`, `running`, or `needs_attention` job is never cleaned.
- On the first authenticated connection after upgrade, Android automatically downloads every currently accessible server-only person and garment original into its private device library.
- A migrated server asset is not eligible for automatic cleanup until Android confirms that its full local copy is durable. An unreferenced migrated copy then receives the same 24-hour grace period.
- Migration reads only assets visible to the current authenticated owner scope. Current V1 uses one implicit owner; future account support must partition both Backend assets and Android local records by server identity plus owner identity, without exposing one owner's materials to another.
- This change reserves the ownership boundary but does not add accounts, account switching, cloud backup, or cross-device synchronization now.
- Backend task history and generated outputs remain authoritative server data; this change does not introduce on-device inference.

This behavior passed incremental product-spec review and has been merged into the authoritative Product Spec.

## User Flow

```text
Import from system picker
    -> Material becomes available in the device library
    -> Browse/filter/select online or offline
    -> Save try-on draft
    -> Backend available?
       -> No: keep draft and explain that generation requires reconnection
       -> Yes: upload unsynced selections, resolve Backend asset IDs, create job
    -> Continue through the existing task/result flow
```

## Affected Existing Behavior

- Person and garment library ownership and availability.
- Import recovery, upload progress, deduplication, and retry/cancel behavior.
- The three-step precise try-on draft and submit boundary.
- Local storage usage, App data removal, and photo-permission/URI availability.
- Deletion semantics between local material, Backend asset, and task references.
- Reauthentication and reconnect synchronization.
- Existing Backend job/history/reference protection remains authoritative once a job exists.

## Failure / Recovery

- Backend offline: local browse/select/draft remains available; upload and generation wait for reconnection.
- Upload interrupted: preserve the local material and draft; retry without choosing the source again when the device copy is still available.
- Local private copy missing or corrupt: show a local-missing state and allow replacement or removal from the draft; do not assume the original picker URI remains readable.
- Backend validation rejects an uploaded input: keep the local material and draft, record the validation result, and let the user replace the input or retry after correcting metadata. A warning-only quality result remains submittable under the existing quality policy.
- Backend copy unavailable: retain the local material and allow a fresh upload when it is not protected only by historical server references.
- Multiple jobs share an uploaded copy: defer automatic cleanup until the final active reference becomes terminal.
- Retry or mask correction during the 24-hour grace period: reuse the existing Backend copy and cancel its pending cleanup while the new job is active.
- Automatic cleanup completes: history retains parameters and lineage; the removed server input is represented as unavailable, while the same-device Android UI may still show its independent local material.
- Existing-asset migration is interrupted: keep completed local copies, resume remaining items later, and do not start cleanup for any item whose durable local copy is unconfirmed.
- Device storage is insufficient for migration: pause before deleting any Backend source, identify the affected items, and let the user free space or delete individual unwanted server-only materials through the existing protected-deletion rules.
- Authentication changes during migration: stop the migration and never continue downloading under a different owner scope.
- App uninstall or local data clearing removes device-only materials unless a later backup/export feature is explicitly added.

## Open Decisions

None identified during brainstorming.

## Product-spec Review Closure

- Review mode: incremental `CORE_FLOW` review.
- The device library, generation submission, task history, deletion/reference protection, migration, authentication recovery, and future ownership boundary form a closed flow.
- The Backend input image is treated separately from its logical asset record, so automatic binary cleanup does not destroy history or lineage.
- Existing protected references continue to prevent destructive local deletion where a draft or retained layered-outfit flow would otherwise become unusable.
- Future account isolation is a reserved ownership invariant only; V1 still has one implicit owner and no account UI.
- Blocking findings: 0.
- Unresolved important findings: 0.
