"""Build typed requirement objects from section-aware rows."""
from __future__ import annotations
import hashlib
import re
from typing import Any
from engineering_di.requirements.models import Requirement, Section
from engineering_di.requirements.section_detector import section_from_row

_VALUE_UNIT_RE = re.compile(r"^(?P<operator>>=|<=|>|<|=|±)?\s*(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z°/%0-9\-]+(?:/[a-zA-Z0-9]+)?)?$")
_MATERIAL_RE = re.compile(r"\b(SS\s*316L?|316L|304L|DUPLEX|INCONEL|MONEL|BRONZE|CAST\s+IRON|CARBON\s+STEEL)\b", re.I)
_STANDARD_RE = re.compile(r"\b(API|ASME|ANSI|ISO|IEC|NACE|ASTM|DIN|EN)\s*[-A-Z0-9./]*\b", re.I)
_BOOL_RE = re.compile(r"^(yes|no|true|false|required|not required|applicable|not applicable)$", re.I)


def build_requirements(logical_rows: list[dict[str, Any]], default_section: str = "General") -> list[Requirement]:
    requirements: list[Requirement] = []
    current_section = Section(name=default_section)
    for row in logical_rows:
        detected = section_from_row(row)
        if detected:
            current_section = detected
            continue
        requirement = requirement_from_row(row, current_section)
        if requirement:
            requirements.append(requirement)
    return requirements


def requirement_from_row(row: dict[str, Any], section: Section) -> Requirement | None:
    texts = [str(text).strip() for text in row.get("texts", []) if str(text).strip()]
    if len(texts) < 2:
        return None
    parameter = texts[0]
    value_text = " ".join(texts[1:]).strip()
    if not parameter or not value_text:
        return None
    operator, value, unit = split_value_unit(value_text)
    parameter_type = infer_parameter_type(parameter, value_text, unit)
    requirement_id = stable_requirement_id(section.name, parameter, value_text, row.get("page"), row.get("row"))
    return Requirement(
        id=requirement_id,
        section=section.name,
        parameter=parameter,
        value=value,
        unit=unit,
        page=row.get("page"),
        row_index=row.get("row"),
        parameter_type=parameter_type,
        operator=operator,
        provenance={"cells": row.get("cells", [])},
    )


def split_value_unit(text: str) -> tuple[str | None, str | float | bool, str | None]:
    stripped = text.strip()
    match = _VALUE_UNIT_RE.match(stripped)
    if match:
        raw_value = match.group("value")
        value: str | float = float(raw_value) if "." in raw_value else int(raw_value)
        return match.group("operator") or None, value, match.group("unit")
    lowered = stripped.lower()
    if _BOOL_RE.match(stripped):
        return None, lowered in {"yes", "true", "required", "applicable"}, None
    return None, stripped, None


def infer_parameter_type(parameter: str, value_text: str, unit: str | None) -> str:
    combined = f"{parameter} {value_text}"
    if unit is not None or isinstance(split_value_unit(value_text)[1], (int, float)):
        return "numeric"
    if _MATERIAL_RE.search(combined):
        return "material"
    if _STANDARD_RE.search(combined):
        return "standard"
    if _BOOL_RE.match(value_text.strip()):
        return "boolean"
    if len(value_text.split()) > 12:
        return "note"
    return "text"


def stable_requirement_id(section: str, parameter: str, value: str, page: object, row: object) -> str:
    digest = hashlib.sha1(f"{section}|{parameter}|{value}|{page}|{row}".encode("utf-8")).hexdigest()[:10]
    return f"REQ-{digest.upper()}"
