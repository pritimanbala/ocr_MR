"""Format dispatcher for engineering document ingestion."""
from __future__ import annotations
from pathlib import Path
from engineering_di.models import Document
from engineering_di.parsers.base_parser import BaseParser
from engineering_di.parsers.docx_parser import DOCXParser
from engineering_di.parsers.excel_parser import ExcelParser
from engineering_di.parsers.image_parser import ImageParser, OCRAdapter
from engineering_di.parsers.pdf_parser import PDFParser

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".zip"})

class DocumentDispatcher:
    """Dispatch files to parser implementations using suffix inspection."""
    def __init__(self, line_axis_tolerance: float = 1.0, ocr_adapter: OCRAdapter | None = None) -> None:
        self.parsers: dict[str, BaseParser] = {}
        for parser in (PDFParser(line_axis_tolerance), DOCXParser(), ExcelParser(), ImageParser(ocr_adapter)):
            for ext in parser.supported_extensions:
                self.parsers[ext] = parser

    def parse(self, path: str | Path) -> Document | list[Document]:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".zip":
            from engineering_di.parsers.zip_handler import ZipHandler
            return ZipHandler(self).parse(path)
        parser = self.parsers.get(suffix)
        if parser is None:
            raise ValueError(f"Unsupported file format '{suffix}' for {path}")
        return parser.parse(path)
