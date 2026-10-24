"""Local thermodynamic database (SQLite, built by chem_agent.data.build)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from ..parser.formula import Composition, parse_formula
from ..utils.paths import DATA_DIR

PHASE_RU = {"aq": "р-р", "s": "тв", "l": "ж", "g": "г"}


@dataclass(frozen=True)
class Species:
    formula: str
    phase: str
    elements: tuple[tuple[str, float], ...]
    charge: int
    dGf: float | None           # kJ/mol at 298.15 K
    dHf: float | None = None    # kJ/mol
    S: float | None = None      # J/(mol K)
    Cp: float | None = None
    dSf: float | None = None    # J/(mol K)
    source: str = "CRC"
    sigma: float = 1.0          # kJ/mol
    name_en: str = ""
    name_ru: str | None = None
    note: str = ""
    tags: frozenset = field(default_factory=frozenset)

    @property
    def id(self) -> str:
        return f"{self.formula}({self.phase})"

    @property
    def comp(self) -> Composition:
        return Composition(self.elements, self.charge, self.phase)

    @property
    def key(self) -> tuple:
        return (self.elements, self.charge)

    @property
    def label(self) -> str:
        return f"{self.formula} ({PHASE_RU.get(self.phase, self.phase)})"

    def molar_mass(self) -> float:
        return self.comp.molar_mass()

    def with_energy(self, **kw) -> "Species":
        return replace(self, **kw)


class ThermoDB:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or DATA_DIR / "crc.db")
        if not self.path.exists():
            raise FileNotFoundError(
                f"Не найдена локальная база {self.path}. Выполните: python -m chem_agent.data.build")
            
        con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        
        # Загрузка видов (как и раньше)
        rows = con.execute(
            "SELECT formula, phase, elements, charge, dGf, dHf, S, Cp, dSf, source, sigma, name_en, "
            "name_ru, note FROM species").fetchall()
        self.meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        
        self.species: list[Species] = []
        for r in rows:
            els = tuple(sorted((k, v) for k, v in json.loads(r[2]).items()))
            self.species.append(Species(
                formula=r[0], phase=r[1], elements=els, charge=r[3], dGf=r[4], dHf=r[5], S=r[6],
                Cp=r[7], dSf=r[8], source=r[9], sigma=r[10], name_en=r[11] or "", name_ru=r[12],
                note=r[13] or ""))
        
        self.by_key: dict[tuple, list[Species]] = {}
        for sp in self.species:
            self.by_key.setdefault(sp.key, []).append(sp)

        self.redox_pairs: dict[tuple[str, str], dict] = {}
        self.kinetic_barriers: dict[str, float] = {}
        self.sit_params: dict[tuple[str, str], float] = {}

        try:
            for row in con.execute("SELECT ox_formula, red_formula, n_electrons, e0_volts, ox_coeff, red_coeff, overpotential_V FROM redox_pairs"):
                self.redox_pairs[(row[0], row[1])] = {
                    "n": row[2], "e0": row[3], "ox_coeff": row[4], "red_coeff": row[5],
                    "overpotential_V": row[6] or 0.0
                }
                
            # Загружаем кинетические барьеры
            for row in con.execute("SELECT reaction_key, ea_kj_mol FROM kinetic_barriers"):
                self.kinetic_barriers[row[0]] = row[1]
                
            # Загружаем параметры SIT
            for row in con.execute("SELECT ion1, ion2, epsilon FROM sit_parameters"):
                self.sit_params[(row[0], row[1])] = row[2]
                self.sit_params[(row[1], row[0])] = row[2] # Симметричность
        except sqlite3.OperationalError:
            # Если база старая (без миграции), просто пропускаем
            pass

        con.close()

    def find(self, comp: Composition, phase: str | None = None) -> list[Species]:
        out = self.by_key.get(comp.key, [])
        if phase:
            out = [s for s in out if s.phase == phase]
        return out

    def find_formula(self, formula: str, phase: str | None = None) -> list[Species]:
        c = parse_formula(formula)
        return self.find(c, phase or c.phase)

    def with_elements(self, allowed: set[str]) -> list[Species]:
        return [s for s in self.species if all(e in allowed for e, _ in s.elements)]

    def find_compounds_by_element(self, symbol: str) -> list[Species]:
        """Возвращает все вещества, в состав которых входит указанный элемент."""
        out = []
        for s in self.species:
            if any(el == symbol for el, _ in s.elements):
                out.append(s)
        return out

    def get_e0(self, ox_formula: str, red_formula: str) -> dict | None:
        "Возвращает стандартный электродный потенциал и число электронов для пары."
        return self.redox_pairs.get((ox_formula, red_formula))

    def get_barrier(self, reaction_key: str) -> float | None:
        """Возвращает энергию активации для реакции (кДж/моль)."""
        return self.kinetic_barriers.get(reaction_key)

    def get_sit(self, ion1: str, ion2: str) -> float:
        """Возвращает параметр SIT для пары ионов (по умолчанию 0.0)."""
        return self.sit_params.get((ion1, ion2), 0.0)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        srcs: dict[str, int] = {}
        for s in self.species:
            counts[s.phase] = counts.get(s.phase, 0) + 1
            srcs[s.source] = srcs.get(s.source, 0) + 1
        return {"path": str(self.path), "species": len(self.species), "by_phase": counts,
                "by_source": srcs, "redox_pairs": len(self.redox_pairs), 
                "kinetic_barriers": len(self.kinetic_barriers), "sit_params": len(self.sit_params), **self.meta}


@lru_cache(maxsize=4)
def get_db(path: str | None = None) -> ThermoDB:
    return ThermoDB(Path(path) if path else None)