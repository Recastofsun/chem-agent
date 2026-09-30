"""Build local thermodynamic SQLite database from raw offline files.

Sources (all local, see offline_cache/README.txt):
  offline_cache/crc_ions_raw.tsv        - CRC Handbook, Thermodynamic Properties of Aqueous Ions
  offline_cache/crc_substances_raw.tsv  - CRC Handbook, Standard Thermodynamic Properties of Chemical Substances
  offline_cache/crc_cas_formula.tsv     - CAS -> formula map (PubChem identifiers via `chemicals` package)
  chem_agent/data/supplement.yaml       - curated NBS-1982 values, Ksp-derived and E0-derived values

Usage:  python -m chem_agent.data.build [--out chem_agent/data/crc.db]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from pathlib import Path

import yaml

from ..parser.formula import FormulaError, parse_formula
from ..parser.naming import display_formula, hydrate_count, russian_name
from ..utils.paths import CACHE_DIR, DATA_DIR

R = 8.314462618e-3  # kJ/(mol K)
T0 = 298.15
F = 96.485332  # kJ/(V mol)

SCHEMA = """
CREATE TABLE species (
    id INTEGER PRIMARY KEY,
    formula TEXT NOT NULL,          -- display formula
    hill TEXT NOT NULL,
    elements TEXT NOT NULL,         -- JSON {"Na":1,"Cl":1}
    charge INTEGER NOT NULL,
    phase TEXT NOT NULL,            -- aq, s, l, g
    name_en TEXT,
    name_ru TEXT,
    dGf REAL,                       -- kJ/mol, 298.15 K, 1 bar
    dHf REAL,                       -- kJ/mol
    S REAL,                         -- J/(mol K)  (conventional for ions)
    Cp REAL,                        -- J/(mol K)
    dSf REAL,                       -- J/(mol K), entropy of formation, (dHf-dGf)/T0
    source TEXT NOT NULL,
    sigma REAL NOT NULL,            -- kJ/mol, 1-sigma uncertainty of dGf
    note TEXT
);
CREATE INDEX ix_species_hill ON species(hill, phase);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

SIGMA_CRC = {"aq": 1.0, "s": 1.0, "l": 1.0, "g": 0.5}


def _num(v: str) -> float | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _element_reference_entropies(rows: list[list[str]], cas_formula: dict[str, str]) -> dict[str, float]:
    """S per atom of each element in its reference state (row with dHf = 0)."""
    out: dict[str, float] = {}
    for r in rows:
        f = cas_formula.get(r[0])
        if not f:
            continue
        try:
            c = parse_formula(f)
        except FormulaError:
            continue
        if len(c.elements) != 1 or c.charge:
            continue
        el, n = c.elements[0]
        for h_i, s_i in ((2, 4), (6, 8), (10, 12)):  # s, l, g
            h, s = _num(r[h_i]), _num(r[s_i])
            if h is not None and abs(h) < 1e-9 and s is not None:
                out.setdefault(el, s / n)
    return out


def build(out: Path | None = None, cache: Path | None = None) -> Path:
    cache = Path(cache or CACHE_DIR)
    out = Path(out or DATA_DIR / "crc.db")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)
    records: dict[tuple, dict] = {}

    def add(rec: dict) -> None:
        key = (rec["hill"], rec["phase"])
        old = records.get(key)
        # keep the most stable polymorph/isomer; curated entries never override CRC
        if old is None or (rec["dGf"] is not None and old["dGf"] is not None and rec["dGf"] < old["dGf"]
                           and old["source"] == rec["source"]):
            records[key] = rec

    def make(formula: str, phase: str, name_en: str, g, h, s, cp, source: str, sigma: float,
             note: str = "", hyd: int = 0) -> dict | None:
        try:
            c = parse_formula(formula)
        except FormulaError:
            return None
        dsf = None
        if g is not None and h is not None:
            dsf = (h - g) / T0 * 1000.0
        disp = display_formula(c, hyd)
        if c.charge != 0 and phase == "aq":
            disp = formula.strip()  # keep tabulated ion notation: Fe(OH)2+, FeOH+2, Cu(NH3)4+2
        return {
            "formula": disp, "hill": c.hill(), "elements": json.dumps(c.as_dict),
            "charge": c.charge, "phase": phase, "name_en": name_en, "name_ru": russian_name(c),
            "dGf": g, "dHf": h, "S": s, "Cp": cp, "dSf": dsf, "source": source, "sigma": sigma,
            "note": note,
        }

    # --- CRC aqueous ions
    with open(cache / "crc_ions_raw.tsv", encoding="utf-8") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd)
        for r in rd:
            h, g, s, cp = (_num(x) for x in r[4:8])
            if g is None:
                continue
            rec = make(r[1], "aq", r[2], g / 1000, None if h is None else h / 1000, s, cp,
                       "CRC", SIGMA_CRC["aq"])
            if rec:
                add(rec)

    # --- CRC substances (s, l, g)
    cas_formula: dict[str, str] = {}
    with open(cache / "crc_cas_formula.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            k, v = line.rstrip("\n").split("\t")
            cas_formula[k] = v
    with open(cache / "crc_substances_raw.tsv", encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))[1:]
    # manual name -> formula fixes (unmapped CAS or wrong PubChem formula)
    fixes_path = cache / "crc_name_fixes.tsv"
    if fixes_path.exists():
        with open(fixes_path, encoding="utf-8") as fh:
            next(fh)
            fixes = dict(line.rstrip("\n").split("\t") for line in fh if line.strip())
        for r in rows:
            if r[1] in fixes:
                cas_formula[r[0]] = fixes[r[1]]
    s_ref = _element_reference_entropies(rows, cas_formula)
    h_only: dict[tuple, float] = {}
    for r in rows:
        f = cas_formula.get(r[0])
        if not f:
            continue
        try:
            comp = parse_formula(f)
        except FormulaError:
            continue
        if comp.charge != 0:  # substances table is neutral: a charged formula is a bad mapping
            continue
        for phase, base in (("s", 2), ("l", 6), ("g", 10)):
            h, g, s, cp = (_num(x) for x in r[base:base + 4])
            if h is None and g is None:
                continue
            note = ""
            if g is None and h is not None:
                if len(comp.elements) == 1 and abs(h) < 1e-9:
                    g = 0.0
                elif s is not None and all(e in s_ref for e, _ in comp.elements):
                    s_el = sum(s_ref[e] * n for e, n in comp.elements)
                    g = h - T0 * (s - s_el)  # J/mol (CRC units)
                    note = "dGf вычислена из dHf и S (S элементов из той же таблицы CRC)"
                else:
                    h_only[(comp.hill(), phase)] = h / 1000
                    continue
            if g is None:
                continue
            g_kj = g / 1000  # CRC values are J/mol
            h_kj = None if h is None else h / 1000
            rec = make(f, phase, r[1], g_kj, h_kj, s, cp, "CRC", SIGMA_CRC[phase] + (0.5 if note else 0),
                       note, hydrate_count(r[1]))
            if rec:
                add(rec)

    # --- supplement
    sup = yaml.safe_load((DATA_DIR / "supplement.yaml").read_text(encoding="utf-8"))
    for d in sup.get("direct", []):
        rec = make(d["formula"], d["phase"], d.get("name", ""), d["dGf"], d.get("dHf"), d.get("S"),
                   d.get("Cp"), "NBS-1982", d["sigma"], "ручное дополнение (NBS Tables 1982)")
        if rec and (rec["hill"], rec["phase"]) not in records:
            records[(rec["hill"], rec["phase"])] = rec

    def g_of(formula: str, phase: str = "aq") -> float:
        c = parse_formula(formula)
        rec = records.get((c.hill(), phase))
        if rec is None and formula == "H2O":
            rec = records.get((c.hill(), "l"))
        if rec is None:
            raise KeyError(f"нет данных для {formula} ({phase}) при выводе из Ksp/E0")
        return rec["dGf"]

    for d in sup.get("e0", []):
        c = parse_formula(d["formula"])
        # M(z+) + z e- -> M(s): dG = -zFE0, dGf(M)=0, dGf(e-)=0 (SHE) => dGf(M z+) = zFE0
        g = d["z"] * F * d["E0"]
        rec = make(d["formula"], "aq", "", g, None, None, None, "CRC-E0", d["sigma"],
                   f"из E0 = {d['E0']} В")
        if rec and (rec["hill"], "aq") not in records:
            records[(rec["hill"], "aq")] = rec

    for d in sup.get("ksp", []):
        g_ions = 0.0
        for ion, n in d["ions"].items():
            g_ions += n * (g_of(ion, "l") if ion == "H2O" else g_of(ion))
        g = g_ions + R * T0 * math.log(d["ksp"])
        hyd_f = float(d["ions"].get("H2O", 0))
        hyd = int(hyd_f) if hyd_f == int(hyd_f) else 0
        hill = parse_formula(d["formula"]).hill()
        h = h_only.get((hill, "s"))
        note = f"из Ksp = {d['ksp']:.3g} (25 C)" + (f"; {d['note']}" if d.get("note") else "")
        if h is not None:
            note += "; dHf из CRC"
        elif d.get("dS_ref"):
            dsf_ref = (d["dS_ref"]["dHf"] - d["dS_ref"]["dGf"]) / T0  # kJ/(mol K)
            h = g + T0 * dsf_ref
            note += "; dSf принята как у кристаллической фазы (NBS-1982)"
        rec = make(d["formula"], "s", "", g, h, None, None, "CRC-Ksp", d["sigma"], note, hyd)
        if rec and hyd_f != int(hyd_f):
            rec["formula"] = d["formula"]
        if rec and (rec["hill"], "s") not in records:
            records[(rec["hill"], "s")] = rec

    # --- post-processing
    # 1) reference states and conventions are exact: sigma = 0 (elements with dGf = 0, H+(aq))
    #    key CODATA values are known much better than the generic 1 kJ/mol
    codata_sigma = {("H2O", "l"): 0.04, ("H2O", "g"): 0.04, ("HO-", "aq"): 0.1, ("CO2", "g"): 0.13}
    for (hill, phase), rec in records.items():
        els = json.loads(rec["elements"])
        if rec["dGf"] == 0 and rec["charge"] == 0 and len(els) == 1:
            rec["sigma"] = 0.0
        if hill == "H+" and phase == "aq":
            rec["sigma"] = 0.0
        if (hill, phase) in codata_sigma:
            rec["sigma"] = codata_sigma[(hill, phase)]
    # 2) aqueous species that differ only by n H2O are the same species (AlO2- = Al(OH)4- - 2 H2O):
    #    keep the hydrated form, drop the other
    w = records.get(("H2O", "l"))
    aq = {k: r for k, r in records.items() if k[1] == "aq"}
    drop = set()
    for k, r in aq.items():
        els = json.loads(r["elements"])
        for n in (1, 2, 3):
            e2 = dict(els)
            e2["H"] = e2.get("H", 0) + 2 * n
            e2["O"] = e2.get("O", 0) + n
            c2 = parse_formula("".join(f"{a}{int(b)}" for a, b in e2.items()) + (
                ("+" if r["charge"] > 0 else "-") + str(abs(r["charge"])) if r["charge"] else ""))
            k2 = (c2.hill(), "aq")
            if k2 in aq and k2 != k:
                r2 = aq[k2]
                if abs((r["dGf"] + n * w["dGf"]) - r2["dGf"]) < 5.0:
                    drop.add(k)
    for k in drop:
        del records[k]

    cols = ["formula", "hill", "elements", "charge", "phase", "name_en", "name_ru", "dGf", "dHf", "S",
            "Cp", "dSf", "source", "sigma", "note"]
    con.executemany(
        f"INSERT INTO species ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [tuple(rec[c] for c in cols) for rec in sorted(records.values(), key=lambda r: (r["hill"], r["phase"]))],
    )
    con.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built_from", "CRC Handbook tables (via chemicals 1.5.2 data files), NBS-1982 supplement"),
        ("species_count", str(len(records))),
        ("schema_version", "1"),
    ])
    con.commit()
    con.close()
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Сборка локальной термодинамической базы")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--nist", type=Path, default=None, help="не используется: открытой выгрузки NIST нет")
    a = ap.parse_args(argv)
    p = build(a.out, a.cache)
    print(f"База собрана: {p}")


if __name__ == "__main__":
    main()
