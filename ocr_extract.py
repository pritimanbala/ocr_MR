#!/usr/bin/env python3
"""OCR and heuristic parameter extraction for engineering documents.

The extractor works in two stages:
1. Recover text from common engineering document formats. Digital PDFs use
   pdfplumber, scanned PDFs and images use Tesseract OCR, and Office/text files
   use format-specific parsers.
2. Convert the recovered text into a JSON array of engineering parameters using
   conservative, rule-based parsing for labels, values, operators, units,
   booleans, mandatory markers, and checkboxes.

This file intentionally does not call an LLM. It is a local baseline that can be
used directly or as preprocessing for a document-intelligence model.
"""

from __future__ import annotations

import argparse
import csv
import importlib
from importlib.util import find_spec
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


UNIT_PATTERN = (
    r"bar|psi|MPa|kPa\(abs\)|kPa\(g\)|kPa|Pa|kg/h|kg|mg/L|ppm|°C|degC|C|°F|degF|F|"
    r"RPM|rpm|kW|W|m³/h|m3/h|L/s|l/s|mm|cm|m|in|Hz|V|A|%"
)
OPERATOR_PATTERN = r"<=|>=|<|>|=|≈|~"
CHECKED_BOX_PATTERN = re.compile(r"(?:☑|☒|\[x\]|\[X\]|\(x\)|\(X\)|✓|✔)\s*(?P<label>.+)")
UNCHECKED_BOX_PATTERN = re.compile(r"(?:☐|\[ \]|\( \))\s*(?P<label>.+)")
BOOLEAN_LINE_PATTERN = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 /&().,%#:+_-]{1,80}?)\s*[:=\-]?\s*(?P<value>YES|NO)\s*$", re.IGNORECASE)
MANDATORY_PATTERN = re.compile(
    r"\b(required|mandatory|must|shall|vendor\s+shall\s+provide|purchaser\s+requirement)\b",
    re.IGNORECASE,
)
SECTION_PATTERN = re.compile(r"^(?:[A-Z]|\d+)(?:\.\d+)*[.)]?\s+(?P<section>[A-Z][A-Za-z0-9 /&(),._-]{2,})$")
KEY_VALUE_PATTERN = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z0-9 /&().,%#:+_-]{{1,80}}?)\s*[:=\-]?\s+"
    rf"(?P<operator>{OPERATOR_PATTERN})?\s*"
    rf"(?P<value>-?\d+(?:,\d{{3}})*(?:\.\d+)?|YES|NO|N/A|NA|[A-Za-z][A-Za-z0-9 /&().,%#:+_-]+?)"
    rf"(?:\s*(?P<unit>{UNIT_PATTERN}))?\s*$",
    re.IGNORECASE,
)
TRAILING_UNIT_PATTERN = re.compile(rf"^(?P<number>-?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})$", re.IGNORECASE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SPREADSHEET_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm"}
DOCUMENT_SUFFIXES = {".pdf", ".docx", ".pptx", *SPREADSHEET_SUFFIXES, *TEXT_SUFFIXES, *IMAGE_SUFFIXES}
DATABASE_FILENAMES = {"thumbs", "thumbs.db"}


def is_supported_document(file_path: Path) -> bool:
    """Return True when a file can be handled by the legacy extractor.

    Windows Explorer may show the thumbnail cache as ``Thumbs`` without an
    extension. These files are OLE database/cache files, so filename matching is
    required in addition to suffix matching.
    """
    return file_path.suffix.lower() in DOCUMENT_SUFFIXES or file_path.name.lower() in DATABASE_FILENAMES


def is_thumbs_database(file_path: Path) -> bool:
    """Return True for Windows thumbnail database/cache files."""
    return file_path.name.lower() in DATABASE_FILENAMES


@dataclass
class PageText:
    page: int
    text: str
    source: str


def import_optional(module_name: str) -> Any:
    """Import an optional dependency with an actionable error message."""
    if find_spec(module_name) is None:
        raise RuntimeError(
            f"Missing optional dependency '{module_name}'. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        )
    return importlib.import_module(module_name)


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    aliases = {"degC": "°C", "C": "°C", "degF": "°F", "F": "°F", "rpm": "RPM", "m3/h": "m³/h", "l/s": "L/s"}
    return aliases.get(unit, unit)


def normalize_value(raw_value: str) -> Any:
    value = raw_value.strip()
    upper_value = value.upper()
    if upper_value == "YES":
        return True
    if upper_value == "NO":
        return False
    if upper_value in {"N/A", "NA"}:
        return None
    number_text = value.replace(",", "")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", number_text):
        number = float(number_text)
        return int(number) if number.is_integer() else number
    return value


def clean_label(label: str) -> str:
    label = re.sub(r"\s+", " ", label).strip(" :-\t")
    return label


def is_probable_section(line: str) -> str | None:
    match = SECTION_PATTERN.match(line.strip())
    if match:
        return clean_label(match.group("section"))
    if line.isupper() and 3 <= len(line) <= 80 and not any(char.isdigit() for char in line):
        return clean_label(line.title())
    return None


def parse_checkbox(line: str, section: str | None) -> dict[str, Any] | None:
    if UNCHECKED_BOX_PATTERN.match(line):
        return None
    checked = CHECKED_BOX_PATTERN.match(line)
    if not checked:
        return None
    label = clean_label(checked.group("label"))
    return {"section": section, "parameter": "Selected Option", "value": label, "mandatory": False}


def parse_key_value(line: str, section: str | None) -> dict[str, Any] | None:
    boolean_match = BOOLEAN_LINE_PATTERN.match(line.strip())
    if boolean_match:
        return {
            "section": section,
            "parameter": clean_label(boolean_match.group("label")),
            "value": normalize_value(boolean_match.group("value")),
            "mandatory": bool(MANDATORY_PATTERN.search(line)),
        }

    match = KEY_VALUE_PATTERN.match(line.strip())
    if not match:
        return None

    label = clean_label(match.group("label"))
    raw_value = match.group("value").strip()
    unit = normalize_unit(match.group("unit"))
    operator = match.group("operator")
    if operator == "~":
        operator = "≈"

    trailing_unit = TRAILING_UNIT_PATTERN.match(raw_value)
    if trailing_unit and unit is None:
        raw_value = trailing_unit.group("number")
        unit = normalize_unit(trailing_unit.group("unit"))

    result: dict[str, Any] = {
        "section": section,
        "parameter": label,
        "value": normalize_value(raw_value),
        "mandatory": bool(MANDATORY_PATTERN.search(line)),
    }
    if operator:
        result["operator"] = operator
    if unit:
        result["unit"] = unit
    return result


def merge_duplicates(parameters: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str | None, str], dict[str, Any]] = {}
    for item in parameters:
        key = (item.get("section"), item["parameter"])
        if key not in merged:
            merged[key] = {k: v for k, v in item.items() if v is not None}
            continue
        existing = merged[key]
        old_value = existing.get("value")
        new_value = item.get("value")
        if old_value == new_value:
            existing["mandatory"] = bool(existing.get("mandatory")) or bool(item.get("mandatory"))
        elif isinstance(old_value, list):
            old_value.append(new_value)
        else:
            existing["value"] = [old_value, new_value]
    return list(merged.values())


def extract_parameters_from_text(text: str) -> list[dict[str, Any]]:
    section: str | None = None
    parameters: list[dict[str, Any]] = []
    pending_label: str | None = None

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        section_name = is_probable_section(line)
        if section_name:
            section = section_name
            pending_label = None
            continue

        checkbox = parse_checkbox(line, section)
        if checkbox:
            parameters.append(checkbox)
            pending_label = None
            continue

        parsed = parse_key_value(line, section)
        if parsed:
            parameters.append(parsed)
            pending_label = None
            continue

        if pending_label:
            value_line = TRAILING_UNIT_PATTERN.match(line)
            parameter: dict[str, Any] = {
                "section": section,
                "parameter": pending_label,
                "value": normalize_value(value_line.group("number") if value_line else line),
                "mandatory": bool(MANDATORY_PATTERN.search(pending_label)),
            }
            if value_line:
                parameter["unit"] = normalize_unit(value_line.group("unit"))
            parameters.append(parameter)
            pending_label = None
            continue

        if 2 <= len(line) <= 80 and not re.search(r"\d", line):
            pending_label = clean_label(line)

    return merge_duplicates(parameters)


def extract_text_with_pdfplumber(pdf_path: Path) -> list[PageText]:
    pdfplumber = import_optional("pdfplumber")
    pages: list[PageText] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            pages.append(PageText(page=index, text=text, source="pdfplumber"))
    return pages


def extract_text_with_ocr(pdf_path: Path, dpi: int, language: str) -> list[PageText]:
    pdf2image = import_optional("pdf2image")
    pytesseract = import_optional("pytesseract")
    images = pdf2image.convert_from_path(str(pdf_path), dpi=dpi)
    pages: list[PageText] = []
    for index, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, lang=language, config="--psm 6")
        pages.append(PageText(page=index, text=text, source="tesseract"))
    return pages


def extract_image(image_path: Path, language: str) -> dict[str, Any]:
    image = import_optional("PIL.Image")
    pytesseract = import_optional("pytesseract")
    with image.open(image_path) as opened_image:
        text = pytesseract.image_to_string(opened_image, lang=language, config="--psm 6")
    return build_result(image_path, [PageText(page=1, text=text, source="tesseract-image")])


def extract_text_file(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if file_path.suffix.lower() in {".csv", ".tsv"}:
        dialect = "excel-tab" if file_path.suffix.lower() == ".tsv" else "excel"
        rows = [" | ".join(row) for row in csv.reader(text.splitlines(), dialect=dialect)]
        text = "\n".join(rows)
    return build_result(file_path, [PageText(page=1, text=text, source="text")])


def extract_docx(docx_path: Path) -> dict[str, Any]:
    docx = import_optional("docx")
    document = docx.Document(str(docx_path))
    lines: list[str] = []
    lines.extend(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return build_result(docx_path, [PageText(page=1, text="\n".join(lines), source="python-docx")])


def extract_pptx(pptx_path: Path) -> dict[str, Any]:
    pptx = import_optional("pptx")
    presentation = pptx.Presentation(str(pptx_path))
    pages: list[PageText] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                lines.append(shape.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
        pages.append(PageText(page=index, text="\n".join(lines), source="python-pptx"))
    return build_result(pptx_path, pages)


def extract_xlsx(xlsx_path: Path) -> dict[str, Any]:
    openpyxl = import_optional("openpyxl")
    workbook = openpyxl.load_workbook(str(xlsx_path), data_only=True, read_only=True)
    pages: list[PageText] = []
    for index, sheet in enumerate(workbook.worksheets, start=1):
        rows: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(value.strip() for value in values):
                rows.append(" | ".join(values).rstrip(" |"))
        pages.append(PageText(page=index, text="\n".join(rows), source=f"openpyxl:{sheet.title}"))
    workbook.close()
    return build_result(xlsx_path, pages)


def build_database_result(
    file_path: Path,
    database_format: str,
    streams: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    stat = file_path.stat()
    database: dict[str, Any] = {
        "format": database_format,
        "streams": streams or [],
        "metadata": metadata or {},
        "note": "Windows thumbnail caches normally contain preview images, not extractable engineering text.",
    }
    if warning:
        database["warning"] = warning
    return {
        "source_file": str(file_path),
        "file_type": "thumbs_database",
        "size_bytes": stat.st_size,
        "pages": [],
        "parameters": [],
        "database": database,
    }


def extract_thumbs_database(file_path: Path) -> dict[str, Any]:
    """Extract safe metadata from Windows Thumbs database/cache files.

    Thumbs.db files usually store thumbnail images and OLE directory streams, not
    engineering text. The extractor includes them in batch output so the file is
    no longer silently skipped, but it does not OCR or dump binary thumbnail
    bytes. Stream names and sizes are preserved for audit/debugging when the
    optional ``olefile`` package is available.
    """
    if find_spec("olefile") is None:
        return build_database_result(
            file_path,
            database_format="unknown_without_olefile",
            warning="Install olefile to inspect OLE streams inside this Windows thumbnail database.",
        )

    olefile = importlib.import_module("olefile")
    streams: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}

    try:
        with olefile.OleFileIO(str(file_path)) as ole:
            for stream_path in ole.listdir(streams=True, storages=False):
                stream_name = "/".join(stream_path)
                streams.append({"name": stream_name, "size": ole.get_size(stream_path)})

            try:
                meta = ole.get_metadata()
                metadata = {
                    key: str(value)
                    for key, value in vars(meta).items()
                    if value not in {None, ""} and not key.startswith("_")
                }
            except Exception:
                metadata = {}
    except Exception as exc:
        return build_database_result(file_path, database_format="unreadable_ole_compound_file", warning=str(exc))

    return build_database_result(file_path, database_format="ole_compound_file", streams=streams, metadata=metadata)


def build_result(source_path: Path, pages: list[PageText]) -> dict[str, Any]:
    combined_text = "\n".join(page.text for page in pages)
    return {
        "source_file": str(source_path),
        "file_type": source_path.suffix.lower().lstrip("."),
        "pages": [{"page": page.page, "source": page.source, "text": page.text} for page in pages],
        "parameters": extract_parameters_from_text(combined_text),
    }


def extract_pdf(pdf_path: Path, force_ocr: bool = False, dpi: int = 300, language: str = "eng") -> dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {pdf_path}")

    pages = [] if force_ocr else extract_text_with_pdfplumber(pdf_path)
    if force_ocr or not any(page.text.strip() for page in pages):
        pages = extract_text_with_ocr(pdf_path, dpi=dpi, language=language)

    return build_result(pdf_path, pages)


def extract_document(file_path: Path, force_ocr: bool = False, dpi: int = 300, language: str = "eng") -> dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    suffix = file_path.suffix.lower()
    if is_thumbs_database(file_path):
        return extract_thumbs_database(file_path)
    if suffix == ".pdf":
        return extract_pdf(file_path, force_ocr=force_ocr, dpi=dpi, language=language)
    if suffix in IMAGE_SUFFIXES:
        return extract_image(file_path, language=language)
    if suffix in TEXT_SUFFIXES:
        return extract_text_file(file_path)
    if suffix == ".docx":
        return extract_docx(file_path)
    if suffix == ".pptx":
        return extract_pptx(file_path)
    if suffix in SPREADSHEET_SUFFIXES:
        return extract_xlsx(file_path)
    raise ValueError(f"Unsupported file type '{suffix}' for {file_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract engineering parameters from PDFs, images, Office files, and text files.")
    parser.add_argument("document", type=Path, help="Path to the document file to process.")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON results to this file instead of stdout.")
    parser.add_argument("--force-ocr", action="store_true", help="OCR every PDF page even if embedded PDF text is available.")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI for PDF OCR mode. Default: 300.")
    parser.add_argument("--language", default="eng", help="Tesseract language code. Default: eng.")
    parser.add_argument("--parameters-only", action="store_true", help="Output only the extracted parameter array.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = extract_document(args.document, force_ocr=args.force_ocr, dpi=args.dpi, language=args.language)
    payload: Any = result["parameters"] if args.parameters_only else result
    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
