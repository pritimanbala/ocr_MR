"""Embedding text generation and optional sentence-transformers adapter."""
from __future__ import annotations
from dataclasses import replace
from engineering_di.requirements.models import Requirement


def generate_embedding_text(requirement: Requirement, equipment: str | None = None) -> str:
    subject = f"{equipment} " if equipment else ""
    value = requirement.normalized_value if requirement.normalized_value is not None else requirement.value
    unit = requirement.normalized_unit or requirement.unit or ""
    operator = requirement.operator or "is"
    if requirement.parameter_type == "numeric" and operator != "is":
        phrase = f"{subject}{requirement.parameter} shall be {operator} {value} {unit}".strip()
    elif requirement.parameter_type == "numeric":
        phrase = f"{subject}{requirement.parameter} shall be {value} {unit}".strip()
    else:
        phrase = f"{subject}{requirement.parameter} is {value}".strip()
    return f"Section {requirement.section}: {phrase}."


def attach_embedding_text(requirements: list[Requirement], equipment: str | None = None) -> list[Requirement]:
    return [replace(requirement, embedding_text=generate_embedding_text(requirement, equipment)) for requirement in requirements]

class SentenceTransformerEmbeddingGenerator:
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode_requirements(self, requirements: list[Requirement]) -> list[list[float]]:
        texts = [requirement.embedding_text or generate_embedding_text(requirement) for requirement in requirements]
        return self.model.encode(texts, normalize_embeddings=True).tolist()
