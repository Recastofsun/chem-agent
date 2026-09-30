"""Energy source priority chain.

  1. known_energies from the request / reagent.known_energy   (highest)
  2. local database (CRC Handbook, NBS-1982 supplement, Ksp/E0-derived)
  3. ML potential   - unavailable in v1.0 (see energy.ml_potential)
  4. DFT            - unavailable in v1.0 (see energy.dft)
  5. empirical      - only T-extrapolation of tabulated data
  6. refusal: "неизвестно"
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..parser.formula import parse_formula
from . import dft, estimate, ml_potential
from .database import Species, ThermoDB
from .manual import ManualEnergy, apply_manual, parse_manual

SOURCE_LEVEL = {"user": 1, "CRC": 2, "NBS-1982": 2, "CRC-Ksp": 2, "CRC-E0": 2}


@dataclass
class EnergyResolver:
    db: ThermoDB
    manual: list[ManualEnergy] = field(default_factory=list)
    energy_source: str = "auto"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_request(cls, db: ThermoDB, known_energies: dict | None, reagents: list[dict],
                     energy_source: str = "auto") -> "EnergyResolver":
        manual: list[ManualEnergy] = []
        for key, spec in (known_energies or {}).items():
            # phase: explicit > from key suffix > reagent phase
            rphase = next((r.get("phase") for r in reagents
                           if parse_formula(r["formula"]).key == parse_formula(key).key), None)
            manual.append(parse_manual(key, spec, rphase))
        for r in reagents:
            ke = r.get("known_energy")
            if ke:
                if any(parse_formula(m.formula).key == parse_formula(r["formula"]).key for m in manual):
                    continue  # request-level known_energies win over reagent-level ones
                manual.append(parse_manual(r["formula"], ke, r.get("phase")))
        if energy_source in ("ml_only", "dft_only"):
            raise ValueError(
                f"energy_source={energy_source}: источник недоступен в версии 1.0 "
                f"({ml_potential.status()['reason'] if energy_source == 'ml_only' else dft.status()['reason']})")
        return cls(db=db, manual=manual, energy_source=energy_source)

    def apply(self, species: list[Species], aqueous: bool) -> list[Species]:
        """Apply manual overrides; add manual-only species that are not in the DB."""
        out = list(species)
        index = {(s.key, s.phase): i for i, s in enumerate(out)}
        for m in self.manual:
            comp = parse_formula(m.formula)
            phases = [m.phase] if m.phase else sorted({s.phase for s in self.db.find(comp)}) or ["s"]
            if not m.phase and len(phases) > 1:
                cands = [s for s in self.db.find(comp) if s.dGf is not None]
                best = min(cands, key=lambda s: s.dGf).phase if cands else phases[0]
                self.warnings.append(f"{m.formula}: фаза не указана, значение применено к фазе '{best}'")
                phases = [best]
            for ph in phases:
                if ph == "aq" and not aqueous:
                    continue
                key = (comp.key, ph)
                base = out[index[key]] if key in index else next(iter(self.db.find(comp, ph)), None)
                sp, w = apply_manual(base, ManualEnergy(**{**m.__dict__, "phase": ph}))
                self.warnings.extend(w)
                if key in index:
                    out[index[key]] = sp
                else:
                    index[key] = len(out)
                    out.append(sp)
        return out

    def chain_status(self) -> list[dict]:
        return [
            {"level": 1, "source": "known_energies (пользователь)", "available": True,
             "used": bool(self.manual), "note": f"{len(self.manual)} значений"},
            {"level": 2, "source": "локальная база (CRC, NBS-1982, Ksp, E0)", "available": True,
             "used": True, "note": f"{len(self.db.species)} частиц"},
            {"level": 3, "source": "ML-потенциал", **_st(ml_potential.status())},
            {"level": 4, "source": "DFT (PySCF)", **_st(dft.status())},
            {"level": 5, "source": "эмпирическая оценка", "available": True, "used": False,
             "note": estimate.status()["reason"]},
            {"level": 6, "source": "отказ: «неизвестно»", "available": True, "used": False,
             "note": "для частиц без данных"},
        ]


def _st(s: dict) -> dict:
    return {"available": s["available"], "used": False, "note": s["reason"]}
