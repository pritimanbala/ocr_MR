"""Engineering document intelligence foundation package.

Phase 1 exposes a geometry-preserving PDF parser and document object model. The
pipeline also defines stable boundaries for layout detection, table structure
models, geometry reconstruction, form reconstruction, and semantic normalization.
"""

from engineering_di.config import GeometryConfig, PipelineConfig
from engineering_di.geometry import GeometryEngine
from engineering_di.models import (
    BoundingBox,
    CellGraph,
    Document,
    Drawing,
    FormField,
    Image,
    LayoutRegion,
    Page,
    Polygon,
    Rectangle,
    SemanticParameter,
    Table,
    TableCell,
    TextBlock,
    TextSpan,
    Token,
    VectorLine,
    Word,
)
from engineering_di.pipeline import EngineeringDocumentPipeline
from engineering_di.pdf_parser import PyMuPDFDocumentParser, parse_pdf

__all__ = [
    "BoundingBox",
    "CellGraph",
    "Document",
    "Drawing",
    "EngineeringDocumentPipeline",
    "FormField",
    "GeometryConfig",
    "GeometryEngine",
    "Image",
    "LayoutRegion",
    "Page",
    "PipelineConfig",
    "Polygon",
    "PyMuPDFDocumentParser",
    "Rectangle",
    "SemanticParameter",
    "Table",
    "TableCell",
    "TextBlock",
    "TextSpan",
    "Token",
    "VectorLine",
    "Word",
    "parse_pdf",
]
