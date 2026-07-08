"""Recursive ZIP archive extraction and processing."""
from __future__ import annotations
import tempfile
import zipfile
from pathlib import Path
from engineering_di.models import Document
from engineering_di.parsers.dispatcher import SUPPORTED_EXTENSIONS

class ZipHandler:
    """Extract ZIP files into a temporary directory and recursively parse contents."""
    supported_extensions = frozenset({".zip"})
    parser_name = "zip"
    def __init__(self, dispatcher: object) -> None:
        self.dispatcher = dispatcher

    def parse(self, path: str | Path) -> list[Document]:
        archive = Path(path)
        if not archive.exists():
            raise FileNotFoundError(archive)
        if archive.suffix.lower() != ".zip":
            raise ValueError(f"Expected .zip archive: {archive}")
        documents: list[Document] = []
        with tempfile.TemporaryDirectory(prefix="engineering_di_zip_") as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(archive) as zf:
                for member in zf.infolist():
                    target = (root / member.filename).resolve()
                    if not str(target).startswith(str(root.resolve())):
                        raise ValueError(f"Unsafe ZIP member path: {member.filename}")
                zf.extractall(root)
            for child in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS):
                result = self.dispatcher.parse(child)  # type: ignore[attr-defined]
                if isinstance(result, list):
                    documents.extend(result)
                else:
                    documents.append(result)
        return documents
