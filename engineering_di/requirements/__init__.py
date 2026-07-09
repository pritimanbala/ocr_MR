"""Requirement intelligence pipeline exports."""
from engineering_di.requirements.embedding import SentenceTransformerEmbeddingGenerator, attach_embedding_text, generate_embedding_text
from engineering_di.requirements.models import Requirement, Section, VendorStatement
from engineering_di.requirements.normalizer import NormalizationEngine
from engineering_di.requirements.pipeline import JSONRequirementPipeline, RequirementPipelineResult
__all__ = [
    "Section",
    "Requirement",
    "VendorStatement",
    "NormalizationEngine",
    "JSONRequirementPipeline",
    "RequirementPipelineResult",
    "generate_embedding_text",
    "attach_embedding_text",
    "SentenceTransformerEmbeddingGenerator",
]
