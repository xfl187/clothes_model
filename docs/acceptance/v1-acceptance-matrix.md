# V1 Acceptance Scenario Matrix

Maps Product Spec §18 acceptance scenarios 1–22 to evidence for the Phase 8 release gate.
V1.1 scenarios 23–43 are out of scope for V1.

Status legend: `automated` = deterministic test/script in this repository; `operator` = scripted manual
run against a real deployment; `deferred` = requires the real Comfy node/Workflow or a credentialed
Provider (documented release prerequisite).

| # | Scenario | Owner | Evidence | Status |
|---|---|---|---|---|
| 1 | LLM generate and save result | Backend/Android | `test_jobs_http.py`, `test_provider_config_http.py`; credentialed Ark smoke (`scripts/credentialed_seedream_smoke.py`) | automated + operator |
| 2 | Switch same assets to ComfyUI, record correct Provider/Workflow | Backend | `test_job_workflow_locking.py`, `test_scheduler_execution.py` | automated + operator |
| 3 | AutoDL off: submit then cancel never runs after recovery | Backend | `test_scheduler_recovery.py::test_offline_node_waits_then_resumes_and_cancelled_never_runs`, `test_fault_recovery.py::test_cancelled_item_is_never_reconciled_or_published` | automated |
| 4 | AutoDL off: submit then auto-resume after recovery | Backend | `test_scheduler_recovery.py` (offline resume) | automated |
| 5 | Two candidates, one fails: keep success and retry failed | Backend | `test_job_commands.py`, `test_jobs_http.py` | automated |
| 6 | Mask correction creates a traceable related new job | Backend/Android | `test_jobs_http.py` (mask correction), `MaskEditorScreenTest.kt` | automated |
| 7 | Other-person garment shows experimental hint and continues | Android | `CreateWizardScreenTest.kt` | automated |
| 8 | Active job progress/stage/elapsed; stale-network retention; no fake percent | Android | Phase 6 post-exit JobDetail Compose tests | automated |
| 8b | Admin changes Comfy address without restart or App update | Backend/Web | `test_comfy_node_http.py`, `ComfyNodePage` | automated + operator |
| 9 | Publish/validate Workflow; new jobs use new version, old history old | Backend | `test_workflow_lifecycle.py`, `test_workflow_artifacts.py` | automated |
| 10 | App Token cannot open admin; rotation invalidates old token | Backend | `test_auth_http.py`, `test_app_credential_http.py`, `test_security_boundary.py` | automated |
| 11 | Upload fail/app interrupt retains local; cancel cleans temp | Backend/Android | `test_upload_asset_http.py`, `PendingImportMigrationTest.kt` | automated |
| 12 | Restart unknown external → `needs_attention`; retry creates new item | Backend | `test_scheduler_recovery.py`, `test_job_commands.py`, `test_fault_recovery.py::test_unknown_external_state_never_resubmits` | automated |
| 13 | Config change during wait uses locked version; locked unavailable → `needs_attention` | Backend | `test_job_workflow_locking.py` | automated |
| 14 | Partial retry creates new child; mask correction new parent | Backend | `test_job_commands.py`, `test_jobs_http.py` | automated |
| 15 | Active reference blocks delete; terminal delete keeps placeholder | Backend | `test_asset_lifecycle_http.py`, `test_local_first_library.py` | automated |
| 16 | Token invalid → re-auth; server tasks continue | Backend/Android | `test_auth_http.py`; Android re-auth routing tests | automated |
| 17 | Waiting Comfy task migrates node with locked Workflow + compat check | Backend | `test_scheduler_recovery.py`, `test_job_workflow_locking.py` | automated |
| 18 | Storage full rejects new; blocked `queued`; resume after cleanup | Backend | `test_fault_recovery.py::test_job_creation_blocked_when_storage_capacity_exhausted`, `test_scheduler_recovery.py`, `test_upload_asset_http.py::test_capacity_guard_returns_507` | automated |
| 19 | Comfy offline → `waiting_provider`; missing/incompatible config blocks | Backend | `test_jobs_http.py::test_offline_provider_creates_waiting_job`, `test_job_workflow_locking.py` | automated |
| 20 | Cancel one candidate; whole-task cancel aggregate | Backend | `test_job_commands.py` | automated |
| 21 | Manual-mask correction via compatible Provider; env has one | Backend/Operator | `test_jobs_http.py::test_mask_job_requires_provider_capability` | automated + operator |
| 22 | `waiting_provider` never expires; resume or cancel | Backend | `test_scheduler_recovery.py` | automated |

## Deferred release prerequisites

- Real credentialed AutoDL/Comfy acceptance: configure a real node, validate/activate a real immutable
  Workflow, run and persist one output, prove restart and compatible-node recovery. Procedure:
  [node replacement](../runbooks/node-replacement.md) and
  [workflow publish and rollback](../runbooks/workflow-publish-rollback.md).
- The acceptance environment must contain at least one Provider advertisement with `manual_mask`
  support (scenario 21).
