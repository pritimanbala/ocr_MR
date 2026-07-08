"""Layout detector contracts.

DocLayout-YOLO should be the first structural signal when configured. This
module keeps model inference separate from the parser and geometry engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from engineering_di.config import LayoutModelConfig
from engineering_di.models import LayoutRegion, Page


class LayoutDetector(ABC):
    """Detect high-level regions such as tables, headers, forms, and figures."""

    @abstractmethod
    def detect(self, page: Page) -> list[LayoutRegion]:
        raise NotImplementedError


class UnconfiguredLayoutDetector(LayoutDetector):
    """Placeholder used until DocLayout-YOLO weights/runtime are configured."""

    def __init__(self, config: LayoutModelConfig) -> None:
        self.config = config

    def detect(self, page: Page) -> list[LayoutRegion]:
        return []


class DocLayoutYOLODetector(LayoutDetector):
    """Adapter boundary for DocLayout-YOLO.

    The concrete model package and weights are intentionally loaded lazily so
    installations that only need Phase 1 parsing do not import heavy ML stacks.
    """

    def __init__(self, config: LayoutModelConfig) -> None:
        if config.model_path is None:
            raise ValueError("DocLayout-YOLO requires LayoutModelConfig.model_path.")
        self.config = config

    def detect(self, page: Page) -> list[LayoutRegion]:
        raise NotImplementedError("DocLayout-YOLO inference wiring belongs in Phase 2.")
