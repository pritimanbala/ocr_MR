#!/usr/bin/env python3
"""CLI for parsing engineering documents into a geometry-preserving JSON document model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

from engineering_di.config import GeometryConfig, PipelineConfig
from engineering_di.pipeline import EngineeringDocumentPipeline
from engineering_di.pdf_parser import PyMuPDFDocumentParser


SUPPORTED_EXTENSIONS = {".pdf"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse one or more engineering PDFs into JSON."
    )

    parser.add_argument(
        "input_path",
        type=Path,
        help="PDF file or directory containing PDFs.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Output JSON file (single PDF) or output directory (folder mode).",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search subdirectories.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JSON files.",
    )

    parser.add_argument(
        "--line-axis-tolerance",
        type=float,
        default=1.0,
        help="Tolerance for classifying vector lines.",
    )

    parser.add_argument(
        "--with-geometry",
        action="store_true",
        help="Run the geometry engine.",
    )

    return parser


def discover_files(path: Path, recursive: bool) -> list[Path]:

    if path.is_file():
        return [path]

    if path.is_dir():
        if recursive:
            files = [
                p
                for p in path.rglob("*")
                if p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
        else:
            files = [
                p
                for p in path.glob("*")
                if p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]

        return sorted(files)

    raise FileNotFoundError(path)


def parse_document(pdf: Path, config: PipelineConfig, geometry: bool):

    if geometry:
        pipeline = EngineeringDocumentPipeline(config)
        return pipeline.process_pdf(pdf)

    parser = PyMuPDFDocumentParser(
        line_axis_tolerance=config.geometry.axis_tolerance
    )
    return parser.parse(pdf)


def save_document(document, output_file: Path):

    output_file.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        document.to_dict(),
        ensure_ascii=False,
        indent=2,
    )

    output_file.write_text(payload + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:

    args = build_parser().parse_args(argv)

    config = PipelineConfig(
        geometry=GeometryConfig(
            axis_tolerance=args.line_axis_tolerance
        )
    )

    files = discover_files(args.input_path, args.recursive)

    if not files:
        print("No PDF files found.")
        return 1

    single_file = len(files) == 1 and files[0].is_file()

    for pdf in tqdm(files, desc="Processing PDFs"):

        if single_file and args.output.suffix == ".json":
            output_file = args.output
        else:

            if args.input_path.is_dir():
                relative = pdf.relative_to(args.input_path)
                output_file = (
                    args.output / relative
                ).with_suffix(".json")
            else:
                output_file = args.output / f"{pdf.stem}.json"

        if output_file.exists() and not args.overwrite:
            continue

        try:
            document = parse_document(
                pdf,
                config,
                args.with_geometry,
            )

            save_document(document, output_file)

        except Exception as exc:
            print(f"Failed: {pdf}")
            print(exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())