"""Read canonical document JSON emitted by parse_documents.py."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def read_document_json(path: str | Path) -> dict[str, Any]:
    document_path = Path(path)
    if not document_path.exists():
        raise FileNotFoundError(document_path)
    with document_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {document_path}")
    return payload
