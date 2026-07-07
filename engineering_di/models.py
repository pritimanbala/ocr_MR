"""Strongly typed document object model for engineering PDFs.

The classes in this module intentionally preserve low-level geometry rather than
performing semantic interpretation. Later phases can build layout graphs, table
models, form fields, and normalized parameters from this stable representation.
Coordinates are stored in PDF page coordinate space as reported by PyMuPDF:
origin at the top-left of the page, x increasing to the right, y increasing
downward, and units in PDF points.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned rectangular geometry in page coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict[str, float]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class Token:
    """Smallest text-bearing object emitted by the parser.

    A token can be backed by a PyMuPDF span, word, or future OCR token. Keeping a
    generic token type lets later OCR fallback plug into the same layout graph.
    """

    id: str
    text: str
    bbox: BoundingBox
    page_number: int
    source: Literal["pymupdf_span", "pymupdf_word", "ocr"]
    confidence: float | None = None
    font: str | None = None
    font_size: float | None = None
    color: int | None = None
    flags: int | None = None
    line_id: str | None = None
    block_id: str | None = None


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Font-consistent text span from PyMuPDF's structured text output."""

    id: str
    text: str
    bbox: BoundingBox
    page_number: int
    block_id: str
    line_id: str
    font: str | None = None
    font_size: float | None = None
    color: int | None = None
    flags: int | None = None
    ascender: float | None = None
    descender: float | None = None
    origin: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class Word:
    """Word-level text geometry from ``page.get_text('words')``."""

    id: str
    text: str
    bbox: BoundingBox
    page_number: int
    block_number: int | None = None
    line_number: int | None = None
    word_number: int | None = None


@dataclass(frozen=True, slots=True)
class TextBlock:
    """A text block preserving PyMuPDF block, line, and span relationships."""

    id: str
    bbox: BoundingBox
    page_number: int
    block_number: int
    block_type: int | None = None
    text: str = ""
    line_ids: list[str] = field(default_factory=list)
    span_ids: list[str] = field(default_factory=list)
    word_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VectorLine:
    """Straight vector segment extracted from PDF drawing commands."""

    id: str
    bbox: BoundingBox
    page_number: int
    x0: float
    y0: float
    x1: float
    y1: float
    orientation: Literal["horizontal", "vertical", "diagonal"]
    stroke: tuple[float, ...] | None = None
    width: float | None = None
    drawing_id: str | None = None


@dataclass(frozen=True, slots=True)
class Rectangle:
    """Rectangle-like vector object, commonly table borders or form boxes."""

    id: str
    bbox: BoundingBox
    page_number: int
    stroke: tuple[float, ...] | None = None
    fill: tuple[float, ...] | None = None
    width: float | None = None
    drawing_id: str | None = None


@dataclass(frozen=True, slots=True)
class Drawing:
    """Raw vector drawing path with normalized metadata and primitive counts."""

    id: str
    bbox: BoundingBox
    page_number: int
    drawing_type: str | None = None
    stroke: tuple[float, ...] | None = None
    fill: tuple[float, ...] | None = None
    width: float | None = None
    is_closed: bool | None = None
    line_ids: list[str] = field(default_factory=list)
    rectangle_ids: list[str] = field(default_factory=list)
    curve_count: int = 0
    polygon_count: int = 0
    raw_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Image:
    """Embedded image occurrence on a PDF page."""

    id: str
    bbox: BoundingBox
    page_number: int
    xref: int
    width: int | None = None
    height: int | None = None
    bits_per_component: int | None = None
    colorspace: str | None = None
    name: str | None = None
    filter: str | None = None


@dataclass(frozen=True, slots=True)
class Page:
    """Complete geometry-preserving representation of one PDF page."""

    number: int
    bbox: BoundingBox
    rotation: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    text_spans: list[TextSpan] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)
    drawings: list[Drawing] = field(default_factory=list)
    vector_lines: list[VectorLine] = field(default_factory=list)
    rectangles: list[Rectangle] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Document:
    """Parsed PDF document object model."""

    source_path: str
    page_count: int
    metadata: dict[str, Any]
    pages: list[Page]
    parser: str = "pymupdf"
    schema_version: str = "phase1.document.v1"

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def to_jsonable(value: Any) -> Any:
    """Convert nested dataclasses and paths into JSON-serializable objects."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if is_dataclass(value):
        data = asdict(value)
        return {key: to_jsonable(item) for key, item in data.items()}
    return value
