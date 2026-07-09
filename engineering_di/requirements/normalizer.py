"""Normalize units, aliases, and values in requirement objects."""
from __future__ import annotations
from dataclasses import replace
from typing import Mapping
from engineering_di.requirements.models import Requirement

DEFAULT_ALIASES: dict[str, str] = {
    "SS316L": "316L",
    "SS 316L": "316L",
    "STAINLESS STEEL 316L": "316L",
    "DEG C": "degree_Celsius",
    "°C": "degree_Celsius",
}

class NormalizationEngine:
    def __init__(self, aliases: Mapping[str, str] | None = None) -> None:
        self.aliases = {**DEFAULT_ALIASES, **dict(aliases or {})}
        self._ureg = None

    def normalize(self, requirements: list[Requirement]) -> list[Requirement]:
        return [self.normalize_requirement(requirement) for requirement in requirements]

    def normalize_requirement(self, requirement: Requirement) -> Requirement:
        normalized_value = self._normalize_alias(requirement.value)
        normalized_unit = self._normalize_unit(requirement.unit)
        return replace(requirement, normalized_value=normalized_value, normalized_unit=normalized_unit)

    def _normalize_alias(self, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return self.aliases.get(normalized.upper(), normalized)

    def _normalize_unit(self, unit: str | None) -> str | None:
        if not unit:
            return None
        alias = self.aliases.get(unit.upper(), unit)
        try:
            if self._ureg is None:
                from pint import UnitRegistry
                self._ureg = UnitRegistry()
            return str(self._ureg.Unit(alias))
        except Exception:
            return alias
