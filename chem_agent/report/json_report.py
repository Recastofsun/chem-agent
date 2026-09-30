"""JSON report (UTF-8 without BOM). Internal keys starting with '_' are dropped."""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..utils.encoding import write_text


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(f"{obj:.10g}")
    return obj


def to_public(data: dict) -> dict:
    return _clean(data)


def dumps(data: dict) -> str:
    return json.dumps(to_public(data), ensure_ascii=False, indent=2)


def save(data: dict, path: Path) -> Path:
    return write_text(path, dumps(data) + "\n")
