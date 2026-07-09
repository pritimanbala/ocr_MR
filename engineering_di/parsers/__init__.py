"""Format-specific parsers and dispatchers."""
from engineering_di.parsers.base_parser import BaseParser
from engineering_di.parsers.dispatcher import DocumentDispatcher, SUPPORTED_EXTENSIONS
from engineering_di.parsers.docx_parser import DOCXParser
from engineering_di.parsers.excel_parser import ExcelParser
from engineering_di.parsers.image_parser import ImageParser, OCRAdapter, TesseractOCRAdapter
from engineering_di.parsers.pdf_parser import PDFParser
from engineering_di.parsers.zip_handler import ZipHandler
__all__ = ["BaseParser", "DocumentDispatcher", "SUPPORTED_EXTENSIONS", "PDFParser", "DOCXParser", "ExcelParser", "ImageParser", "OCRAdapter", "TesseractOCRAdapter", "ZipHandler"]
