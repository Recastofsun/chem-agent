"""Базовый класс формата термодинамической базы данных."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class BlockType(Enum):
    """Типы блоков в термодинамических базах."""
    MASTER_SPECIES = "master_species"
    SOLUTION_SPECIES = "solution_species"
    PHASES = "phases"
    EXCHANGE_SPECIES = "exchange_species"
    SURFACE_SPECIES = "surface_species"
    GAS_PHASE = "gas_phase"
    REDOX_PAIRS = "redox_pairs"
    KINETICS = "kinetics"


@dataclass
class Reaction:
    """Унифицированное представление химической реакции."""
    left: str
    right: str
    log_k: float
    delta_h: Optional[float] = None
    analytical_expression: Optional[list] = None
    gamma: Optional[float] = None
    source_block: BlockType = BlockType.SOLUTION_SPECIES
    raw_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MasterSpecies:
    """Мастер-ион (базовый компонент)."""
    element: str
    master_formula: str
    alkalinity: float = 0.0
    charge: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDatabase:
    """Результат парсинга термодинамической базы."""
    format_name: str
    source_file: str
    master_species: list[MasterSpecies] = field(default_factory=list)
    reactions: list[Reaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class BaseFormat(ABC):
    """Абстрактный базовый класс для парсера формата."""
    
    FORMAT_NAME: str = "base"
    FILE_EXTENSIONS: tuple[str, ...] = (".dat",)
    SUPPORTED_BLOCKS: tuple[BlockType, ...] = (
        BlockType.MASTER_SPECIES,
        BlockType.SOLUTION_SPECIES,
        BlockType.PHASES,
    )
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lines: list[str] = []
    
    def load(self) -> None:
        """Загружает файл в память."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.file_path}")
        self.lines = self.file_path.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
    
    @abstractmethod
    def parse(self) -> ParsedDatabase:
        """Парсит файл и возвращает унифицированную структуру."""
        ...
    
    @staticmethod
    def strip_comment(line: str, comment_char: str = "#") -> str:
        """Удаляет комментарий из строки."""
        if comment_char in line:
            return line.split(comment_char)[0].strip()
        return line.strip()