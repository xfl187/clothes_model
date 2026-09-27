"""Immutable Workflow version and validation entities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

WorkflowState = Literal["draft", "active", "retired"]


@dataclass(frozen=True, slots=True)
class WorkflowVersion:
    id: str
    workflow_id: str
    version: int
    mode: str
    display_name: str
    state: WorkflowState
    workflow_sha256: str
    workflow_path: str
    manifest_sha256: str
    manifest_path: str
    bindings_schema_version: str
    manifest_json: str
    capabilities_json: str
    created_at: datetime
    validation_json: str | None = None
    validated_at: datetime | None = None
    activated_at: datetime | None = None
    retired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowValidationRun:
    id: str
    workflow_version_id: str
    status: str
    result_json: str
    checked_node_fingerprint: str | None
    created_at: datetime

