"""Convert canonical document JSON to row-oriented pandas DataFrames."""
from __future__ import annotations
from typing import Any

try:
    import pandas as pd
except ImportError:  # keep CLI help and lightweight installs usable; requirements.txt includes pandas for production
    pd = None  # type: ignore[assignment]


def document_to_dataframe(document: dict[str, Any]) -> Any:
    """Flatten document cells/tokens into a table-like DataFrame.

    Cell objects are preferred because engineering requirements usually live in
    tables. If a page has no cells, token rows are emitted so scanned/image/PDF
    text can still flow through the same downstream section detector.
    """
    rows: list[dict[str, Any]] = []
    for page in document.get("pages", []):
        page_number = page.get("number")
        cells = page.get("cells") or []
        if cells:
            for cell in cells:
                rows.append({
                    "source_path": document.get("source_path"),
                    "page": page_number,
                    "row": cell.get("row", 0),
                    "column": cell.get("column", 0),
                    "text": _clean_text(cell.get("text", "")),
                    "bbox": cell.get("bbox"),
                    "kind": "cell",
                    "provenance": {"cell_id": cell.get("id"), "parser": document.get("parser")},
                })
            continue
        for index, token in enumerate(page.get("tokens") or []):
            rows.append({
                "source_path": document.get("source_path"),
                "page": page_number,
                "row": index,
                "column": 0,
                "text": _clean_text(token.get("text", "")),
                "bbox": token.get("bbox"),
                "kind": "token",
                "provenance": {"token_id": token.get("id"), "parser": document.get("parser")},
            })
    if pd is None:
        return sorted(rows, key=lambda item: (item.get("page") or 0, item.get("row") or 0, item.get("column") or 0))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["source_path", "page", "row", "column", "text", "bbox", "kind", "provenance"])
    return frame.sort_values(["page", "row", "column"], kind="stable").reset_index(drop=True)


def iter_logical_rows(frame: Any) -> list[dict[str, Any]]:
    """Group flattened cells/tokens into logical rows with ordered cell values."""
    if pd is None:
        if not frame:
            return []
        grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        for item in frame:
            grouped.setdefault((item.get("page"), item.get("row")), []).append(item)
        logical_rows = []
        for (page, row_index), items in sorted(grouped.items(), key=lambda item: ((item[0][0] or 0), (item[0][1] or 0))):
            ordered = sorted(items, key=lambda item: item.get("column") or 0)
            texts = [item.get("text", "") for item in ordered if item.get("text")]
            logical_rows.append({"page": page, "row": row_index, "cells": ordered, "texts": texts, "joined_text": " ".join(texts).strip()})
        return logical_rows

    if frame.empty:
        return []
    logical_rows: list[dict[str, Any]] = []
    for (page, row_index), group in frame.groupby(["page", "row"], sort=True, dropna=False):
        ordered = group.sort_values("column", kind="stable")
        texts = [text for text in ordered["text"].tolist() if text]
        logical_rows.append({
            "page": None if pd.isna(page) else int(page),
            "row": None if pd.isna(row_index) else int(row_index),
            "cells": ordered.to_dict("records"),
            "texts": texts,
            "joined_text": " ".join(texts).strip(),
        })
    return logical_rows


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())
