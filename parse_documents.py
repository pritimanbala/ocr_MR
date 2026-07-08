#!/usr/bin/env python3
"""Production CLI for engineering document ingestion."""
from __future__ import annotations
import argparse, json, logging, tempfile, time, zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable=None, **kwargs):
        return iterable if iterable is not None else []
from engineering_di.config import GeometryConfig, PipelineConfig
from engineering_di.parsers.dispatcher import SUPPORTED_EXTENSIONS
from engineering_di.pipeline import EngineeringDocumentPipeline

LOG_DIR = Path("logs")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parse engineering documents and archives into canonical JSON.")
    p.add_argument("input_path", type=Path, help="File, folder, or ZIP archive to process.")
    p.add_argument("-o", "--output", type=Path, default=Path("output"), help="Output directory or JSON file for a single input file.")
    p.add_argument("--recursive", action="store_true", help="Recursively discover files in folders.")
    p.add_argument("--workers", type=int, default=1, help="Number of worker processes.")
    p.add_argument("--resume", action="store_true", help="Skip files whose JSON output already exists.")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON files.")
    p.add_argument("--line-axis-tolerance", type=float, default=1.0, help="Geometry tolerance for vector line classification.")
    p.add_argument("--with-geometry", action="store_true", default=True, help="Run geometry/layout pipeline after parsing.")
    return p


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(LOG_DIR / "processing.log"), logging.StreamHandler()])
    for name, filename in (("errors", "errors.log"), ("statistics", "statistics.log")):
        logger = logging.getLogger(name); logger.setLevel(logging.INFO); logger.handlers.clear(); logger.addHandler(logging.FileHandler(LOG_DIR / filename))


def safe_extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        root = destination.resolve()
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(root)):
                raise ValueError(f"Unsafe ZIP member path: {member.filename}")
        zf.extractall(destination)


def discover_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)


def expand_archives(files: Iterable[Path], root: Path, temp_root: Path) -> list[tuple[Path, Path]]:
    jobs: list[tuple[Path, Path]] = []
    for file in files:
        rel_parent = file.parent.relative_to(root) if root.is_dir() and file.is_relative_to(root) else Path("")
        if file.suffix.lower() == ".zip":
            extract_dir = temp_root / file.stem
            safe_extract_zip(file, extract_dir)
            for inner in sorted(p for p in extract_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS):
                if inner.suffix.lower() == ".zip":
                    jobs.extend(expand_archives([inner], extract_dir, temp_root / f"nested_{inner.stem}"))
                else:
                    jobs.append((inner, rel_parent / inner.relative_to(extract_dir)))
        else:
            rel = file.relative_to(root) if root.is_dir() and file.is_relative_to(root) else Path(file.name)
            jobs.append((file, rel))
    return jobs


def output_for(input_file: Path, relative: Path, output: Path, single: bool) -> Path:
    if single and output.suffix == ".json":
        return output
    return (output / relative).with_suffix(".json")


def process_one(args: tuple[str, str, float]) -> dict[str, object]:
    input_path, output_path, tolerance = args
    start = time.perf_counter(); path = Path(input_path); out = Path(output_path)
    try:
        pipeline = EngineeringDocumentPipeline(PipelineConfig(geometry=GeometryConfig(axis_tolerance=tolerance)))
        document = pipeline.process(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"file": input_path, "output": output_path, "parser": document.parser, "time": time.perf_counter() - start, "status": "ok", "error": ""}
    except Exception as exc:
        return {"file": input_path, "output": output_path, "parser": "unknown", "time": time.perf_counter() - start, "status": "error", "error": repr(exc)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv); configure_logging()
    root = args.input_path if args.input_path.is_dir() else args.input_path.parent
    files = discover_files(args.input_path, args.recursive)
    if not files:
        logging.info("No supported files found."); return 1
    with tempfile.TemporaryDirectory(prefix="engineering_di_cli_") as tmp:
        jobs_with_rel = expand_archives(files, root, Path(tmp))
        single = len(jobs_with_rel) == 1 and args.input_path.is_file()
        tasks = []
        for infile, rel in jobs_with_rel:
            outfile = output_for(infile, rel, args.output, single)
            if outfile.exists() and (args.resume or not args.overwrite):
                continue
            tasks.append((str(infile), str(outfile), args.line_axis_tolerance))
        results = []
        if args.workers > 1 and len(tasks) > 1:
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futures = [ex.submit(process_one, task) for task in tasks]
                for fut in tqdm(as_completed(futures), total=len(futures), desc="Processing documents"):
                    results.append(fut.result())
        else:
            for task in tqdm(tasks, desc="Processing documents"):
                results.append(process_one(task))
        errlog = logging.getLogger("errors"); statlog = logging.getLogger("statistics")
        for result in results:
            logging.info("file=%s parser=%s time=%.3f status=%s error=%s", result["file"], result["parser"], result["time"], result["status"], result["error"])
            statlog.info(json.dumps(result, sort_keys=True))
            if result["status"] != "ok": errlog.error(json.dumps(result, sort_keys=True))
        return 0 if all(r["status"] == "ok" for r in results) else 2

if __name__ == "__main__":
    raise SystemExit(main())
