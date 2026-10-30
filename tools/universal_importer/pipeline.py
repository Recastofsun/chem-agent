"""Stage 1: Parsing + Staging + Manifest Generation."""
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .formats.base import BaseFormat, BlockType, ParsedDatabase, Reaction
from .core.normalizer import clean_formula_complex, clean_formula_mineral, check_balance, parse_reaction_side
from .core.calculator import (
    RT_LN10, get_g_crc, dg_from_reaction, calculate_mineral_dg, get_g_from_cache_or_crc
)
from .core.log_manager import LogManager
from chem_agent.parser.formula import parse_formula


# Blacklist: вещества с отрицательным log_k (полностью диссоциируют)
# или сильные электролиты
BLACKLIST_BY_LOGK_THRESHOLD = -0.1  # Порог: всё, что < -0.1, исключается

BLACKLIST_FORMULAS = {
    # Сильные кислоты (полностью диссоциируют)
    "HCl", "HBr", "HI", "HNO3", "H2SO4", "HClO4", "HClO3",
    
    # Сильные основания (полностью диссоциируют)
    "NaOH", "KOH", "LiOH",
    
    # Странные вещества
    "C2O4",  # (CO2)2 - димер CO2
}


def _should_blacklist(formula: str, log_k: float) -> bool:
    """
    Проверяет, нужно ли исключить вещество из импорта.
    
    Критерии:
    1. Формула в явном blacklist
    2. Отрицательный log_k < порога (вещество полностью диссоциирует)
    """
    # Явный blacklist
    if formula in BLACKLIST_FORMULAS:
        return True
    
    # Отрицательный log_k
    if log_k < BLACKLIST_BY_LOGK_THRESHOLD:
        return True
    
    return False


@dataclass
class ImportStats:
    """Статистика импорта."""
    total_parsed: int = 0
    added: int = 0
    skipped_crc_exists: int = 0
    skipped_balance_fail: int = 0
    skipped_missing_reactants: int = 0
    skipped_master: int = 0
    skipped_blacklist: int = 0
    skipped_other: int = 0
    conflicts: list[dict] = field(default_factory=list)
    new_species: list[dict] = field(default_factory=list)
    
    def summary(self) -> str:
        return (
            f"Всего распарсено: {self.total_parsed}, "
            f"Добавлено: {self.added}, "
            f"Пропущено (CRC существует): {self.skipped_crc_exists}, "
            f"Пропущено (баланс): {self.skipped_balance_fail}, "
            f"Пропущено (нет реагентов): {self.skipped_missing_reactants}, "
            f"Пропущено (мастер): {self.skipped_master}, "
            f"Пропущено (blacklist): {self.skipped_blacklist}, "
            f"Прочее: {self.skipped_other}"
        )


class Stage1Pipeline:
    """
    Stage 1: Parsing + Staging + Manifest Generation.
    
    Создает staging.db (копия crc.db + новые вещества) и manifest.json.
    """
    
    def __init__(
        self,
        crc_db_path: Path,
        staging_db_path: Path,
        manifest_path: Path,
        log_dir: Path,
        overwrite_staging: bool = True,
    ):
        self.crc_db_path = crc_db_path
        self.staging_db_path = staging_db_path
        self.manifest_path = manifest_path
        self.log_dir = log_dir
        self.overwrite_staging = overwrite_staging
        
        # Настройка логгера
        log_manager = LogManager(log_dir, "stage1", max_logs=10)
        self.logger = log_manager.setup()
    
    def run(self, format_parser: BaseFormat) -> ImportStats:
        """Запускает Stage 1."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 1: Parsing + Staging + Manifest")
        self.logger.info("=" * 60)
        
        # Шаг 1: Парсинг
        self.logger.info(f"📖 Парсинг {format_parser.FORMAT_NAME}...")
        parsed = format_parser.parse()
        self.logger.info(f"   Мастер-ионов: {parsed.stats.get('master_species', 0)}")
        self.logger.info(f"   Реакций: {parsed.stats.get('reactions', 0)}")
        if parsed.warnings:
            for w in parsed.warnings[:5]:
                self.logger.warning(f"   ⚠️  {w}")
        
        # Шаг 2: Создание staging.db
        self._create_staging_db()
        
        # Шаг 3: Импорт с CRC lookup
        stats = self._import_with_crc_lookup(parsed)
        
        # Шаг 4: Генерация manifest
        self._generate_manifest(format_parser, stats)
        
        self.logger.info(f"\n📊 Итог Stage 1:")
        self.logger.info(f"   {stats.summary()}")
        self.logger.info(f"   Staging DB: {self.staging_db_path.name}")
        self.logger.info(f"   Manifest: {self.manifest_path.name}")
        
        return stats
    
    def _create_staging_db(self):
        """Создает staging.db как копию crc.db."""
        if self.staging_db_path.exists() and self.overwrite_staging:
            self.staging_db_path.unlink()
            self.logger.info(f"🗑️  Удален старый staging.db")
        
        if not self.crc_db_path.exists():
            raise FileNotFoundError(f"CRC DB не найден: {self.crc_db_path}")
        
        shutil.copy(str(self.crc_db_path), str(self.staging_db_path))
        self.logger.info(f"📂 Staging DB создан как копия crc.db")
    
    def _import_with_crc_lookup(self, parsed: ParsedDatabase) -> ImportStats:
        """Импортирует вещества с проверкой CRC (CRC Priority)."""
        stats = ImportStats()
        
        con = sqlite3.connect(str(self.staging_db_path))
        cur = con.cursor()
        
        # Собираем мастер-формулы
        master_formulas = {
            ms.master_formula for ms in parsed.master_species
        } | {"H2O", "e-", "H+", "OH-"}
        
        # Кэш dGf
        dg_cache: dict[str, float] = {}
        
        # Импортируем реакции
        for reaction in parsed.reactions:
            stats.total_parsed += 1
            
            if reaction.source_block == BlockType.SOLUTION_SPECIES:
                self._import_solution_species(
                    cur, reaction, master_formulas, dg_cache, stats
                )
            elif reaction.source_block == BlockType.PHASES:
                self._import_phase(
                    cur, reaction, master_formulas, dg_cache, stats
                )
        
        # Обновляем счетчик
        total = cur.execute("SELECT count(*) FROM species").fetchone()[0]
        try:
            cur.execute(
                "UPDATE meta SET value = ? WHERE key = 'species_count'",
                (str(total),)
            )
        except Exception:
            pass
        
        con.commit()
        con.close()
        
        return stats
    
    def _import_solution_species(
        self,
        cur: sqlite3.Cursor,
        reaction: Reaction,
        master_formulas: set[str],
        dg_cache: dict[str, float],
        stats: ImportStats,
    ):
        """Импортирует водный комплекс с CRC lookup."""
        left = parse_reaction_side(reaction.left)
        right = parse_reaction_side(reaction.right)
    
        if len(right) != 1:
            stats.skipped_other += 1
            return
    
        product_raw = right[0][0]
        product = clean_formula_complex(product_raw)
        
        # Защита мастер-ионов
        if product in master_formulas:
            stats.skipped_master += 1
            return
        
        # НОВОЕ: Blacklist по формуле И log_k
        if _should_blacklist(product, reaction.log_k):
            stats.skipped_blacklist += 1
            self.logger.info(f"⚠️  Пропущен {product}: в blacklist (log_k={reaction.log_k})")
            return
        
        # Проверка баланса
        if not check_balance(left, right):
            stats.skipped_balance_fail += 1
            return
        
        # CRC Lookup
        existing = cur.execute(
            "SELECT dGf, source FROM species WHERE formula = ? AND phase = 'aq'",
            (product,)
        ).fetchone()
        
        if existing:
            stats.skipped_crc_exists += 1
            stats.conflicts.append({
                "formula": product,
                "phase": "aq",
                "crc_dGf": existing[0],
                "phreeqc_dGf": None,
                "action": "SKIPPED (CRC priority)",
            })
            return
        
        # Расчет dGf
        dg_reactants = 0.0
        for f_raw, c in left:
            f = clean_formula_complex(f_raw)
            g = get_g_from_cache_or_crc(cur, f, dg_cache)
            if g is None:
                stats.skipped_missing_reactants += 1
                return
            dg_reactants += g * c
        
        dg_product = dg_from_reaction(reaction.log_k, dg_reactants)
        dg_cache[product] = dg_product
        
        # Запись в staging.db
        self._write_species(
        cur, product, "aq", dg_product, stats,
        charge=self._get_charge(product)
        )
        
        # Добавляем в manifest
        stats.new_species.append({
            "formula": product,
            "phase": "aq",
            "dGf": round(dg_product, 2),
            "source_reaction": reaction.left + " = " + reaction.right,
            "log_k": reaction.log_k,
        })
    
    def _import_phase(
        self,
        cur: sqlite3.Cursor,
        reaction: Reaction,
        master_formulas: set[str],
        dg_cache: dict[str, float],
        stats: ImportStats,
    ):
        """Импортирует минерал с CRC lookup."""
        left = parse_reaction_side(reaction.left)
        right = parse_reaction_side(reaction.right)
        
        if not left:
            stats.skipped_other += 1
            return
        
        mineral_raw = left[0][0]
        # ИСПРАВЛЕНО: используем clean_formula_mineral для минералов
        mineral = clean_formula_mineral(mineral_raw)
        
        # Проверка баланса (минерал исключается из левой части)
        if not check_balance(left[1:], right):
            stats.skipped_balance_fail += 1
            return
        
        # CRC Lookup
        existing = cur.execute(
            "SELECT dGf, source FROM species WHERE formula = ? AND phase = 's'",
            (mineral,)
        ).fetchone()
        
        if existing:
            stats.skipped_crc_exists += 1
            stats.conflicts.append({
                "formula": mineral,
                "phase": "s",
                "crc_dGf": existing[0],
                "phreeqc_dGf": None,
                "action": "SKIPPED (CRC priority)",
            })
            return
        
        # Расчет dGf
        dg_left = 0.0
        for f_raw, c in left[1:]:
            # ИСПРАВЛЕНО: используем clean_formula_complex для реагентов
            f = clean_formula_complex(f_raw)
            g = get_g_from_cache_or_crc(cur, f, dg_cache)
            if g is None:
                stats.skipped_missing_reactants += 1
                return
            dg_left += g * c
        
        dg_right = 0.0
        for f_raw, c in right:
            # ИСПРАВЛЕНО: используем clean_formula_complex для продуктов
            f = clean_formula_complex(f_raw)
            g = get_g_from_cache_or_crc(cur, f, dg_cache)
            if g is None:
                stats.skipped_missing_reactants += 1
                return
            dg_right += g * c
        
        dg_mineral = calculate_mineral_dg(reaction.log_k, dg_left, dg_right)
        
        # Запись в staging.db
        self._write_species(
            cur, mineral, "s", dg_mineral, stats,
            name_en=reaction.raw_name,
            charge=0
        )
        
        # Добавляем в manifest
        stats.new_species.append({
            "formula": mineral,
            "phase": "s",
            "dGf": round(dg_mineral, 2),
            "source_reaction": reaction.left + " = " + reaction.right,
            "log_k": reaction.log_k,
            "phase_name": reaction.raw_name,
        })
    
    def _write_species(
        self,
        cur: sqlite3.Cursor,
        formula: str,
        phase: str,
        dgf: float,
        stats: ImportStats,
        charge: Optional[int] = None,
        name_en: Optional[str] = None,
    ):
        """Записывает вещество в staging.db."""
        try:
            comp = parse_formula(formula)
            elements = json.dumps(comp.as_dict)
            if charge is None:
                charge = comp.charge
        except Exception:
            elements = "{}"
            if charge is None:
                charge = 0
        
        cur.execute(
            """INSERT INTO species 
               (formula, hill, phase, elements, charge, dGf, source, sigma, name_en) 
               VALUES (?, ?, ?, ?, ?, ?, 'phreeqc.dat', 1.0, ?)""",
            (formula, formula, phase, elements, charge, round(dgf, 2), name_en or formula)
        )
        stats.added += 1
    
    def _generate_manifest(self, format_parser: BaseFormat, stats: ImportStats):
        """Генерирует manifest.json."""
        # Вычисляем хэш источника
        source_hash = hashlib.sha256(
            format_parser.file_path.read_bytes()
        ).hexdigest()
        
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "source": format_parser.file_path.name,
            "source_hash": f"sha256:{source_hash}",
            "format": format_parser.FORMAT_NAME,
            "new_species": stats.new_species,
            "conflicts": stats.conflicts,
            "stats": {
                "total_parsed": stats.total_parsed,
                "added": stats.added,
                "skipped_crc_exists": stats.skipped_crc_exists,
                "skipped_balance_fail": stats.skipped_balance_fail,
                "skipped_missing_reactants": stats.skipped_missing_reactants,
                "skipped_master": stats.skipped_master,
                "skipped_other": stats.skipped_other,
            }
        }
        
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        self.logger.info(f"📝 Manifest сохранен: {self.manifest_path.name}")
        self.logger.info(f"   Новых веществ: {len(stats.new_species)}")
        self.logger.info(f"   Конфликтов: {len(stats.conflicts)}")
    
    @staticmethod
    def _get_charge(formula: str) -> int:
        """Извлекает заряд из формулы."""
        import re
        m = re.search(r'([+-])(\d*)$', formula)
        if not m:
            return 0
        sign = 1 if m.group(1) == "+" else -1
        count = int(m.group(2)) if m.group(2) else 1
        return sign * count