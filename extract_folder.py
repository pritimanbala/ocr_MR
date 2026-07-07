#!/usr/bin/env python3
"""Batch extract engineering details while mirroring an input folder tree.

This script is meant to run after `test.js` downloads S3 files using their
original keys, for example under `Pumps/`. It walks that folder, processes every
supported document, and writes JSON outputs to the same relative path in another
folder so the extracted details are easy to browse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ocr_extract import DOCUMENT_SUFFIXES, extract_document

DEFAULT_MAX_OUTPUT_PATH_LENGTH = 240


def is_temporary_office_file(path: Path) -> bool:
    """Return True for Microsoft Office lock files such as ~$PENDIX-A.docx."""
    return path.name.startswith("~$")


def shorten_name(name: str, digest: str, max_length: int = 80) -> str:
    if len(name) <= max_length:
        return name
    suffix = f"-{digest[:12]}"
    keep = max_length - len(suffix)
    return f"{name[:keep]}{suffix}"


def output_path_for(
    input_file: Path,
    input_root: Path,
    output_root: Path,
    max_output_path_length: int = DEFAULT_MAX_OUTPUT_PATH_LENGTH,
) -> Path:
    """Build the mirrored output path, with a hashed fallback for Windows path limits."""
    relative = input_file.relative_to(input_root)
    mirrored = output_root / relative.parent / f"{relative.name}.extracted.json"
    if max_output_path_length <= 0 or len(str(mirrored)) <= max_output_path_length:
        return mirrored

    digest = hashlib.sha1(str(relative).encode("utf-8")).hexdigest()
    short_name = shorten_name(f"{relative.name}.extracted.json", digest)
    return output_root / "_long_paths" / digest[:2] / digest / short_name


def iter_supported_files(input_root: Path, include_temp_files: bool = False) -> list[Path]:
    files: list[Path] = []
    for path in input_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue
        if not include_temp_files and is_temporary_office_file(path):
            continue
        files.append(path)
    return sorted(files)


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
    parser.add_argument("--include-temp-files", action="store_true", help="Also process Microsoft Office lock/temp files beginning with ~$.")
    parser.add_argument(
        "--max-output-path-length",
        type=int,
        default=DEFAULT_MAX_OUTPUT_PATH_LENGTH,
        help="Use a hashed _long_paths output location when a mirrored output path exceeds this length. Use 0 to disable.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input_root.exists() or not args.input_root.is_dir():
        raise NotADirectoryError(f"Input folder not found: {args.input_root}")

    files = iter_supported_files(args.input_root, include_temp_files=args.include_temp_files)
    summary: dict[str, Any] = {"input_root": str(args.input_root), "output_root": str(args.output_root), "files": []}

    for input_file in files:
        relative_path = str(input_file.relative_to(args.input_root))
        output_file = output_path_for(input_file, args.input_root, args.output_root, args.max_output_path_length)
        print(f"Extracting {input_file} -> {output_file}")
        try:
            result = extract_document(input_file, force_ocr=args.force_ocr, dpi=args.dpi, language=args.language)
            result["relative_path"] = relative_path
            write_json(output_file, result)
            summary["files"].append({
                "source": str(input_file),
                "relative_path": relative_path,
                "output": str(output_file),
                "status": "ok",
                "parameters": len(result.get("parameters", [])),
            })
        except Exception as exc:  # noqa: BLE001 - batch mode should report per-file failures.
            error_payload = {"source_file": str(input_file), "relative_path": relative_path, "status": "error", "error": str(exc)}
            write_json(output_file, error_payload)
            summary["files"].append({"source": str(input_file), "relative_path": relative_path, "output": str(output_file), "status": "error", "error": str(exc)})
            if not args.continue_on_error:
                write_json(args.output_root / "summary.json", summary)
                raise

    write_json(args.output_root / "summary.json", summary)
    print(f"Finished. Processed {len(files)} supported files. Summary: {args.output_root / 'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
