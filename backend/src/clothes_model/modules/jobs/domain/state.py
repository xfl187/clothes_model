"""Centralized job item transition policy and aggregate calculation.

The Backend domain is the only owner of legal transitions. Clients issue commands
and render states; they never invent transitions or local state variants.
"""

from collections.abc import Iterable

from clothes_model.modules.jobs.domain.models import JobItemState, JobState

ACTIVE_ITEM_STATES: frozenset[JobItemState] = frozenset(
    {"queued", "waiting_provider", "preparing", "running"}
)
TERMINAL_ITEM_STATES: frozenset[JobItemState] = frozenset(
    {"succeeded", "failed", "cancelled"}
)

_TRANSITIONS: dict[JobItemState, frozenset[JobItemState]] = {
    "queued": frozenset({"waiting_provider", "preparing", "cancelled"}),
    "waiting_provider": frozenset({"preparing", "cancelled"}),
    "preparing": frozenset({"running", "cancelled", "needs_attention"}),
    "running": frozenset({"succeeded", "failed", "needs_attention", "cancelled"}),
    "needs_attention": frozenset({"running", "succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class IllegalJobTransition(RuntimeError):
    """A caller attempted a transition the domain policy forbids."""


def is_terminal(state: JobItemState) -> bool:
    return state in TERMINAL_ITEM_STATES


def can_transition(current: JobItemState, target: JobItemState) -> bool:
    return target in _TRANSITIONS[current]


def assert_transition(current: JobItemState, target: JobItemState) -> None:
    if not can_transition(current, target):
        raise IllegalJobTransition(f"illegal job item transition {current} -> {target}")


def backoff_seconds(transient_attempts: int, *, base: int = 5, cap: int = 3600) -> int:
    exponent = max(0, transient_attempts - 1)
    return min(cap, base * (2**exponent))


def aggregate_state(effective_items: Iterable[JobItemState]) -> JobState:
    """Derive the job aggregate from one effective attempt per candidate lineage.

    Active work dominates. Retained failures remain visible while a newer
    successful attempt supersedes them for the same candidate.
    """
    states = list(effective_items)
    if not states:
        return "queued"
    if any(state == "needs_attention" for state in states):
        return "needs_attention"

    active = [state for state in states if state in ACTIVE_ITEM_STATES]
    if active:
        if "running" in active:
            return "running"
        if "preparing" in active:
            return "preparing"
        if "waiting_provider" in active:
            return "waiting_provider"
        return "queued"

    succeeded = states.count("succeeded")
    cancelled = states.count("cancelled")
    failed = states.count("failed")
    total = len(states)

    if succeeded == total:
        return "succeeded"
    if succeeded > 0:
        return "partially_succeeded"
    if cancelled > 0:
        return "cancelled"
    if failed > 0:
        return "failed"
    return "failed"
