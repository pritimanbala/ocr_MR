#!/usr/bin/env python3
"""Convert parsed document JSON into typed requirement objects."""
from __future__ import annotations
import argparse, json, logging
from pathlib import Path
from typing import Iterable

from engineering_di.requirements import JSONRequirementPipeline, SentenceTransformerEmbeddingGenerator
from engineering_di.requirements.vector_store import QdrantRequirementStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert canonical document JSON files into normalized requirement objects.")
    parser.add_argument("input_path", type=Path, help="JSON file or folder containing JSON files from parse_documents.py.")
    parser.add_argument("-o", "--output", type=Path, default=Path("requirements_output"), help="Output directory for requirement JSON files.")
    parser.add_argument("--recursive", action="store_true", help="Recursively discover JSON files.")
    parser.add_argument("--equipment", default=None, help="Equipment name to include in generated embedding text, e.g. Pump.")
    parser.add_argument("--embed", action="store_true", help="Generate numeric embeddings with sentence-transformers.")
    parser.add_argument("--embedding-model", default="BAAI/bge-large-en-v1.5", help="sentence-transformers model name.")
    parser.add_argument("--qdrant-url", default=None, help="Optional Qdrant URL for vector upsert, e.g. http://localhost:6333.")
    parser.add_argument("--qdrant-collection", default="engineering_requirements", help="Qdrant collection name.")
    return parser


def discover_json(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".json" else []
    iterator: Iterable[Path] = path.rglob("*.json") if recursive else path.glob("*.json")
    return sorted(file for file in iterator if file.is_file())


def output_path_for(source: Path, root: Path, output_root: Path) -> Path:
    relative = source.relative_to(root) if root.is_dir() and source.is_relative_to(root) else Path(source.name)
    return (output_root / relative).with_suffix(".requirements.json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = args.input_path if args.input_path.is_dir() else args.input_path.parent
    files = discover_json(args.input_path, args.recursive)
    if not files:
        logging.error("No JSON files found in %s", args.input_path)
        return 1

    pipeline = JSONRequirementPipeline()
    embedder = SentenceTransformerEmbeddingGenerator(args.embedding_model) if args.embed else None
    vector_store = QdrantRequirementStore(args.qdrant_url, args.qdrant_collection) if args.qdrant_url else None

    for file in files:
        try:
            result = pipeline.process_json(file, equipment=args.equipment)
            payload = result.to_dict()
            if embedder:
                embeddings = embedder.encode_requirements(result.requirements)
                payload["embeddings"] = {requirement.id: embedding for requirement, embedding in zip(result.requirements, embeddings, strict=True)}
                if vector_store:
                    vector_store.upsert(result.requirements, embeddings)
            output_file = output_path_for(file, root, args.output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            logging.info("processed=%s requirements=%d output=%s", file, len(result.requirements), output_file)
        except Exception as exc:
            logging.exception("failed=%s error=%s", file, exc)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
