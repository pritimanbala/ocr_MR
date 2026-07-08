# OCR MR

This repository is being migrated into a production-grade engineering Document Intelligence system for complex PDFs such as pump datasheets, specification sheets, vendor forms, and similar engineering documents.

The current migration separates **document geometry parsing** from later semantic extraction. Phase 1 builds a geometry-preserving PDF document object model using PyMuPDF. Later phases should add layout analysis, table detection, cell reconstruction, form reconstruction, checkbox detection, label-value association, LLM normalization, canonical JSON, and database storage.

## Architecture Direction

Target pipeline:

```text
PDF
↓
PyMuPDF Parsing
↓
OCR only if required
↓
Geometry Extraction
↓
Layout Analysis
↓
Table Detection
↓
Cell Reconstruction
↓
Form Reconstruction
↓
Checkbox Detection
↓
Label–Value Association
↓
Structured Intermediate Representation
↓
LLM Normalization
↓
Canonical JSON
↓
Database Storage
```

The current codebase is now organized around production pipeline boundaries:

- `engineering_di/pdf/` wraps PDF ingestion.
- `engineering_di/layout/` defines the DocLayout-YOLO detector boundary for titles, tables, text, headers, footers, forms, and figures.
- `engineering_di/tables/` defines the Microsoft Table Transformer boundary for table regions, rows, columns, and spanning cells.
- `engineering_di/geometry/` reconstructs vector geometry into cells and cell graphs.
- `engineering_di/forms/` is reserved for key-value, checkbox, and radio reconstruction after geometry exists.
- `engineering_di/ocr/` is reserved for OCR adapters that emit positioned tokens, not plain strings.
- `engineering_di/llm/` is reserved for semantic normalization only.
- `engineering_di/pipeline/` orchestrates the staged flow.
- `engineering_di/models.py` contains shared typed dataclasses.

DocLayout-YOLO and Microsoft Table Transformer are represented by explicit adapters but are disabled by default until model weights and runtime dependencies are configured. The pipeline does not let an LLM determine table structure.

## Phase 1: Document Parsing and Layout Foundation

Phase 1 is implemented in the `engineering_di` package and intentionally performs **no semantic extraction**.

It extracts and preserves:

- pages
- page bounding boxes and rotation
- text blocks
- text spans
- words
- normalized text tokens
- font name, size, flags, and color where available
- embedded image occurrences
- vector drawing paths from `page.get_drawings()`
- rectangles
- polygons
- horizontal, vertical, and diagonal vector lines
- curves and raw drawing primitives for later polygon/cell reconstruction

Core modules:

- `engineering_di/models.py` contains strongly typed dataclasses for `Document`, `Page`, `TextBlock`, `TextSpan`, `Word`, `Token`, `VectorLine`, `Rectangle`, `Drawing`, `Image`, and `BoundingBox`.
- `engineering_di/pdf_parser.py` contains the PyMuPDF-backed parser that fills the document object model.
- `engineering_di/geometry/engine.py` reconstructs cells from vector lines and assigns positioned tokens into cells by overlap.
- `parse_pdf_layout.py` is the Phase 1 CLI for writing the parsed document model as JSON.
- `schemas/document_model.schema.json` defines the initial JSON contract for the Phase 1 model.

Parse a PDF into the Phase 1 object model:

```bash
python parse_pdf_layout.py path/to/document.pdf --output layout.json
```

Parse and also run the geometry engine:

```bash
python parse_pdf_layout.py path/to/document.pdf --with-geometry --output layout.json
```

## Geometry-First Extraction Rule

Semantic extraction must consume reconstructed layout objects such as cells, form fields, regions, and token provenance. It must not consume flattened page text as the source of truth for tables. Legacy scripts still exist for comparison and batch continuity, but they are not the architecture for the production pipeline.

## Legacy Utilities

The previous local OCR and heuristic parameter extraction scripts remain available while the migration is in progress:

- `test.js` lists and downloads files from the `procurepumps/Pumps/` S3 prefix while preserving the original S3 key folder structure locally.
- `ocr_extract.py` is a legacy CLI that accepts supported documents and emits text plus heuristic parameters.
- `extract_folder.py` is a legacy batch CLI that reads a downloaded folder such as `Pumps/`, processes supported files, and writes extracted JSON files into a mirrored output folder.
- `prompts/engineering_document_intelligence.md` defines the desired semantic extraction behavior for later LLM normalization.
- `schemas/extracted_parameters.schema.json` defines the older JSON Schema for extracted parameter arrays.

## Supported Legacy Inputs

The legacy extractor can process:

- PDFs: embedded text with `pdfplumber`, falling back to OCR with `pdf2image` and `pytesseract` when needed.
- Images: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, and `.webp` through Tesseract OCR.
- Word files: `.docx` paragraphs and tables.
- PowerPoint files: `.pptx` slide text and tables.
- Excel files: `.xlsx`, `.xlsm`, `.xltx`, and `.xltm` sheets through `openpyxl`.
- Text-like files: `.txt`, `.md`, `.csv`, `.tsv`, `.json`, `.xml`, `.html`, and `.htm`.
- Windows thumbnail database/cache files named `Thumbs` or `Thumbs.db`; the extractor records OLE stream metadata for auditability, but these files normally contain preview thumbnails rather than engineering text.

Legacy binary Office formats such as `.doc`, `.ppt`, and `.xls` are not parsed directly. Convert them to modern formats first, or add a LibreOffice conversion step before extraction.

## Setup

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

OCR mode also needs the system binaries for Tesseract OCR and Poppler. On Debian or Ubuntu, install them with:

```bash
sudo apt-get install tesseract-ocr poppler-utils
```

Install Node dependencies if you need to download the S3 folder with `test.js`:

```bash
npm install
```

## Legacy Usage

Download the S3 folder structure defined in `test.js`:

```bash
node test.js
```

Process the downloaded folder and write a mirrored tree of extracted JSON files:

```bash
python extract_folder.py Pumps --output-root extracted_details --continue-on-error
```

For an input file such as:

```text
Pumps/VendorA/Datasheet.pdf
```

the batch extractor writes:

```text
extracted_details/VendorA/Datasheet.pdf.extracted.json
```

It also writes a run index at:

```text
extracted_details/summary.json
```

Notes for Windows batch runs:

- Microsoft Office lock files beginning with `~$` are skipped by default because they are temporary files, not real documents. Use `--include-temp-files` only if you intentionally want to inspect them.
- Files named `Thumbs` or `Thumbs.db` are included in legacy batch extraction and produce metadata JSON instead of being silently skipped.
- Very deep downloaded paths can exceed the traditional Windows path limit. When a mirrored output path is longer than 240 characters, `extract_folder.py` automatically writes that result under `extracted_details/_long_paths/...` and records the original `relative_path` plus final `output` path in `summary.json`. You can change this threshold with `--max-output-path-length`, or disable the fallback with `--max-output-path-length 0`.

Extract one document directly with the legacy extractor:

```bash
python ocr_extract.py path/to/datasheet.pdf --output result.json
```
