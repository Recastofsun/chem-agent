"""Logging to %LOCALAPPDATA%\\chem-agent\\logs (UTF-8)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .utils.paths import logs_dir


def setup(level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger("chem_agent")
    if log.handlers:
        return log
    log.setLevel(level)
    try:
        h = RotatingFileHandler(logs_dir() / "chem-agent.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(h)
    except OSError:
        log.addHandler(logging.NullHandler())
    return log
