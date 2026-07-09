"""Optional Qdrant vector storage for requirement embeddings."""
from __future__ import annotations
from engineering_di.requirements.models import Requirement

class QdrantRequirementStore:
    def __init__(self, url: str, collection: str = "engineering_requirements") -> None:
        from qdrant_client import QdrantClient
        self.client = QdrantClient(url=url)
        self.collection = collection

    def upsert(self, requirements: list[Requirement], embeddings: list[list[float]]) -> None:
        from qdrant_client.http.models import PointStruct
        points = [PointStruct(id=requirement.id, vector=embedding, payload=requirement.to_dict()) for requirement, embedding in zip(requirements, embeddings, strict=True)]
        self.client.upsert(collection_name=self.collection, points=points)
