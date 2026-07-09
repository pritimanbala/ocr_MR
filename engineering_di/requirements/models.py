"""Typed objects for engineering requirement intelligence."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ParameterType = Literal["numeric", "text", "material", "standard", "boolean", "note"]

@dataclass(frozen=True, slots=True)
class Section:
    name: str
    page: int | None = None
    row_index: int | None = None
    confidence: float = 1.0
    source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    section: str
    parameter: str
    value: str | int | float | bool | None
    unit: str | None = None
    page: int | None = None
    row_index: int | None = None
    parameter_type: ParameterType = "text"
    operator: str | None = None
    normalized_value: str | int | float | bool | None = None
    normalized_unit: str | None = None
    embedding_text: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class VendorStatement:
    section: str
    parameter: str
    value: str | int | float | bool | None
    page: int | None = None
    row_index: int | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
