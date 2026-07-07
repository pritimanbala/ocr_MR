#!/usr/bin/env python3
"""CLI for Phase 1 PDF parsing into a geometry-preserving JSON document model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engineering_di.pdf_parser import PyMuPDFDocumentParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a PDF into the Phase 1 engineering document object model.")
    parser.add_argument("pdf", type=Path, help="PDF file to parse.")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON document model to this file instead of stdout.")
    parser.add_argument("--line-axis-tolerance", type=float, default=1.0, help="Tolerance in PDF points for classifying vector lines as horizontal or vertical.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = PyMuPDFDocumentParser(line_axis_tolerance=args.line_axis_tolerance).parse(args.pdf)
    payload = json.dumps(document.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
