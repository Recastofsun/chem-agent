"""Report generators: JSON, HTML (single file), Markdown."""
from __future__ import annotations

import time
from pathlib import Path

from ..utils.paths import ensure_dir, reports_dir
from .html import HTMLReport

__all__ = ["HTMLReport", "save_all", "file_stem"]


def file_stem(data: dict) -> str:
    """chem-agent_<reaction_id>_<timestamp>. The timestamp is derived from the input hash when
    CHEM_AGENT_DETERMINISTIC=1 so that identical inputs give identical file names in tests."""
    import os
    if os.environ.get("CHEM_AGENT_DETERMINISTIC") == "1":
        stamp = data["input_hash"][:14]
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"chem-agent_{data['reaction_id']}_{stamp}"


def save_all(result, output_dir=None, formats=None) -> dict[str, Path]:
    data = result.data if hasattr(result, "data") else result
    formats = formats or data["options"].get("output_formats") or ["json"]
    out_dir = Path(output_dir or data["options"].get("output_dir") or reports_dir())
    ensure_dir(out_dir)
    stem = file_stem(data)
    paths: dict[str, Path] = {}
    for f in formats:
        if f == "json":
            from .json_report import save
            paths["json"] = save(data, out_dir / f"{stem}.json")
        elif f == "html":
            paths["html"] = HTMLReport(data, theme=data["options"].get("theme", "light")).save(out_dir / f"{stem}.html")
        elif f == "markdown":
            from .markdown import save
            paths["markdown"] = save(data, out_dir / f"{stem}.md")
    return paths
