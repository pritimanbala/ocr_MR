"""Shared parser contracts for all document formats."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from engineering_di.models import Document

class BaseParser(ABC):
    """Abstract parser interface. Every parser returns the common Document model."""

    supported_extensions: frozenset[str] = frozenset()
    parser_name: str = "base"

    @abstractmethod
    def parse(self, path: str | Path) -> Document:
        """Parse *path* into a common Document object."""
        raise NotImplementedError

    def validate_path(self, path: str | Path) -> Path:
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Input file not found: {resolved}")
        if self.supported_extensions and resolved.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"{self.parser_name} does not support {resolved.suffix}: {resolved}")
        return resolved
