"""PyMuPDF-backed Phase 1 parser for engineering PDF geometry.

This module deliberately stops at document parsing. It does not detect tables,
associate labels and values, extract parameters, or call an LLM. Its job is to
produce a faithful object model that later pipeline phases can consume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

Point = tuple[float, float]


class PyMuPDFDocumentParser:
    """Parse PDFs into the Phase 1 document object model using PyMuPDF."""

    def __init__(self, line_axis_tolerance: float = 1.0) -> None:
        self.line_axis_tolerance = line_axis_tolerance

    def parse(self, pdf_path: str | Path) -> Document:
        fitz = self._import_pymupdf()
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, got: {path}")

        with fitz.open(path) as pdf:
            pages = [self._parse_page(page, page_index + 1) for page_index, page in enumerate(pdf)]
            return Document(
                source_path=str(path),
                page_count=pdf.page_count,
                metadata=dict(pdf.metadata or {}),
                pages=pages,
            )

    @staticmethod
    def _import_pymupdf() -> Any:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("Missing dependency 'PyMuPDF'. Install it with: python -m pip install -r requirements.txt") from exc
        return fitz

    def _parse_page(self, page: Any, page_number: int) -> Page:
        page_bbox = bbox_from_rect(page.rect)
        blocks, spans, words, tokens = self._extract_text(page, page_number)
        drawings, vector_lines, rectangles = self._extract_drawings(page, page_number)
        images = self._extract_images(page, page_number)
        return Page(
            number=page_number,
            bbox=page_bbox,
            rotation=int(page.rotation or 0),
            text_blocks=blocks,
            text_spans=spans,
            words=words,
            tokens=tokens,
            drawings=drawings,
            vector_lines=vector_lines,
            rectangles=rectangles,
            images=images,
        )

    def _extract_text(self, page: Any, page_number: int) -> tuple[list[TextBlock], list[TextSpan], list[Word], list[Token]]:
        text_dict = page.get_text("dict")
        blocks: list[TextBlock] = []
        spans: list[TextSpan] = []
        tokens: list[Token] = []

        for block_index, block in enumerate(text_dict.get("blocks", [])):
            if "bbox" not in block:
                continue
            block_id = f"p{page_number}.block{block_index}"
            span_ids: list[str] = []
            line_ids: list[str] = []
            block_text_parts: list[str] = []

            for line_index, line in enumerate(block.get("lines", [])):
                line_id = f"{block_id}.line{line_index}"
                line_ids.append(line_id)
                for span_index, span in enumerate(line.get("spans", [])):
                    text = span.get("text", "")
                    if not text:
                        continue
                    span_id = f"{line_id}.span{span_index}"
                    span_bbox = bbox_from_sequence(span["bbox"])
                    span_obj = TextSpan(
                        id=span_id,
                        text=text,
                        bbox=span_bbox,
                        page_number=page_number,
                        block_id=block_id,
                        line_id=line_id,
                        font=span.get("font"),
                        font_size=to_float_or_none(span.get("size")),
                        color=span.get("color"),
                        flags=span.get("flags"),
                        ascender=to_float_or_none(span.get("ascender")),
                        descender=to_float_or_none(span.get("descender")),
                        origin=point_from_sequence(span.get("origin")),
                    )
                    spans.append(span_obj)
                    span_ids.append(span_id)
                    block_text_parts.append(text)
                    tokens.append(
                        Token(
                            id=f"{span_id}.token",
                            text=text,
                            bbox=span_bbox,
                            page_number=page_number,
                            source="pymupdf_span",
                            font=span_obj.font,
                            font_size=span_obj.font_size,
                            color=span_obj.color,
                            flags=span_obj.flags,
                            line_id=line_id,
                            block_id=block_id,
                        )
                    )

            blocks.append(
                TextBlock(
                    id=block_id,
                    bbox=bbox_from_sequence(block["bbox"]),
                    page_number=page_number,
                    block_number=int(block.get("number", block_index)),
                    block_type=block.get("type"),
                    text="".join(block_text_parts),
                    line_ids=line_ids,
                    span_ids=span_ids,
                )
            )

        words = self._extract_words(page, page_number)
        word_ids_by_block: dict[int, list[str]] = {}
        for word in words:
            if word.block_number is not None:
                word_ids_by_block.setdefault(word.block_number, []).append(word.id)
            tokens.append(Token(id=f"{word.id}.token", text=word.text, bbox=word.bbox, page_number=page_number, source="pymupdf_word"))

        blocks = [
            TextBlock(
                id=block.id,
                bbox=block.bbox,
                page_number=block.page_number,
                block_number=block.block_number,
                block_type=block.block_type,
                text=block.text,
                line_ids=block.line_ids,
                span_ids=block.span_ids,
                word_ids=word_ids_by_block.get(block.block_number, []),
            )
            for block in blocks
        ]
        return blocks, spans, words, tokens

    @staticmethod
    def _extract_words(page: Any, page_number: int) -> list[Word]:
        words: list[Word] = []
        for index, item in enumerate(page.get_text("words")):
            # PyMuPDF word tuple: x0, y0, x1, y1, text, block_no, line_no, word_no.
            x0, y0, x1, y1, text, *rest = item
            block_no = int(rest[0]) if len(rest) > 0 else None
            line_no = int(rest[1]) if len(rest) > 1 else None
            word_no = int(rest[2]) if len(rest) > 2 else None
            words.append(
                Word(
                    id=f"p{page_number}.word{index}",
                    text=str(text),
                    bbox=BoundingBox(float(x0), float(y0), float(x1), float(y1)),
                    page_number=page_number,
                    block_number=block_no,
                    line_number=line_no,
                    word_number=word_no,
                )
            )
        return words

    def _extract_drawings(self, page: Any, page_number: int) -> tuple[list[Drawing], list[VectorLine], list[Rectangle]]:
        drawings: list[Drawing] = []
        vector_lines: list[VectorLine] = []
        rectangles: list[Rectangle] = []

        for drawing_index, drawing in enumerate(page.get_drawings()):
            drawing_id = f"p{page_number}.drawing{drawing_index}"
            line_ids: list[str] = []
            rectangle_ids: list[str] = []
            curve_count = 0
            polygon_count = 0
            raw_items: list[dict[str, Any]] = []

            for item_index, item in enumerate(drawing.get("items", [])):
                op = item[0]
                raw_items.append(normalize_drawing_item(item))
                if op == "l":
                    p0 = point_from_any(item[1])
                    p1 = point_from_any(item[2])
                    if p0 is None or p1 is None:
                        continue
                    line_id = f"{drawing_id}.line{len(line_ids)}"
                    line_ids.append(line_id)
                    vector_lines.append(self._build_vector_line(line_id, page_number, p0, p1, drawing, drawing_id))
                elif op == "re":
                    rect = bbox_from_rect(item[1])
                    rectangle_id = f"{drawing_id}.rect{len(rectangle_ids)}"
                    rectangle_ids.append(rectangle_id)
                    rectangles.append(self._build_rectangle(rectangle_id, page_number, rect, drawing, drawing_id))
                elif op in {"c", "qu"}:
                    curve_count += 1
                else:
                    # Move/close/fill/path operators are preserved in raw_items. If a
                    # path contains multiple line segments and is closed, later phases
                    # can interpret it as a polygon from raw_items.
                    polygon_count += 1 if drawing.get("closePath") else 0

            drawing_bbox = bbox_from_rect(drawing.get("rect")) if drawing.get("rect") is not None else bbox_from_items(raw_items)
            drawings.append(
                Drawing(
                    id=drawing_id,
                    bbox=drawing_bbox,
                    page_number=page_number,
                    drawing_type=drawing.get("type"),
                    stroke=tuple_or_none(drawing.get("color")),
                    fill=tuple_or_none(drawing.get("fill")),
                    width=to_float_or_none(drawing.get("width")),
                    is_closed=bool(drawing.get("closePath")) if drawing.get("closePath") is not None else None,
                    line_ids=line_ids,
                    rectangle_ids=rectangle_ids,
                    curve_count=curve_count,
                    polygon_count=polygon_count,
                    raw_items=raw_items,
                )
            )

        return drawings, vector_lines, rectangles

    def _build_vector_line(self, line_id: str, page_number: int, p0: Point, p1: Point, drawing: dict[str, Any], drawing_id: str) -> VectorLine:
        orientation = classify_line_orientation(p0, p1, self.line_axis_tolerance)
        return VectorLine(
            id=line_id,
            bbox=BoundingBox(min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])),
            page_number=page_number,
            x0=p0[0],
            y0=p0[1],
            x1=p1[0],
            y1=p1[1],
            orientation=orientation,
            stroke=tuple_or_none(drawing.get("color")),
            width=to_float_or_none(drawing.get("width")),
            drawing_id=drawing_id,
        )

    @staticmethod
    def _build_rectangle(rectangle_id: str, page_number: int, bbox: BoundingBox, drawing: dict[str, Any], drawing_id: str) -> Rectangle:
        return Rectangle(
            id=rectangle_id,
            bbox=bbox,
            page_number=page_number,
            stroke=tuple_or_none(drawing.get("color")),
            fill=tuple_or_none(drawing.get("fill")),
            width=to_float_or_none(drawing.get("width")),
            drawing_id=drawing_id,
        )

    @staticmethod
    def _extract_images(page: Any, page_number: int) -> list[Image]:
        images: list[Image] = []
        for image_index, image_info in enumerate(page.get_images(full=True)):
            xref = int(image_info[0])
            rects = page.get_image_rects(xref)
            for occurrence_index, rect in enumerate(rects or []):
                images.append(
                    Image(
                        id=f"p{page_number}.image{image_index}.{occurrence_index}",
                        bbox=bbox_from_rect(rect),
                        page_number=page_number,
                        xref=xref,
                        width=int(image_info[2]) if len(image_info) > 2 and image_info[2] is not None else None,
                        height=int(image_info[3]) if len(image_info) > 3 and image_info[3] is not None else None,
                        bits_per_component=int(image_info[4]) if len(image_info) > 4 and image_info[4] is not None else None,
                        colorspace=str(image_info[5]) if len(image_info) > 5 and image_info[5] is not None else None,
                        name=str(image_info[7]) if len(image_info) > 7 and image_info[7] is not None else None,
                        filter=str(image_info[8]) if len(image_info) > 8 and image_info[8] is not None else None,
                    )
                )
        return images


def parse_pdf(pdf_path: str | Path) -> Document:
    """Convenience wrapper for parsing a PDF with the default parser."""
    return PyMuPDFDocumentParser().parse(pdf_path)


def bbox_from_sequence(values: Any) -> BoundingBox:
    x0, y0, x1, y1 = values
    return BoundingBox(float(x0), float(y0), float(x1), float(y1))


def bbox_from_rect(rect: Any) -> BoundingBox:
    return BoundingBox(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


def bbox_from_items(items: list[dict[str, Any]]) -> BoundingBox:
    points = [point for item in items for point in item.get("points", [])]
    if not points:
        return BoundingBox(0.0, 0.0, 0.0, 0.0)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def point_from_any(value: Any) -> Point | None:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y"):
        return (float(value.x), float(value.y))
    return point_from_sequence(value)


def point_from_sequence(value: Any) -> Point | None:
    if value is None:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError, IndexError):
        return None


def tuple_or_none(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None
    try:
        return tuple(float(item) for item in value)
    except TypeError:
        return None


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_line_orientation(p0: Point, p1: Point, tolerance: float) -> str:
    if abs(p0[1] - p1[1]) <= tolerance:
        return "horizontal"
    if abs(p0[0] - p1[0]) <= tolerance:
        return "vertical"
    return "diagonal"


def normalize_drawing_item(item: Any) -> dict[str, Any]:
    op = item[0]
    if op == "l":
        points = [point for point in (point_from_any(item[1]), point_from_any(item[2])) if point is not None]
        return {"operator": op, "points": points}
    if op == "re":
        rect = bbox_from_rect(item[1])
        return {"operator": op, "bbox": rect.to_dict(), "points": [(rect.x0, rect.y0), (rect.x1, rect.y1)]}
    if op in {"c", "qu"}:
        points = [point for point in (point_from_any(value) for value in item[1:]) if point is not None]
        return {"operator": op, "points": points}
    points = [point for point in (point_from_any(value) for value in item[1:]) if point is not None]
    return {"operator": str(op), "points": points, "raw": repr(item)}
