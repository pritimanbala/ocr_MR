"""PDF parser adapter preserving the existing PyMuPDF implementation."""
from __future__ import annotations
from pathlib import Path
from engineering_di.models import Document
from engineering_di.pdf_parser import PyMuPDFDocumentParser
from engineering_di.parsers.base_parser import BaseParser

class PDFParser(BaseParser):
    supported_extensions = frozenset({".pdf"})
    parser_name = "pymupdf"

    def __init__(self, line_axis_tolerance: float = 1.0) -> None:
        self._parser = PyMuPDFDocumentParser(line_axis_tolerance=line_axis_tolerance)

    def parse(self, path: str | Path) -> Document:
        return self._parser.parse(self.validate_path(path))
