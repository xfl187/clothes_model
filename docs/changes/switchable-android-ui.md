# Switchable Android UI Presentations

status: draft
updated: 2026-10-07
next_action: Deferred by owner until Phase 7-8 are executed. Resume review by resolving the permitted presentation difference (recommended option 2), the appearance-settings entry point (recommended: inside S23 connection settings), and the unsaved-work-on-switch rule (recommended: block switch while the mask editor is open).

## Goal

Allow the owner to compare and keep multiple Android visual presentations without changing the
Backend or risking loss of tasks, assets, drafts, history, or recovery behavior when one visual
direction proves unsatisfactory.

## Current Behavior

Android has one confirmed `Quiet Atelier` visual direction and one Compose presentation for the V1
flows. Product behavior, task state, assets, drafts, connection state, and history are shared through
the existing Backend and Android data boundaries.

## Proposed Behavior

- Android offers an appearance choice containing two or more named UI presentations.
- Changing presentation changes visual composition, typography, color, shape, imagery treatment,
  navigation styling, and reusable visual components.
- Every presentation exposes the same confirmed product capabilities, destinations, state meanings,
  destructive-action consequences, accessibility requirements, and recovery actions.
- Backend endpoints, authentication, Provider behavior, jobs, assets, drafts, history, and persisted
  identifiers do not change when the presentation changes.
- The chosen presentation is device-local and takes effect without deleting or migrating product
  data. Active server jobs continue unaffected.
- A presentation that cannot render an existing state falls back to a shared safe state surface
  rather than hiding the state or changing its meaning.
- New product features are defined once and become available to every maintained presentation; a
  presentation may not silently omit a required feature.
- The existing presentation remains selectable while new presentations are evaluated.

## User Flow

```text
Open appearance settings
    ↓
Preview available presentations
    ↓
Select one presentation
    ↓
App redraws the current destination
    ↓
Continue using the same assets, draft, job, and history
```

## Affected Existing Behavior

- Android startup restores the last selected presentation before drawing the main navigation.
- Switching while a draft or active job exists must preserve the current destination and product
  state where feasible; otherwise it returns to the nearest shared destination with an explanation.
- Connection, offline, authentication-expired, deletion, job recovery, and Provider-unavailable
  states retain identical meaning and available recovery actions in every presentation.
- Accessibility and compact-phone support remain release requirements for every selectable
  presentation, not only the default one.
- Web Admin and the Backend are unaffected.

## Failure / Recovery

- If a saved presentation is unavailable after an update, Android selects the supported default and
  explains that the previous appearance is no longer available; product data is unchanged.
- Switching appearance never cancels a job, clears a draft, deletes an asset, logs out the user, or
  changes Provider selection.

## Open Decisions

- Confirm the permitted difference between presentations:
  1. theme packs only (same layout and components);
  2. visual presentation packs (different composition/components, shared flows and state semantics);
  3. independent experiences (navigation and flows may also differ).

The recommended scope is option 2. It provides meaningful alternatives without multiplying product
logic, test matrices, and behavioral inconsistencies like fully independent clients would.
