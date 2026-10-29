"""All filesystem paths via pathlib (Windows-first, works on Linux/macOS)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PACKAGE_DIR / "data"
TEMPLATES_DIR = PROJECT_DIR / "templates"
STATIC_DIR = PROJECT_DIR / "static"
CACHE_DIR = PROJECT_DIR / "offline_cache"
MODELS_DIR = PROJECT_DIR / "models"
EXAMPLES_DIR = PROJECT_DIR / "examples"

# bundled copies (used when package is installed without project tree)
if not TEMPLATES_DIR.exists():
    TEMPLATES_DIR = PACKAGE_DIR / "_resources" / "templates"
    STATIC_DIR = PACKAGE_DIR / "_resources" / "static"


def user_data_dir() -> Path:
    """%LOCALAPPDATA%\\chem-agent on Windows, ~/.local/share/chem-agent elsewhere."""
    override = os.environ.get("CHEM_AGENT_HOME")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "chem-agent"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "chem-agent"
    return base


def ensure_dir(p: Path) -> Path:
    p = Path(p)
    long_path(p).mkdir(parents=True, exist_ok=True)
    return p


def long_path(p: Path) -> Path:
    """Add \\\\?\\ prefix on Windows for absolute paths longer than 240 characters."""
    p = Path(p)
    if sys.platform.startswith("win"):
        s = str(p.resolve())
        if len(s) > 240 and not s.startswith("\\\\?\\"):
            if s.startswith("\\\\"):
                return Path("\\\\?\\UNC\\" + s[2:])
            return Path("\\\\?\\" + s)
    return p


def reports_dir() -> Path:
    return ensure_dir(user_data_dir() / "reports")


def logs_dir() -> Path:
    return ensure_dir(user_data_dir() / "logs")


def cache_dir() -> Path:
    return ensure_dir(user_data_dir() / "cache")
