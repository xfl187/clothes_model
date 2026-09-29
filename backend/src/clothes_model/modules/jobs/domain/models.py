"""Durable job, candidate-item, output, and event entities for Phase 3."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

JobState = Literal[
    "queued",
    "waiting_provider",
    "preparing",
    "running",
    "needs_attention",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
]
JobItemState = Literal[
    "queued",
    "waiting_provider",
    "preparing",
    "running",
    "needs_attention",
    "succeeded",
    "failed",
    "cancelled",
]
JobBlockReason = Literal[
    "provider_offline",
    "storage_capacity",
    "retry_backoff",
    "locked_configuration_unavailable",
    "external_state_unknown",
    "configuration_invalid",
    "unknown",
]
TryOnMode = Literal["precise_try_on", "unknown"]

TERMINAL_JOB_ITEM_STATES: frozenset[JobItemState] = frozenset(
    {"succeeded", "failed", "cancelled"}
)


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    mode: TryOnMode
    state: JobState
    candidate_count: int
    garment_asset_id: str
    provider_id: str
    provider_revision_id: str
    provider_snapshot_json: str
    created_at: datetime
    updated_at: datetime
    owner_scope_id: str | None = None
    block_reason: JobBlockReason | None = None
    blocked_detail: str | None = None
    seed: int | None = None
    advanced_parameters_json: str = "{}"
    mask_asset_id: str | None = None
    related_job_id: str | None = None
    workflow_version_id: str | None = None
    workflow_snapshot_json: str | None = None
    next_attempt_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class JobPersonInput:
    job_id: str
    person_asset_id: str
    ordinal: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobItem:
    id: str
    job_id: str
    person_asset_id: str
    candidate_index: int
    attempt: int
    state: JobItemState
    created_at: datetime
    updated_at: datetime
    block_reason: JobBlockReason | None = None
    retry_of_job_item_id: str | None = None
    superseded_by_job_item_id: str | None = None
    external_execution_id: str | None = None
    error_code: str | None = None
    error_json: str | None = None
    next_attempt_at: datetime | None = None
    transient_attempts: int = 0
    claimant_token: str | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GeneratedOutputRecord:
    id: str
    job_item_id: str
    asset_id: str
    favorite: bool
    created_at: datetime
    seed: int | None = None
    actual_parameters_json: str = "{}"
    quality_warnings_json: str = "[]"


@dataclass(frozen=True, slots=True)
class JobExecutionEvent:
    id: str
    job_id: str
    event_type: str
    occurred_at: datetime
    job_item_id: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    error_code: str | None = None
    detail_json: str = "{}"
