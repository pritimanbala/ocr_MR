"""Semantic normalization boundary.

The LLM receives geometry-derived structures only. It must not invent table
structure or override cell/region relationships.
"""

from __future__ import annotations

from engineering_di.models import CellGraph, SemanticParameter


class SemanticNormalizer:
    """Normalize labels, units, operators, and mandatory flags."""

    def normalize(self, cell_graphs: list[CellGraph]) -> list[SemanticParameter]:
        return []
