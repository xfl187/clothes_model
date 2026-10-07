"""Domain models for V1.1 layered outfits."""

from dataclasses import dataclass
from datetime import datetime

TERMINAL_JOB_STATES = ("succeeded", "partially_succeeded", "failed", "cancelled")

SYSTEM_LAYER_ROLES = ("inner_top", "outerwear", "lower_body", "dress")
DEFAULT_LAYER_DEFINITION_VERSION = 1


@dataclass(frozen=True, slots=True)
class LayerTypeDefinition:
    id: str
    definition_version: int
    role: str
    body_region: str
    layer_order: int
    compatible_roles_json: str
    conflicting_roles_json: str
    required_capabilities_json: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutfitSession:
    id: str
    owner_scope_id: str | None
    name: str
    favorite: bool
    person_asset_id: str
    layer_definition_version: int
    main_branch_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutfitBranch:
    id: str
    session_id: str
    name: str
    route: str
    favorite: bool
    is_mainline: bool
    head_revision_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutfitRevision:
    id: str
    session_id: str
    branch_id: str
    base_revision_id: str | None
    parent_revision_id: str | None
    layers_json: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutfitLayer:
    id: str
    session_id: str
    branch_id: str
    role: str
    garment_asset_id: str
    layer_order: int
    state: str
    definition_version: int
    source_layer_id: str | None
    apply_job_id: str | None
    selected_output_id: str | None
    created_at: datetime
    updated_at: datetime
