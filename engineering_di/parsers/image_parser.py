"""Image parser with pluggable OCR adapters."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from engineering_di.models import BoundingBox, Document, Image, Page, Token
from engineering_di.parsers.base_parser import BaseParser

class OCRAdapter(ABC):
    name = "ocr"
    @abstractmethod
    def recognize(self, image_path: Path) -> list[Token]:
        raise NotImplementedError

class TesseractOCRAdapter(OCRAdapter):
    name = "tesseract"
    def recognize(self, image_path: Path) -> list[Token]:
        try:
            import pytesseract
            from PIL import Image as PILImage
        except ImportError as exc:
            raise RuntimeError("Missing pytesseract/Pillow dependencies for OCR.") from exc
        img = PILImage.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        tokens: list[Token] = []
        for i, text in enumerate(data.get("text", [])):
            if not str(text).strip():
                continue
            conf = float(data["conf"][i]) / 100.0 if str(data["conf"][i]).replace(".", "", 1).lstrip("-").isdigit() else None
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            tokens.append(Token(id=f"p1.ocr{i}", text=str(text), bbox=BoundingBox(float(x), float(y), float(x + w), float(y + h)), page_number=1, source="ocr", confidence=conf))
        return tokens

class ImageParser(BaseParser):
    supported_extensions = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff"})
    parser_name = "image"
    def __init__(self, ocr_adapter: OCRAdapter | None = None) -> None:
        self.ocr_adapter = ocr_adapter or TesseractOCRAdapter()
    def parse(self, path: str | Path) -> Document:
        path = self.validate_path(path)
        try:
            from PIL import Image as PILImage
        except ImportError as exc:
            raise RuntimeError("Missing dependency 'Pillow'.") from exc
        with PILImage.open(path) as img:
            width, height = img.size
            frames = getattr(img, "n_frames", 1)
        tokens = self.ocr_adapter.recognize(path)
        page = Page(number=1, bbox=BoundingBox(0, 0, float(width), float(height)), rotation=0, tokens=tokens, images=[Image(id="p1.image0", bbox=BoundingBox(0,0,float(width),float(height)), page_number=1, xref=0, width=width, height=height, name=path.name)])
        return Document(source_path=str(path), page_count=frames, metadata={"image": {"width": width, "height": height, "frames": frames}, "ocr_adapter": self.ocr_adapter.name}, pages=[page], parser=self.parser_name, schema_version="engineering.document.v1")
