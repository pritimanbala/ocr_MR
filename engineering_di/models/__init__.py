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

    def intersects(self, other: "BoundingBox") -> bool:
        return self.x0 < other.x1 and self.x1 > other.x0 and self.y0 < other.y1 and self.y1 > other.y0

    def intersection(self, other: "BoundingBox") -> "BoundingBox | None":
        if not self.intersects(other):
            return None
        return BoundingBox(max(self.x0, other.x0), max(self.y0, other.y0), min(self.x1, other.x1), min(self.y1, other.y1))

    def intersection_area(self, other: "BoundingBox") -> float:
        intersection = self.intersection(other)
        return intersection.area if intersection else 0.0

    def contains_point(self, x: float, y: float, tolerance: float = 0.0) -> bool:
        return self.x0 - tolerance <= x <= self.x1 + tolerance and self.y0 - tolerance <= y <= self.y1 + tolerance

    def contains_box(self, other: "BoundingBox", tolerance: float = 0.0) -> bool:
        return (
            self.x0 - tolerance <= other.x0
            and self.y0 - tolerance <= other.y0
            and self.x1 + tolerance >= other.x1
            and self.y1 + tolerance >= other.y1
        )

    def expand(self, amount: float) -> "BoundingBox":
        return BoundingBox(self.x0 - amount, self.y0 - amount, self.x1 + amount, self.y1 + amount)

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
class Polygon:
    """Closed or polygon-like vector path extracted from drawing commands."""

    id: str
    bbox: BoundingBox
    page_number: int
    points: list[tuple[float, float]]
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
    polygon_ids: list[str] = field(default_factory=list)
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


LayoutRegionType = Literal["title", "table", "text", "footer", "header", "form", "figure", "unknown"]


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    """Detected structural page region from a layout model or rule engine."""

    id: str
    bbox: BoundingBox
    page_number: int
    region_type: LayoutRegionType
    confidence: float
    detector: str


@dataclass(frozen=True, slots=True)
class TableCell:
    """Geometry-first table cell reconstructed before semantic extraction."""

    id: str
    bbox: BoundingBox
    page_number: int
    row: int
    column: int
    row_span: int = 1
    col_span: int = 1
    token_ids: list[str] = field(default_factory=list)
    text: str = ""
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class Table:
    """Independent table or form grid with reconstructed cells."""

    id: str
    bbox: BoundingBox
    page_number: int
    cell_ids: list[str] = field(default_factory=list)
    source: Literal["geometry", "tatr", "hybrid"] = "geometry"
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class CellGraph:
    """Graph relationships between cells in a table."""

    table_id: str
    page_number: int
    cells: list[TableCell] = field(default_factory=list)
    horizontal_edges: list[tuple[str, str]] = field(default_factory=list)
    vertical_edges: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FormField:
    """Geometry-preserved form field candidate."""

    id: str
    bbox: BoundingBox
    page_number: int
    label_token_ids: list[str] = field(default_factory=list)
    value_token_ids: list[str] = field(default_factory=list)
    field_type: Literal["key_value", "checkbox", "radio", "unknown"] = "unknown"
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class SemanticParameter:
    """Canonical normalized parameter emitted after geometry is complete."""

    parameter: str
    value: Any
    section: str | None = None
    unit: str | None = None
    operator: str | None = None
    mandatory: bool | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


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
    polygons: list[Polygon] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    layout_regions: list[LayoutRegion] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    cells: list[TableCell] = field(default_factory=list)
    forms: list[FormField] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Document:
    """Parsed PDF document object model."""

    source_path: str
    page_count: int
    metadata: dict[str, Any]
    pages: list[Page]
    cell_graphs: list[CellGraph] = field(default_factory=list)
    semantic_parameters: list[SemanticParameter] = field(default_factory=list)
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
