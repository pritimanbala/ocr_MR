#!/usr/bin/env python3
"""OCR and heuristic parameter extraction for engineering datasheet PDFs.

The extractor works in two stages:
1. Extract page text from digital PDFs with pdfplumber, or OCR scanned pages with
   pdf2image + pytesseract when text is unavailable.
2. Convert the recovered text into a JSON array of engineering parameters using
   conservative, rule-based parsing for labels, values, operators, units,
   booleans, mandatory markers, and checkboxes.

This file intentionally does not call an LLM. It is a local baseline that can be
used directly or as preprocessing for a document-intelligence model.
"""

from __future__ import annotations

import argparse
import importlib
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


@dataclass
class PageText:
    page: int
    text: str
    source: str


def import_optional(module_name: str) -> Any:
    """Import an optional dependency with an actionable error message."""
    if importlib.util.find_spec(module_name) is None:
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


def extract_pdf(pdf_path: Path, force_ocr: bool = False, dpi: int = 300, language: str = "eng") -> dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {pdf_path}")

    pages = [] if force_ocr else extract_text_with_pdfplumber(pdf_path)
    if force_ocr or not any(page.text.strip() for page in pages):
        pages = extract_text_with_ocr(pdf_path, dpi=dpi, language=language)

    combined_text = "\n".join(page.text for page in pages)
    return {
        "source_file": str(pdf_path),
        "pages": [{"page": page.page, "source": page.source, "text": page.text} for page in pages],
        "parameters": extract_parameters_from_text(combined_text),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract engineering parameters from a PDF using text extraction and OCR fallback.")
    parser.add_argument("pdf", type=Path, help="Path to the PDF file to process.")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON results to this file instead of stdout.")
    parser.add_argument("--force-ocr", action="store_true", help="OCR every page even if embedded PDF text is available.")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI for OCR mode. Default: 300.")
    parser.add_argument("--language", default="eng", help="Tesseract language code. Default: eng.")
    parser.add_argument("--parameters-only", action="store_true", help="Output only the extracted parameter array.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = extract_pdf(args.pdf, force_ocr=args.force_ocr, dpi=args.dpi, language=args.language)
    payload: Any = result["parameters"] if args.parameters_only else result
    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
