# OCR MR

This repository contains a local OCR pipeline plus prompt and schema assets for reconstructing engineering datasheet layout and extracting structured parameters from PDF files.

## Assets

- `ocr_extract.py` is a Python CLI that accepts a PDF, extracts embedded text with `pdfplumber`, falls back to OCR with `pdf2image` and `pytesseract`, and emits JSON results.
- `prompts/engineering_document_intelligence.md` defines the extraction behavior for engineering datasheets, including layout reconstruction, table handling, checkbox interpretation, mandatory-field detection, unit separation, operator extraction, and JSON-only output.
- `schemas/extracted_parameters.schema.json` defines the JSON Schema for extracted parameter arrays.
- `requirements.txt` lists the Python packages needed by the extractor.

## Setup

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

OCR mode also needs the system binaries for Tesseract OCR and Poppler. On Debian or Ubuntu, install them with:

```bash
sudo apt-get install tesseract-ocr poppler-utils
```

## Usage

Extract the full result, including per-page text and structured parameters:

```bash
python ocr_extract.py path/to/datasheet.pdf --output result.json
```

Return only the parameter array:

```bash
python ocr_extract.py path/to/datasheet.pdf --parameters-only
```

Force OCR for scanned or image-heavy PDFs:

```bash
python ocr_extract.py path/to/datasheet.pdf --force-ocr --dpi 300 --language eng
```
