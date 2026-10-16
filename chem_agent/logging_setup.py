"""Логирование в %LOCALAPPDATA%\\chem-agent\\logs (UTF-8, ротация по дню и размеру).

Правила хранения:
  - Каждый день — новый файл app-YYYY-MM-DD.log.
  - Максимум 5 МБ на файл.
  - При старте: удаляем файлы старше RETENTION_DAYS, но НИКОГДА не меньше MIN_FILES.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .utils.paths import logs_dir

RETENTION_DAYS = 7
MIN_FILES = 5
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def _cleanup_old_logs(directory: Path) -> None:
    """Удаляет старые логи, но не опускает общее число файлов ниже MIN_FILES."""
    try:
        files = sorted(
            [p for p in directory.glob("app-*.log*") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return

    if len(files) <= MIN_FILES:
        return

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cutoff_ts = cutoff.timestamp()

    to_delete = []
    for i, p in enumerate(files):
        if i < MIN_FILES:
            continue
        try:
            if p.stat().st_mtime < cutoff_ts:
                to_delete.append(p)
        except OSError:
            continue

    for p in to_delete:
        try:
            p.unlink()
        except OSError:
            pass


def setup(level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger("chem_agent")
    if log.handlers:
        return log
    log.setLevel(level)
    log.propagate = False

    try:
        directory = logs_dir()
        _cleanup_old_logs(directory)
        filename = directory / f"app-{datetime.now():%Y-%m-%d}.log"
        handler = RotatingFileHandler(
            filename,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        log.addHandler(handler)
    except OSError:
        log.addHandler(logging.NullHandler())

    return log


def logs_directory() -> Path:
    """Публичный путь к папке логов (для кнопки «собрать логи»)."""
    return logs_dir()


def info_about_logs() -> dict:
    """Информация о текущей папке логов (для UI/CLI)."""
    d = logs_dir()
    try:
        files = sorted(d.glob("app-*.log*"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        files = []
    total = sum(p.stat().st_size for p in files if p.is_file())
    return {
        "directory": str(d),
        "files": len(files),
        "total_bytes": total,
        "retention_days": RETENTION_DAYS,
        "min_files": MIN_FILES,
        "max_bytes_per_file": MAX_BYTES,
    }