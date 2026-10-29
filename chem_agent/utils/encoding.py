"""UTF-8 without BOM for writing; tolerant reading (utf-8-sig strips BOM from Notepad files)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import long_path

BOM = b"\xef\xbb\xbf"


def read_text(path: Path) -> str:
    return long_path(Path(path)).read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str, newline: str = "\n") -> Path:
    path = Path(path)
    long_path(path.parent).mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if newline != "\n":
        data = data.replace("\n", newline)
    long_path(path).write_bytes(data.encode("utf-8"))
    return path


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: Path, obj: Any) -> Path:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def has_bom(path: Path) -> bool:
    with open(long_path(Path(path)), "rb") as fh:
        return fh.read(3) == BOM
