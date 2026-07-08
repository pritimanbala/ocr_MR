# Engineering Document Intelligence Architecture Review

## Current Strengths

- The repository has separated the newer `engineering_di` package from legacy OCR scripts.
- PyMuPDF parsing is isolated behind `PyMuPDFDocumentParser`.
- Core document objects are dataclasses with explicit bounding boxes.
- Legacy batch extraction can still process the existing downloaded folder tree.
- Tests cover the document model and a small amount of legacy file handling.

## Current Weaknesses

- Legacy extraction is text-first. PDF geometry is flattened before parameter extraction.
- `ocr_extract.py` combines file parsing, OCR, text cleanup, regex semantics, table handling, and JSON output in one module.
- PDF table structure is not reconstructed before semantic extraction.
- Layout, table detection, forms, OCR adapters, LLM normalization, and orchestration were not separate production modules.
- The previous LLM prompt asked the model to reconstruct visual layout, which makes the LLM responsible for a geometry problem.

## Scalability Issues

- Batch extraction is synchronous and document-level, with no page-level cache or resumable stage artifacts.
- Heavy ML stages cannot be enabled selectively because there was no staged pipeline contract.
- There is no model configuration layer for detector thresholds, weights, or runtime choices.
- Error handling is string-based and file-level rather than stage-specific.
- Tests did not cover geometry reconstruction, cell assignment, or table independence.

## Incorrect Assumptions

- Reading order is not document structure.
- Adjacent text lines are not necessarily label-value pairs.
- Repeated labels are not necessarily duplicate parameters.
- Plain OCR text is not enough to reconstruct engineering title blocks, datasheets, and bordered forms.
- An LLM should normalize semantics only after layout and cells have been reconstructed by deterministic/model geometry stages.

## Geometry Loss Points

- `pdfplumber.extract_text()` emits plain page text and discards table cell boundaries.
- `pytesseract.image_to_string()` emits plain text instead of positioned tokens.
- `build_result()` concatenates all page text, losing page and region provenance.
- `extract_parameters_from_text()` uses line regexes, losing bounding boxes, rows, columns, sections, and cell membership.
- `merge_duplicates()` can merge unrelated table rows when labels repeat.

## Redesigned Direction

The production architecture is staged:

1. `pdf`: PyMuPDF extraction of words, spans, fonts, blocks, images, vector drawings, lines, rectangles, and polygons.
2. `layout`: DocLayout-YOLO boundary for title, table, text, footer, header, form, and figure regions.
3. `tables`: Microsoft Table Transformer boundary for table regions, rows, columns, merged cells, and spanning cells.
4. `geometry`: geometry engine for line merging, intersections, rectangles, cells, connected components, token assignment, and cell graphs.
5. `forms`: key-value, checkbox, and radio reconstruction after geometry exists.
6. `llm`: semantic normalization only.
7. `pipeline`: configurable orchestration and stage composition.

The LLM must never determine table structure. It should receive structured cells, forms, regions, and provenance.
