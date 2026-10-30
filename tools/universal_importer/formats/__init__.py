"""Реестр форматов парсеров."""
from .base import BaseFormat, BlockType, ParsedDatabase
from .phreeqc import PhreeqcFormat

FORMAT_REGISTRY = {
    "phreeqc": PhreeqcFormat,
}

__all__ = ["BaseFormat", "BlockType", "ParsedDatabase", "PhreeqcFormat", "FORMAT_REGISTRY"]