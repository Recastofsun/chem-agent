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
        self.pitzer_params: dict[tuple[str, str], dict] = {}
        self.kinetic_rules: list[dict] = []
        self.complex_constants: dict[str, dict] = {}
        self.henry_constants: dict[str, dict] = {}

        try:
            # Загружаем редокс-пары (с новыми колонками)
            for row in con.execute("SELECT ox_formula, red_formula, n_electrons, e0_volts, ox_coeff, red_coeff, overpotential_V, exchange_current_A_m2 FROM redox_pairs"):
                self.redox_pairs[(row[0], row[1])] = {
                    "n": row[2],
                    "e0": row[3],
                    "ox_coeff": row[4] or 1.0,
                    "red_coeff": row[5] or 1.0,
                    "overpotential_V": row[6] or 0.0,
                    "exchange_current_A_m2": row[7] or 1e-3
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

        try:
            for row in con.execute("SELECT ion1, ion2, beta0, beta1, beta2, C_phi, theta, psi, source "
                                   "FROM pitzer_parameters"):
                rec = dict(zip(("beta0", "beta1", "beta2", "C_phi", "theta", "psi", "source"), row[2:]))
                self.pitzer_params[(row[0], row[1])] = rec
                self.pitzer_params[(row[1], row[0])] = rec
        except sqlite3.OperationalError:
            pass  # база без patch_db_pitzer.py

        try:  # W-03: правила кинетики и константы устойчивости
            con.row_factory = sqlite3.Row
            self.kinetic_rules = [dict(r) for r in con.execute(
                "SELECT reaction_key, ea_kj_mol, kind, priority, title, why, conditions, effect, T_ref "
                "FROM kinetic_barriers WHERE effect IS NOT NULL ORDER BY priority")]
            for r in con.execute("SELECT * FROM complex_constants"):
                self.complex_constants[r["complex"]] = dict(r)
        except sqlite3.OperationalError:
            pass  # база без patch_db_w03_rules.py
        try:
            for r in con.execute("SELECT * FROM henry_constants"):
                self.henry_constants[r["gas"]] = dict(r)
        except sqlite3.OperationalError:
            pass  # база без patch_db_henry.py
        finally:
            con.row_factory = None

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

    def search(self, query: str, limit: int = 20) -> list[Species]:
        """Поиск (W-12): точная формула и та же брутто-формула в любой записи (NaCl = ClNa), затем
        подстрока формулы, затем подстрока названия ru/en без учета регистра."""
        q = query.strip()
        ql = q.lower()
        key = None
        try:
            key = parse_formula(q).key
        except Exception:
            pass
        ranked = []
        for s in self.species:
            if s.formula == q:
                r = 0
            elif key is not None and s.key == key:
                r = 1
            elif q in s.formula:
                r = 2
            elif ql in (s.name_ru or "").lower() or ql in (s.name_en or "").lower():
                r = 3
            else:
                continue
            ranked.append((r, len(s.formula), s.formula, s.phase, s))
        ranked.sort(key=lambda t: t[:4])
        return [t[-1] for t in ranked[:limit]]

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

    def get_pitzer(self, ion1: str, ion2: str) -> dict | None:
        """Параметры Pitzer для пары ионов (beta0, beta1, beta2, C_phi, theta, psi) или None."""
        return self.pitzer_params.get((ion1, ion2))

    def get_henry(self, gas: str, T: float = 298.15) -> float | None:
        """Константа Генри kH, моль/(кг·бар), при T (Вант-Гофф по d ln kH / d(1/T))."""
        h = self.henry_constants.get(gas)
        if h is None:
            return None
        import math
        return h["kH_mol_kg_bar"] * math.exp(h["dlnkH_dinvT_K"] * (1.0 / T - 1.0 / 298.15))

    def get_complex(self, formula: str) -> dict | None:
        """lg beta, металл, лиганд, n для комплекса или None."""
        return self.complex_constants.get(formula)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        srcs: dict[str, int] = {}
        for s in self.species:
            counts[s.phase] = counts.get(s.phase, 0) + 1
            srcs[s.source] = srcs.get(s.source, 0) + 1
        return {"path": str(self.path), "species": len(self.species), "by_phase": counts,
                "by_source": srcs, "redox_pairs": len(self.redox_pairs), 
                "kinetic_barriers": len(self.kinetic_barriers), "sit_params": len(self.sit_params),
                "pitzer_params": len(self.pitzer_params) // 2, **self.meta}


@lru_cache(maxsize=4)
def get_db(path: str | None = None) -> ThermoDB:
    return ThermoDB(Path(path) if path else None)