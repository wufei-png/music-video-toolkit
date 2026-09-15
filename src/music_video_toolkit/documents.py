"""Strict JSON document loading shared by CLI and project preflight."""

import json
import math
from pathlib import Path


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def check_finite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if isinstance(value, dict):
        for child in value.values():
            check_finite(child)
    elif isinstance(value, list):
        for child in value:
            check_finite(child)


def read_document(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    check_finite(value)
    if not isinstance(value, dict):
        raise ValueError("artifact root must be an object")
    return value
