import pytest

from clothes_model.modules.jobs.domain import (
    IllegalJobTransition,
    aggregate_state,
    assert_transition,
    backoff_seconds,
    can_transition,
    is_terminal,
)
from clothes_model.modules.jobs.domain.models import JobItemState

ALL_STATES: tuple[JobItemState, ...] = (
    "queued",
    "waiting_provider",
    "preparing",
    "running",
    "needs_attention",
    "succeeded",
    "failed",
    "cancelled",
)

ALLOWED: set[tuple[JobItemState, JobItemState]] = {
    ("queued", "waiting_provider"),
    ("queued", "preparing"),
    ("queued", "cancelled"),
    ("waiting_provider", "preparing"),
    ("waiting_provider", "cancelled"),
    ("preparing", "running"),
    ("preparing", "cancelled"),
    ("preparing", "needs_attention"),
    ("running", "succeeded"),
    ("running", "failed"),
    ("running", "needs_attention"),
    ("running", "cancelled"),
    ("needs_attention", "running"),
    ("needs_attention", "succeeded"),
    ("needs_attention", "failed"),
    ("needs_attention", "cancelled"),
}


def test_every_transition_edge_is_classified() -> None:
    for current in ALL_STATES:
        for target in ALL_STATES:
            assert can_transition(current, target) is ((current, target) in ALLOWED)
    for terminal in ("succeeded", "failed", "cancelled"):
        assert is_terminal(terminal)
        assert not can_transition(terminal, "queued")


def test_illegal_transition_is_rejected_not_repaired() -> None:
    with pytest.raises(IllegalJobTransition):
        assert_transition("queued", "running")
    assert_transition("queued", "preparing")


def test_backoff_is_bounded_and_persisted_friendly() -> None:
    assert backoff_seconds(1, base=5, cap=3600) == 5
    assert backoff_seconds(2, base=5, cap=3600) == 10
    assert backoff_seconds(3, base=5, cap=3600) == 20
    assert backoff_seconds(50, base=5, cap=3600) == 3600


def test_aggregate_active_dominates_and_partial_success() -> None:
    assert aggregate_state(["queued"]) == "queued"
    assert aggregate_state(["waiting_provider", "succeeded"]) == "waiting_provider"
    assert aggregate_state(["running", "waiting_provider"]) == "running"
    assert aggregate_state(["queued", "needs_attention"]) == "needs_attention"
    assert aggregate_state([]) == "queued"


def test_aggregate_terminal_states() -> None:
    assert aggregate_state(["succeeded", "succeeded"]) == "succeeded"
    assert aggregate_state(["succeeded", "failed"]) == "partially_succeeded"
    assert aggregate_state(["succeeded", "cancelled"]) == "partially_succeeded"
    assert aggregate_state(["failed", "failed"]) == "failed"
    assert aggregate_state(["cancelled", "cancelled"]) == "cancelled"
    assert aggregate_state(["failed", "cancelled"]) == "cancelled"
