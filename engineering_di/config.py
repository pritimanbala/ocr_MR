"""Configuration objects for the engineering document pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LayoutModelConfig:
    """DocLayout-YOLO adapter configuration."""

    model_path: Path | None = None
    confidence_threshold: float = 0.25
    image_size: int = 1024


@dataclass(frozen=True, slots=True)
class TableModelConfig:
    """Microsoft Table Transformer adapter configuration."""

    detection_model_name: str = "microsoft/table-transformer-detection"
    structure_model_name: str = "microsoft/table-transformer-structure-recognition"
    confidence_threshold: float = 0.5


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    """Tolerances used by the geometry engine."""

    axis_tolerance: float = 1.0
    merge_gap_tolerance: float = 2.0
    intersection_tolerance: float = 1.5
    cell_min_width: float = 4.0
    cell_min_height: float = 4.0
    token_overlap_threshold: float = 0.2


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Top-level pipeline switches and stage configuration."""

    layout: LayoutModelConfig = field(default_factory=LayoutModelConfig)
    tables: TableModelConfig = field(default_factory=TableModelConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    enable_layout_detection: bool = False
    enable_table_transformer: bool = False
    enable_semantic_normalization: bool = False
