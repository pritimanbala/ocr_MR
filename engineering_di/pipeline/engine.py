"""Pipeline orchestration for the engineering document intelligence system."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from engineering_di.config import PipelineConfig
from engineering_di.geometry import GeometryEngine
from engineering_di.layout.detector import DocLayoutYOLODetector, LayoutDetector, UnconfiguredLayoutDetector
from engineering_di.llm import SemanticNormalizer
from engineering_di.models import Document
from engineering_di.pdf import PyMuPDFDocumentParser
from engineering_di.parsers import DocumentDispatcher
from engineering_di.tables.detector import TableStructureDetector, TableTransformerDetector, UnconfiguredTableStructureDetector


class EngineeringDocumentPipeline:
    """Configurable staged pipeline.

    Stage 1 is implemented. Later ML stages are adapter-backed and disabled by
    default until model weights and runtime dependencies are configured.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        layout_detector: LayoutDetector | None = None,
        table_detector: TableStructureDetector | None = None,
        semantic_normalizer: SemanticNormalizer | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        # Keep the existing PDF parser as a first-class pipeline dependency so
        # the proven PyMuPDF PDF path is not hidden behind the multi-format
        # dispatcher. Non-PDF formats are additive and are routed separately.
        self.pdf_parser = PyMuPDFDocumentParser(line_axis_tolerance=self.config.geometry.axis_tolerance)
        self.dispatcher = DocumentDispatcher(line_axis_tolerance=self.config.geometry.axis_tolerance)
        self.geometry_engine = GeometryEngine(self.config.geometry)
        self.layout_detector = layout_detector or self._build_layout_detector()
        self.table_detector = table_detector or self._build_table_detector()
        self.semantic_normalizer = semantic_normalizer or SemanticNormalizer()

    def process_pdf(self, pdf_path: str | Path) -> Document:
        """Process PDFs through the original PyMuPDF parser and existing geometry pipeline."""
        document = self.pdf_parser.parse(pdf_path)
        return self._process_parsed_document(document)

    def process(self, input_path: str | Path) -> Document:
        """Process any supported single document through parser, geometry, layout, and normalization stages."""
        path = Path(input_path)
        if path.suffix.lower() == ".pdf":
            return self.process_pdf(path)

        parsed = self.dispatcher.parse(path)
        if isinstance(parsed, list):
            raise ValueError("process() expects one document; use the CLI/dispatcher for ZIP archives that expand to multiple documents")
        return self._process_parsed_document(parsed)

    def _process_parsed_document(self, document: Document) -> Document:
        """Run geometry, layout, and semantic stages on an already parsed document."""
        pages = []
        cell_graphs = []
        for page in document.pages:
            layout_regions = self.layout_detector.detect(page)
            geometry = self.geometry_engine.reconstruct_page(page)
            cell_graphs.extend(geometry.cell_graphs)
            pages.append(replace(page, layout_regions=layout_regions, tables=geometry.tables or page.tables, cells=geometry.cells or page.cells))

        semantic_parameters = []
        if self.config.enable_semantic_normalization:
            semantic_parameters = self.semantic_normalizer.normalize(cell_graphs)

        return replace(document, pages=pages, cell_graphs=cell_graphs, semantic_parameters=semantic_parameters)

    def _build_layout_detector(self) -> LayoutDetector:
        if self.config.enable_layout_detection:
            return DocLayoutYOLODetector(self.config.layout)
        return UnconfiguredLayoutDetector(self.config.layout)

    def _build_table_detector(self) -> TableStructureDetector:
        if self.config.enable_table_transformer:
            return TableTransformerDetector(self.config.tables)
        return UnconfiguredTableStructureDetector(self.config.tables)
