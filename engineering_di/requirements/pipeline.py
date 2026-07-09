"""JSON-to-requirement intelligence pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering_di.requirements.dataframe_builder import document_to_dataframe, iter_logical_rows
from engineering_di.requirements.embedding import attach_embedding_text
from engineering_di.requirements.json_reader import read_document_json
from engineering_di.requirements.models import Requirement, Section
from engineering_di.requirements.normalizer import NormalizationEngine
from engineering_di.requirements.requirement_builder import build_requirements
from engineering_di.requirements.section_detector import detect_sections

@dataclass(frozen=True, slots=True)
class RequirementPipelineResult:
    source_json: str
    sections: list[Section]
    requirements: list[Requirement]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_json": self.source_json,
            "sections": [section.to_dict() for section in self.sections],
            "requirements": [requirement.to_dict() for requirement in self.requirements],
        }

class JSONRequirementPipeline:
    """Convert canonical JSON into sections, typed requirements, and embedding text."""
    def __init__(self, normalizer: NormalizationEngine | None = None) -> None:
        self.normalizer = normalizer or NormalizationEngine()

    def process_json(self, path: str | Path, equipment: str | None = None) -> RequirementPipelineResult:
        document = read_document_json(path)
        frame = document_to_dataframe(document)
        rows = iter_logical_rows(frame)
        sections = list(detect_sections(rows).values())
        requirements = build_requirements(rows)
        normalized = self.normalizer.normalize(requirements)
        embedded = attach_embedding_text(normalized, equipment=equipment)
        return RequirementPipelineResult(source_json=str(path), sections=sections, requirements=embedded)
