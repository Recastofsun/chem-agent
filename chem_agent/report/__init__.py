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


_KEEP_LAST_REPORTS = 3


def _rotate_reports(out_dir: Path, keep: int = _KEEP_LAST_REPORTS) -> None:
    """Удалить старые отчёты, оставив только `keep` новейших наборов.

    Набор = все файлы с одинаковым stem (chem-agent_<uuid>_<timestamp>).
    Сортировка по mtime файла — свежие побеждают.
    """
    try:
        entries = [p for p in out_dir.iterdir() if p.is_file()
                   and p.name.startswith("chem-agent_")
                   and p.suffix.lower() in (".json", ".html", ".md", ".markdown")]
    except OSError:
        return
    if not entries:
        return
    # группируем по stem (без расширения)
    groups: dict[str, list[Path]] = {}
    for p in entries:
        groups.setdefault(p.stem, []).append(p)
    if len(groups) <= keep:
        return
    # сортируем группы по времени самого свежего файла в группе
    def group_time(files: list[Path]) -> float:
        return max((f.stat().st_mtime for f in files if f.exists()), default=0.0)
    ordered = sorted(groups.items(), key=lambda kv: group_time(kv[1]), reverse=True)
    for _, files in ordered[keep:]:
        for f in files:
            try:
                f.unlink()
            except OSError:
                pass


def save_all(result, output_dir=None, formats=None) -> dict[str, Path]:
    data = result.data if hasattr(result, "data") else result
    formats = ["json"]
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
    _rotate_reports(out_dir, keep=_KEEP_LAST_REPORTS)
    return paths
