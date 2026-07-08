"""Geometry engine for vector-table reconstruction.

The engine intentionally works from page geometry and OCR/text tokens, not from
reading order. Later model detections can restrict the regions it examines, but
cell construction remains geometry-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from engineering_di.config import GeometryConfig
from engineering_di.models import BoundingBox, CellGraph, Page, Table, TableCell, Token, VectorLine


@dataclass(frozen=True, slots=True)
class GeometryResult:
    """Reconstructed page geometry."""

    tables: list[Table]
    cells: list[TableCell]
    cell_graphs: list[CellGraph]
    merged_lines: list[VectorLine]
    intersections: list[tuple[float, float]]


class GeometryEngine:
    """Build table cells and cell graphs from vector geometry."""

    def __init__(self, config: GeometryConfig | None = None) -> None:
        self.config = config or GeometryConfig()

    def reconstruct_page(self, page: Page) -> GeometryResult:
        merged_lines = self.merge_fragmented_lines(page.vector_lines)
        horizontal = [line for line in merged_lines if line.orientation == "horizontal"]
        vertical = [line for line in merged_lines if line.orientation == "vertical"]
        intersections = self.detect_intersections(horizontal, vertical)
        candidate_cells = self.build_cells(page.number, horizontal, vertical)
        tables = self.detect_independent_tables(page.number, candidate_cells)
        cells = self.assign_tokens_to_cells(candidate_cells, page.tokens)
        graphs = [self.build_cell_graph(table, cells) for table in tables]
        return GeometryResult(tables=tables, cells=cells, cell_graphs=graphs, merged_lines=merged_lines, intersections=intersections)

    def merge_fragmented_lines(self, lines: list[VectorLine]) -> list[VectorLine]:
        horizontal = self._merge_axis_lines([line for line in lines if line.orientation == "horizontal"], axis="y")
        vertical = self._merge_axis_lines([line for line in lines if line.orientation == "vertical"], axis="x")
        diagonal = [line for line in lines if line.orientation == "diagonal"]
        return [*horizontal, *vertical, *diagonal]

    def _merge_axis_lines(self, lines: list[VectorLine], axis: str) -> list[VectorLine]:
        if axis == "y":
            key = lambda line: (round(line.y0 / self.config.axis_tolerance), min(line.x0, line.x1))
        else:
            key = lambda line: (round(line.x0 / self.config.axis_tolerance), min(line.y0, line.y1))

        merged: list[VectorLine] = []
        for line in sorted(lines, key=key):
            if not merged or not self._can_merge(merged[-1], line):
                merged.append(line)
                continue
            previous = merged.pop()
            merged.append(self._merge_two(previous, line))
        return [self._renumber_line(index, line) for index, line in enumerate(merged)]

    def _can_merge(self, first: VectorLine, second: VectorLine) -> bool:
        if first.orientation != second.orientation:
            return False
        if first.orientation == "horizontal":
            same_axis = abs(first.y0 - second.y0) <= self.config.axis_tolerance
            gap = min(abs(second.x0 - first.x1), abs(second.x1 - first.x0))
        elif first.orientation == "vertical":
            same_axis = abs(first.x0 - second.x0) <= self.config.axis_tolerance
            gap = min(abs(second.y0 - first.y1), abs(second.y1 - first.y0))
        else:
            return False
        return same_axis and gap <= self.config.merge_gap_tolerance

    def _merge_two(self, first: VectorLine, second: VectorLine) -> VectorLine:
        if first.orientation == "horizontal":
            x0 = min(first.x0, first.x1, second.x0, second.x1)
            x1 = max(first.x0, first.x1, second.x0, second.x1)
            y = (first.y0 + second.y0) / 2
            return VectorLine(first.id, BoundingBox(x0, y, x1, y), first.page_number, x0, y, x1, y, "horizontal", first.stroke, first.width, first.drawing_id)
        y0 = min(first.y0, first.y1, second.y0, second.y1)
        y1 = max(first.y0, first.y1, second.y0, second.y1)
        x = (first.x0 + second.x0) / 2
        return VectorLine(first.id, BoundingBox(x, y0, x, y1), first.page_number, x, y0, x, y1, "vertical", first.stroke, first.width, first.drawing_id)

    @staticmethod
    def _renumber_line(index: int, line: VectorLine) -> VectorLine:
        return VectorLine(
            id=f"{line.page_number}.merged_line{index}",
            bbox=line.bbox,
            page_number=line.page_number,
            x0=line.x0,
            y0=line.y0,
            x1=line.x1,
            y1=line.y1,
            orientation=line.orientation,
            stroke=line.stroke,
            width=line.width,
            drawing_id=line.drawing_id,
        )

    def detect_intersections(self, horizontal: list[VectorLine], vertical: list[VectorLine]) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        tolerance = self.config.intersection_tolerance
        for h_line in horizontal:
            hx0, hx1 = sorted((h_line.x0, h_line.x1))
            hy = (h_line.y0 + h_line.y1) / 2
            for v_line in vertical:
                vx = (v_line.x0 + v_line.x1) / 2
                vy0, vy1 = sorted((v_line.y0, v_line.y1))
                if hx0 - tolerance <= vx <= hx1 + tolerance and vy0 - tolerance <= hy <= vy1 + tolerance:
                    points.append((vx, hy))
        return sorted(set((round(x, 2), round(y, 2)) for x, y in points))

    def build_cells(self, page_number: int, horizontal: list[VectorLine], vertical: list[VectorLine]) -> list[TableCell]:
        x_positions = sorted({round((line.x0 + line.x1) / 2, 2) for line in vertical})
        y_positions = sorted({round((line.y0 + line.y1) / 2, 2) for line in horizontal})
        cells: list[TableCell] = []
        for row, (y0, y1) in enumerate(pairwise(y_positions)):
            if y1 - y0 < self.config.cell_min_height:
                continue
            for column, (x0, x1) in enumerate(pairwise(x_positions)):
                if x1 - x0 < self.config.cell_min_width:
                    continue
                if self._has_enclosing_borders(BoundingBox(x0, y0, x1, y1), horizontal, vertical):
                    cells.append(TableCell(id=f"p{page_number}.cell{len(cells)}", bbox=BoundingBox(x0, y0, x1, y1), page_number=page_number, row=row, column=column))
        return cells

    def _has_enclosing_borders(self, bbox: BoundingBox, horizontal: list[VectorLine], vertical: list[VectorLine]) -> bool:
        return (
            self._has_horizontal_border(bbox.x0, bbox.x1, bbox.y0, horizontal)
            and self._has_horizontal_border(bbox.x0, bbox.x1, bbox.y1, horizontal)
            and self._has_vertical_border(bbox.y0, bbox.y1, bbox.x0, vertical)
            and self._has_vertical_border(bbox.y0, bbox.y1, bbox.x1, vertical)
        )

    def _has_horizontal_border(self, x0: float, x1: float, y: float, lines: list[VectorLine]) -> bool:
        tolerance = self.config.intersection_tolerance
        return any(abs(line.y0 - y) <= tolerance and min(line.x0, line.x1) <= x0 + tolerance and max(line.x0, line.x1) >= x1 - tolerance for line in lines)

    def _has_vertical_border(self, y0: float, y1: float, x: float, lines: list[VectorLine]) -> bool:
        tolerance = self.config.intersection_tolerance
        return any(abs(line.x0 - x) <= tolerance and min(line.y0, line.y1) <= y0 + tolerance and max(line.y0, line.y1) >= y1 - tolerance for line in lines)

    def assign_tokens_to_cells(self, cells: list[TableCell], tokens: list[Token]) -> list[TableCell]:
        assigned: list[TableCell] = []
        word_tokens = [token for token in tokens if token.source == "pymupdf_word" and token.text.strip()]
        for cell in cells:
            cell_tokens = [
                token
                for token in word_tokens
                if token.bbox.area > 0 and cell.bbox.intersection_area(token.bbox) / token.bbox.area >= self.config.token_overlap_threshold
            ]
            text = " ".join(token.text for token in sorted(cell_tokens, key=lambda token: (token.bbox.y0, token.bbox.x0)))
            assigned.append(
                TableCell(
                    id=cell.id,
                    bbox=cell.bbox,
                    page_number=cell.page_number,
                    row=cell.row,
                    column=cell.column,
                    row_span=cell.row_span,
                    col_span=cell.col_span,
                    token_ids=[token.id for token in cell_tokens],
                    text=text,
                    confidence=cell.confidence,
                )
            )
        return assigned

    def detect_independent_tables(self, page_number: int, cells: list[TableCell]) -> list[Table]:
        components = self._connected_components(cells)
        tables: list[Table] = []
        for index, component in enumerate(components):
            xs = [value for cell in component for value in (cell.bbox.x0, cell.bbox.x1)]
            ys = [value for cell in component for value in (cell.bbox.y0, cell.bbox.y1)]
            bbox = BoundingBox(min(xs), min(ys), max(xs), max(ys))
            tables.append(Table(id=f"p{page_number}.table{index}", bbox=bbox, page_number=page_number, cell_ids=[cell.id for cell in component]))
        return tables

    def _connected_components(self, cells: list[TableCell]) -> list[list[TableCell]]:
        remaining = set(range(len(cells)))
        components: list[list[TableCell]] = []
        while remaining:
            start = remaining.pop()
            stack = [start]
            component_indexes = {start}
            while stack:
                current = stack.pop()
                for candidate in list(remaining):
                    if self._cells_touch(cells[current], cells[candidate]):
                        remaining.remove(candidate)
                        component_indexes.add(candidate)
                        stack.append(candidate)
            components.append([cells[index] for index in sorted(component_indexes)])
        return components

    def _cells_touch(self, first: TableCell, second: TableCell) -> bool:
        expanded = first.bbox.expand(self.config.intersection_tolerance)
        return expanded.intersects(second.bbox) or expanded.contains_box(second.bbox)

    def build_cell_graph(self, table: Table, cells: list[TableCell]) -> CellGraph:
        table_cells = [cell for cell in cells if cell.id in set(table.cell_ids)]
        horizontal_edges: list[tuple[str, str]] = []
        vertical_edges: list[tuple[str, str]] = []
        for first in table_cells:
            for second in table_cells:
                if first.id == second.id:
                    continue
                if first.row == second.row and first.column + first.col_span == second.column:
                    horizontal_edges.append((first.id, second.id))
                if first.column == second.column and first.row + first.row_span == second.row:
                    vertical_edges.append((first.id, second.id))
        return CellGraph(table_id=table.id, page_number=table.page_number, cells=table_cells, horizontal_edges=horizontal_edges, vertical_edges=vertical_edges)
