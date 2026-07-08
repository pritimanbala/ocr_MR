"""Microsoft Table Transformer adapter contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engineering_di.config import TableModelConfig
from engineering_di.models import LayoutRegion, Table


class TableStructureDetector(ABC):
    """Detect table regions, rows, columns, and spanning cells."""

    @abstractmethod
    def detect(self, regions: list[LayoutRegion]) -> list[Table]:
        raise NotImplementedError


class UnconfiguredTableStructureDetector(TableStructureDetector):
    """No-op detector used when Phase 3 is disabled."""

    def __init__(self, config: TableModelConfig) -> None:
        self.config = config

    def detect(self, regions: list[LayoutRegion]) -> list[Table]:
        return []


class TableTransformerDetector(TableStructureDetector):
    """Adapter boundary for Microsoft Table Transformer models."""

    def __init__(self, config: TableModelConfig) -> None:
        self.config = config

    def detect(self, regions: list[LayoutRegion]) -> list[Table]:
        raise NotImplementedError("TATR inference wiring belongs in Phase 3.")
