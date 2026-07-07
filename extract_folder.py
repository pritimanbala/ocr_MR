#!/usr/bin/env python3
"""Batch extract engineering details while mirroring an input folder tree.

This script is meant to run after `test.js` downloads S3 files using their
original keys, for example under `Pumps/`. It walks that folder, processes every
supported document, and writes JSON outputs to the same relative path in another
folder so the extracted details are easy to browse.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ocr_extract import DOCUMENT_SUFFIXES, extract_document


def output_path_for(input_file: Path, input_root: Path, output_root: Path) -> Path:
    relative = input_file.relative_to(input_root)
    return output_root / relative.parent / f"{relative.name}.extracted.json"


def iter_supported_files(input_root: Path) -> list[Path]:
    return sorted(
        path for path in input_root.rglob("*") if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract details from a folder of downloaded documents and mirror the folder structure.")
    parser.add_argument("input_root", type=Path, help="Folder containing downloaded files, e.g. Pumps/")
    parser.add_argument("-o", "--output-root", type=Path, default=Path("extracted_details"), help="Folder where mirrored JSON results are written.")
    parser.add_argument("--force-ocr", action="store_true", help="OCR every PDF page even if embedded PDF text is available.")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI for PDF OCR mode. Default: 300.")
    parser.add_argument("--language", default="eng", help="Tesseract language code. Default: eng.")
    parser.add_argument("--continue-on-error", action="store_true", help="Write error JSON files and continue if one document fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input_root.exists() or not args.input_root.is_dir():
        raise NotADirectoryError(f"Input folder not found: {args.input_root}")

    files = iter_supported_files(args.input_root)
    summary: dict[str, Any] = {"input_root": str(args.input_root), "output_root": str(args.output_root), "files": []}

    for input_file in files:
        output_file = output_path_for(input_file, args.input_root, args.output_root)
        print(f"Extracting {input_file} -> {output_file}")
        try:
            result = extract_document(input_file, force_ocr=args.force_ocr, dpi=args.dpi, language=args.language)
            result["relative_path"] = str(input_file.relative_to(args.input_root))
            write_json(output_file, result)
            summary["files"].append({
                "source": str(input_file),
                "output": str(output_file),
                "status": "ok",
                "parameters": len(result.get("parameters", [])),
            })
        except Exception as exc:  # noqa: BLE001 - batch mode should report per-file failures.
            error_payload = {"source_file": str(input_file), "relative_path": str(input_file.relative_to(args.input_root)), "status": "error", "error": str(exc)}
            write_json(output_file, error_payload)
            summary["files"].append({"source": str(input_file), "output": str(output_file), "status": "error", "error": str(exc)})
            if not args.continue_on_error:
                write_json(args.output_root / "summary.json", summary)
                raise

    write_json(args.output_root / "summary.json", summary)
    print(f"Finished. Processed {len(files)} supported files. Summary: {args.output_root / 'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
