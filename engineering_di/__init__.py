"""Engineering document intelligence foundation package.

Phase 1 exposes a geometry-preserving PDF parser and document object model.
Semantic extraction, table detection, form reconstruction, and LLM normalization
belong to later pipeline phases and are intentionally not performed here.
"""

from engineering_di.models import (
    BoundingBox,
    Document,
    Drawing,
    Image,
    Page,
    Rectangle,
    TextBlock,
    TextSpan,
    Token,
    VectorLine,
    Word,
)
from engineering_di.pdf_parser import PyMuPDFDocumentParser, parse_pdf

__all__ = [
    "BoundingBox",
    "Document",
    "Drawing",
    "Image",
    "Page",
    "PyMuPDFDocumentParser",
    "Rectangle",
    "TextBlock",
    "TextSpan",
    "Token",
    "VectorLine",
    "Word",
    "parse_pdf",
]
