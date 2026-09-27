"""Provider capability description shared by adapters and the config service."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

CAPABILITY_SOURCE = ("adapter", "workflow_declared", "derived", "unknown")
CAPABILITY_VERIFICATION = ("verified", "declared", "unavailable", "unknown")

ParameterMap = Mapping[str, object]


def _mapping(value: object) -> ParameterMap:
    if isinstance(value, dict):
        return cast(ParameterMap, value)
    return {}


def _strings(value: object) -> tuple[str, ...]:
    raw = _mapping(value).get("values")
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item) for item in cast(Sequence[object], raw))


def _int(value: object, default: int) -> int:
    return value if isinstance(value, bool) is False and isinstance(value, int) else default


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    garment_categories: tuple[str, ...] = ("upper_body", "lower_body", "dress")
    manual_mask: bool = False
    multiple_candidates: bool = False
    multi_person_reference: bool = False
    batch_input: bool = False
    interrupt_running: bool = False
    sequential_layering: bool = False
    supported_layer_roles: tuple[str, ...] = ()
    preserve_existing_garments: bool = False
    outfit_context: bool = False
    region_mask: bool = False
    content_types: tuple[str, ...] = ("image/jpeg", "image/png")
    max_size_bytes: int = 20_971_520
    max_candidates: int = 4
    max_width: int | None = 4096
    max_height: int | None = 4096
    source: str = "adapter"
    verification: str = "declared"

    def _flag(self, supported: bool) -> dict[str, object]:
        return {
            "supported": supported,
            "source": self.source,
            "verification": self.verification,
        }

    def _values(self, values: tuple[str, ...]) -> dict[str, object]:
        return {
            "values": list(values),
            "source": self.source,
            "verification": self.verification,
        }

    def to_payload(self) -> dict[str, object]:
        input_constraints: dict[str, object] = {
            "content_types": list(self.content_types),
            "max_size_bytes": self.max_size_bytes,
        }
        if self.max_width is not None:
            input_constraints["max_width"] = self.max_width
        if self.max_height is not None:
            input_constraints["max_height"] = self.max_height
        return {
            "schema_version": 1,
            "garment_categories": self._values(self.garment_categories),
            "manual_mask": self._flag(self.manual_mask),
            "multiple_candidates": self._flag(self.multiple_candidates),
            "multi_person_reference": self._flag(self.multi_person_reference),
            "batch_input": self._flag(self.batch_input),
            "interrupt_running": self._flag(self.interrupt_running),
            "sequential_layering": self._flag(self.sequential_layering),
            "supported_layer_roles": self._values(self.supported_layer_roles),
            "preserve_existing_garments": self._flag(self.preserve_existing_garments),
            "outfit_context": self._flag(self.outfit_context),
            "region_mask": self._flag(self.region_mask),
            "input_constraints": input_constraints,
            "output_constraints": {"max_candidates": self.max_candidates},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_payload(cls, payload: ParameterMap) -> ProviderCapabilities:
        def supported(key: str) -> bool:
            return bool(_mapping(payload.get(key)).get("supported"))

        constraints = _mapping(payload.get("input_constraints"))
        output = _mapping(payload.get("output_constraints"))
        categories = _mapping(payload.get("garment_categories"))
        roles = _mapping(payload.get("supported_layer_roles"))
        width = constraints.get("max_width")
        height = constraints.get("max_height")
        return cls(
            garment_categories=_strings(categories),
            manual_mask=supported("manual_mask"),
            multiple_candidates=supported("multiple_candidates"),
            multi_person_reference=supported("multi_person_reference"),
            batch_input=supported("batch_input"),
            interrupt_running=supported("interrupt_running"),
            sequential_layering=supported("sequential_layering"),
            supported_layer_roles=_strings(roles),
            preserve_existing_garments=supported("preserve_existing_garments"),
            outfit_context=supported("outfit_context"),
            region_mask=supported("region_mask"),
            content_types=_strings(constraints) or ("image/jpeg", "image/png"),
            max_size_bytes=_int(constraints.get("max_size_bytes"), 20_971_520),
            max_candidates=_int(output.get("max_candidates"), 4),
            max_width=_int(width, 4096) if width is not None else None,
            max_height=_int(height, 4096) if height is not None else None,
            source=str(categories.get("source", "adapter")),
            verification=str(categories.get("verification", "declared")),
        )

    @classmethod
    def from_json(cls, raw: str) -> ProviderCapabilities:
        decoded: object = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("capability payload must be an object")
        return cls.from_payload(cast(ParameterMap, decoded))
