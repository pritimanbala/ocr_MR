"""Heuristic section detection for engineering tables."""
from __future__ import annotations
import re
from engineering_di.requirements.models import Section

_HEADING_WORD_RE = re.compile(r"[A-Z][A-Z0-9/&().,\- ]{2,}")
_VALUE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(bar|psi|kpa|mpa|c|°c|kw|hp|rpm|m3/h|gpm|mm|inch|in)\b", re.I)


def detect_sections(logical_rows: list[dict[str, object]]) -> dict[tuple[int | None, int | None], Section]:
    sections: dict[tuple[int | None, int | None], Section] = {}
    for row in logical_rows:
        section = section_from_row(row)
        if section:
            sections[(section.page, section.row_index)] = section
    return sections


def section_from_row(row: dict[str, object]) -> Section | None:
    texts = [str(text).strip() for text in row.get("texts", []) if str(text).strip()]  # type: ignore[arg-type]
    if not texts:
        return None
    joined = " ".join(texts).strip()
    if not looks_like_heading(texts, joined):
        return None
    return Section(name=_title_case_heading(joined), page=row.get("page"), row_index=row.get("row"), confidence=heading_confidence(texts, joined))  # type: ignore[arg-type]


def looks_like_heading(texts: list[str], joined: str) -> bool:
    if len(joined) < 3 or _VALUE_RE.search(joined):
        return False
    non_empty_count = len(texts)
    alpha_chars = [ch for ch in joined if ch.isalpha()]
    uppercase_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / max(len(alpha_chars), 1)
    all_caps = uppercase_ratio >= 0.85 and bool(_HEADING_WORD_RE.fullmatch(joined.upper()))
    no_value_beside_it = non_empty_count == 1
    short_heading = len(joined.split()) <= 8
    return all_caps and short_heading and (no_value_beside_it or len(joined) >= 8)


def heading_confidence(texts: list[str], joined: str) -> float:
    score = 0.55
    if len(texts) == 1:
        score += 0.2
    if joined.upper() == joined:
        score += 0.15
    if len(joined.split()) <= 6:
        score += 0.1
    return min(score, 1.0)


def _title_case_heading(value: str) -> str:
    return " ".join(part.capitalize() if not part.isupper() or len(part) > 3 else part for part in value.lower().split())
