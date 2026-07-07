# OCR MR

This repository contains a local OCR and document-intelligence pipeline for reconstructing engineering datasheet layout and extracting structured parameters from downloaded project folders.

## Assets

- `test.js` lists and downloads files from the `procurepumps/Pumps/` S3 prefix while preserving the original S3 key folder structure locally.
- `ocr_extract.py` is a Python CLI that accepts one supported document, extracts text/OCR content, and emits JSON results with page text plus structured parameters.
- `extract_folder.py` is a batch CLI that reads a downloaded folder such as `Pumps/`, processes supported files, and writes extracted JSON files into a mirrored output folder.
- `prompts/engineering_document_intelligence.md` defines the extraction behavior for engineering datasheets, including layout reconstruction, table handling, checkbox interpretation, mandatory-field detection, unit separation, operator extraction, and JSON-only output.
- `schemas/extracted_parameters.schema.json` defines the JSON Schema for extracted parameter arrays.
- `requirements.txt` lists the Python packages needed by the extractor.

## Supported inputs

The extractor can process:

- PDFs: embedded text with `pdfplumber`, falling back to OCR with `pdf2image` and `pytesseract` when needed.
- Images: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, and `.webp` through Tesseract OCR.
- Word files: `.docx` paragraphs and tables.
- PowerPoint files: `.pptx` slide text and tables.
- Excel files: `.xlsx`, `.xlsm`, `.xltx`, and `.xltm` sheets through `openpyxl`.
- Text-like files: `.txt`, `.md`, `.csv`, `.tsv`, `.json`, `.xml`, `.html`, and `.htm`.

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

## Usage

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

Extract one document directly:

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
