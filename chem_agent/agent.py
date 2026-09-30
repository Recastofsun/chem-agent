"""Orchestrator: validation -> strategy -> equilibrium -> analysis -> uncertainty -> report."""
from __future__ import annotations

import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .conditions import atmosphere as atm_mod
from .conditions import catalyst as cat_mod
from .conditions import ph as ph_mod
from .conditions import solvent as solv_mod
from .conditions.pressure import atm_to_bar
from .conditions.temperature import profile_points, scan_range
from .energy.database import Species, get_db
from .energy.resolver import EnergyResolver
from .kinetics import barrier as barrier_mod
from .kinetics.integration import integrate
from .parser.formula import Composition, parse_formula
from .parser.naming import display_formula, russian_name
from .parser.validator import validate
from .search.balance import balance, format_side
from .search.hypotheses import ChemSystem, build_system, nominal_species_for_reagent
from .search.ranker import KIND_RU, Analysis, ProductEntry, analyze
from .search.rules import Reagent, RuleContext, evaluate
from .thermo.activity import make_gamma_fn, validity_warning
from .thermo.equilibrium import AQ, COND, GAS, SOLVENT, EqProblem, EquilibriumError, solve
from .thermo.gibbs import R, T0, dGf_T
from .uncertainty.ensemble import SIZES, draws, summarize
from .uncertainty.propagation import sigma_logK, sigma_sum
from .utils.hashing import deterministic_uuid, sha256_of

LN10 = math.log(10.0)


# ----------------------------------------------------------------------------- helpers
def _guess_phase(formula: str, aqueous: bool, db, T: float) -> str:
    comp = parse_formula(formula)
    cands = [s for s in db.find(comp) if s.dGf is not None]
    els = comp.as_dict
    if aqueous:
        if len(els) == 1 and comp.charge == 0:
            pass  # elements: standard phase
        elif any(s.phase == "aq" for s in cands) or comp.charge != 0:
            return "aq"
        else:
            from .parser.naming import salt_decomposition
            dec = salt_decomposition(comp.elements)
            if dec:
                solids = [s for s in cands if s.phase == "s"]
                cb, zc, p, ab, za, q = dec
                ions = [db.find_formula(cb + ("+" if zc == 1 else f"+{zc}"), "aq"),
                        db.find_formula(ab + ("-" if za == -1 else f"{za}"), "aq")]
                if solids and all(ions):
                    g_ions = p * ions[0][0].dGf + q * ions[1][0].dGf
                    g_s = min(x.dGf for x in solids)
                    # sparingly soluble (Ksp < 1e-2): given without a phase it is the solid
                    if g_ions - g_s > 11.4:
                        return "s"
                return "aq"
    non_aq = [s for s in cands if s.phase != "aq"]
    if non_aq:
        return min(non_aq, key=lambda s: dGf_T(s, T)[0]).phase
    return "aq" if aqueous else "s"


class _Solver:
    """Wraps building g-vectors and solving for a fixed ChemSystem."""

    def __init__(self, system: ChemSystem, T: float, P_bar: float, act_model: str, eps: float | None,
                 fixed_I: float | None):
        self.system = system
        self.T = T
        self.P_bar = P_bar
        self.gamma_fn = make_gamma_fn(act_model, T, eps) if system.aqueous else None
        self.fixed_I = fixed_I
        g, sig, tdep = [], [], []
        for s in system.species:
            gg, ss, td = dGf_T(s, T)
            g.append(gg)
            sig.append(ss)
            tdep.append(td)
        self.G = np.array(g)          # kJ/mol
        self.sigma = np.array(sig)    # kJ/mol
        self.tdep = tdep

    def run(self, dG_shift: np.ndarray | None = None, b: np.ndarray | None = None, warm=None):
        G = self.G if dG_shift is None else self.G + dG_shift
        p = EqProblem(A=self.system.A, g=G / (R * self.T), kind=self.system.kinds,
                      b=self.system.b if b is None else b,
                      charges=np.array([s.charge for s in self.system.species], dtype=float),
                      P_bar=self.P_bar, gamma_fn=self.gamma_fn, fixed_I=self.fixed_I,
                      charge_col=self.system.charge_col,
                      warm=None if warm is None else (warm.lam, warm.n, warm.water_kg / 0.018015268, warm.gas_total))
        return solve(p)


def _species_G(solver: _Solver, idx_coefs: list[tuple[int, float]], G: np.ndarray | None = None):
    G = solver.G if G is None else G
    g = sum(G[i] * c for i, c in idx_coefs)
    s = sigma_sum([(c, solver.sigma[i]) for i, c in idx_coefs])
    h_ok = all(solver.system.species[i].dHf is not None for i, _ in idx_coefs)
    h = sum(solver.system.species[i].dHf * c for i, c in idx_coefs) if h_ok else None
    return g, s, h


# ----------------------------------------------------------------------------- result
@dataclass
class Result:
    data: dict

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def to_json(self) -> str:
        from .report.json_report import dumps
        return dumps(self.data)

    def save_json(self, path) -> Path:
        from .report.json_report import save
        return save(self.data, Path(path))

    def save_html(self, path, theme: str | None = None, language: str = "ru") -> Path:
        from .report.html import HTMLReport
        return HTMLReport(result=self.data, theme=theme or self.data["options"].get("theme", "light"),
                          language=language).save(Path(path))

    def save_markdown(self, path) -> Path:
        from .report.markdown import save
        return save(self.data, Path(path))

    def save_all(self, output_dir=None, formats=None) -> dict[str, Path]:
        from .report import save_all
        return save_all(self, output_dir, formats)


# ----------------------------------------------------------------------------- agent
class Agent:
    def __init__(self, config: str | dict | None = None, offline: bool = True, db_path: str | None = None):
        from .config import load_config
        self.config = load_config(config)
        if offline:
            from .utils import offline_guard
            offline_guard.enable()
        self.db = get_db(db_path or self.config.get("db_path"))

    # public API ---------------------------------------------------------------
    def predict(self, reagents=None, conditions=None, known_energies=None, constraints=None,
                options=None, request: dict | None = None) -> Result:
        if request is None:
            request = {"reagents": reagents or [], "conditions": conditions or {},
                       "known_energies": known_energies or {}, "constraints": constraints or {},
                       "options": options or {}}
        opts = {**self.config.get("options", {}), **(request.get("options") or {})}
        request = {**request, "options": opts}
        return Result(self._run(request))

    # core ------------------------------------------------------------------------
    def _run(self, raw: dict) -> dict:
        t_start = time.perf_counter()
        req, warnings = validate(raw)
        cond, opts, cons = req["conditions"], req["options"], req["constraints"]
        input_hash = sha256_of({k: raw.get(k) for k in ("reagents", "conditions", "known_energies",
                                                        "constraints", "options") if k != "options"} |
                               {"options": {k: v for k, v in (raw.get("options") or {}).items()
                                            if k not in ("output_dir", "output_formats", "theme")}})
        reaction_id = deterministic_uuid(input_hash)
        T = cond["temperature_K"]
        P_bar = atm_to_bar(cond["pressure_atm"])
        aqueous = cond["solvent"]["name"] == "water"
        explanation: list[dict] = []
        methods: list[str] = []

        # reagents & phases
        for r in req["reagents"]:
            if r["phase"] is None:
                r["phase"] = _guess_phase(r["formula"], aqueous, self.db, T)
                warnings.append(f"{r['formula']}: фаза не задана, принята '{r['phase']}'")
        water_kg, water_note = solv_mod.water_kg(cond, req["reagents"], T) if aqueous else (0.0, "")
        reagents = [Reagent(r["formula"], parse_formula(r["formula"]), r["moles"], r["phase"])
                    for r in req["reagents"] if not (aqueous and parse_formula(r["formula"]).key ==
                                                     parse_formula("H2O").key)]
        if not reagents:
            raise ValueError("После учета воды не осталось реагентов")
        explanation.append({"step": "Парсинг и валидация",
                            "text": "Реагенты: " + ", ".join(f"{r.formula} ({r.phase}) {r.moles:g} моль" for r in reagents)
                                    + (f". Вода: {water_kg:.4g} кг ({water_note})" if aqueous else ". Без растворителя")})

        # pH
        ph = cond.get("pH") or {}
        titration = None
        if aqueous and ph.get("initial") is not None and not ph.get("buffered"):
            tr = ph_mod.titrant_for_initial_pH(ph["initial"], water_kg)
            if tr:
                reagents.append(Reagent(tr[0], parse_formula(tr[0]), tr[1], "aq"))
                warnings.append(f"Начальный pH {ph['initial']} задан добавкой {tr[1]:.3g} моль {tr[0]} "
                                "к растворителю до смешивания реагентов")
        if aqueous and ph.get("initial") is not None and ph.get("buffered"):
            titration = float(ph["initial"])
            for f in ("HCl", "NaOH"):
                reagents.append(Reagent(f, parse_formula(f), 1e-12, "aq"))
            warnings.append(f"Буферный режим: pH поддерживается равным {titration} добавкой HCl/NaOH (pH-стат)")

        # atmosphere
        gases, atm_notes = atm_mod.gas_amounts(cond, T, bool(opts.get("include_atmosphere", True)))
        warnings.extend(atm_notes)

        # rules
        ctx = RuleContext(T=T, aqueous=aqueous, reagents=reagents, volume_L=float(cond["volume_L"]),
                          atmosphere_species=[parse_formula(f) for f in gases])
        rules = evaluate(ctx, set(opts.get("disabled_rules") or []))

        # energies
        resolver = EnergyResolver.from_request(self.db, req.get("known_energies"), req["reagents"],
                                               opts["energy_source"])
        all_species = resolver.apply(self.db.species, aqueous)
        warnings.extend(resolver.warnings)

        system = build_system(all_species, reagents, T=T, P_bar=P_bar, aqueous=aqueous, water_kg=water_kg,
                              rules=rules, atmosphere=gases, forbidden_products=cons.get("forbidden_products"))
        explanation.append({"step": "Сбор энергий",
                            "text": f"Кандидатов в продукты: {len(system.species)} частиц из локальной базы "
                                    f"({self.db.meta.get('species_count')} всего). Исключено: " +
                                    (", ".join(f"{k} - {v}" for k, v in system.excluded.items()) or "ничего")})
        base = self._base_result(req, reaction_id, input_hash, warnings, resolver, system, T, P_bar)
        if system.unknown_reagents:
            base["status"] = "unknown"
            base["message"] = ("неизвестно: нет термодинамических данных для " + ", ".join(system.unknown_reagents) +
                               ". Задайте их через known_energies.")
            base["warnings"].append(base["message"])
            base["metadata"]["compute_time_s"] = round(time.perf_counter() - t_start, 3)
            return base
        if system.inert:
            warnings.append("Не участвуют в реакции (кинетика): " + ", ".join(r.formula for r in system.inert))

        eps = solv_mod.dielectric(cond["solvent"], T) if aqueous else None
        fixed_I = cond["solvent"].get("ionic_strength_M") if aqueous else None
        solver = _Solver(system, T, P_bar, opts["activity_model"], eps, fixed_I)
        self._self_equilibrated_initial(solver, system)
        methods += ["Gibbs minimization (dual barrier + Newton)", "CRC Handbook", "NBS-1982"]
        if aqueous:
            methods.append({"ideal": "ideal", "debye_huckel": "Debye-Huckel (extended)", "davies": "Davies",
                            "pitzer": "Davies (Pitzer недоступен)"}[opts["activity_model"]])
            if opts["activity_model"] == "pitzer":
                warnings.append("Модель Pitzer не реализована (нет параметров взаимодействия в открытых данных); "
                                "используется Davies")
        if any(s.source.startswith("user") for s in system.species):
            methods.append("user energies")

        # equilibrium (with optional pH-stat)
        try:
            eq, b_used = self._equilibrium(solver, titration)
            if b_used is not None:
                self._register_titrant(solver, system, b_used, titration, eq, warnings)
        except EquilibriumError as e:
            base["status"] = "error"
            base["message"] = str(e)
            return base
        n = eq.n
        for m in eq.messages:
            warnings.append(m)
        an = analyze(system, n)
        reliability: list[str] = []
        if not eq.converged:
            reliability.append("расчет равновесия не сошелся с нужной точностью (невязка баланса "
                               f"{eq.residual:.1e})")
        if aqueous and eq.ionic_strength > 5.0:
            reliability.append(f"ионная сила {eq.ionic_strength:.1f} моль/кг: модели активности за пределами "
                               "применимости, pH и активности не имеют смысла")
        if aqueous and "минус объем" in water_note and water_kg <= 0.05 * float(cond["volume_L"]) * 1.001:
            reliability.append("растворенные вещества занимают почти весь объем: оценка массы воды не работает, "
                               "задайте conditions.water_kg")
        if abs(T - T0) > 10:
            no_t = sorted({s.formula for i, s in enumerate(system.species)
                           if not solver.tdep[i] and (eq.n[i] > 1e-6 or system.initial[i] > 0)})
            if no_t:
                warnings.append("Нет ΔfH, зависимость от температуры не учтена для: " + ", ".join(no_t[:10]))
        if not aqueous and T < 700 and all(r.phase == "g" for r in system.reagents) and len(system.reagents) > 1 \
                and not (cond.get("catalyst") or {}).get("formula"):
            warnings.append("Смесь газов при T < 700 K без катализатора обычно реагирует только после поджигания "
                            "(искра, пламя, свет): показано равновесие, а не то, что произойдет само")
        explanation.append({"step": "Генерация гипотез и равновесие",
                            "text": f"Минимизация энергии Гиббса при T = {T:.2f} K, P = {P_bar:.4g} бар. "
                                    f"Итераций: {eq.iterations}, невязка баланса масс {eq.residual:.1e}."})
        for rf in rules.fired:
            explanation.append({"step": f"Правило: {rf['title']}", "text": rf["why"], "rule": rf["id"]})

        # products & equations
        products = self._products(solver, an, eq, cons)
        equations, main_eq = self._equations(solver, system, an, T)
        ionic = self._ionic_equation(system, an)
        if main_eq and main_eq.get("parallel_reactions"):
            warnings.append("Идут параллельные реакции: уравнение описывает только основную; полный итог - "
                            "в таблице равновесного состава")
        if not an.reaction_occurred:
            explanation.append({"step": "Вывод", "text": "Состав после смешивания совпадает с исходным: "
                                "реакция термодинамически не выгодна или запрещена кинетическими правилами."})
        else:
            if products:
                explanation.append({"step": "Вывод", "text": "Основной продукт: " + products[0]["formula"] +
                                    f" ({KIND_RU.get(products[0]['kind'], '')}), {products[0]['moles']:.4g} моль"})
        if aqueous:
            w = validity_warning(opts["activity_model"], eq.ionic_strength)
            if w:
                warnings.append(w)
            if T >= 373.15 * (P_bar / 1.01325) ** 0.03 and P_bar <= 1.1:
                warnings.append("T выше температуры кипения воды при данном давлении: испарение не моделируется "
                                "(считается закрытый сосуд с жидкой водой)")
        warnings.extend(self._saturation_warnings(solver, eq, system))

        # kinetics
        kinetics = self._kinetics(opts, cond, system, an, main_eq, eq, T) if opts.get("include_kinetics") else None

        # uncertainty
        unc = None
        confidence = None
        if opts.get("include_uncertainty") and opts["uncertainty_method"] != "none":
            unc = self._ensemble(solver, system, an, main_eq, opts, titration, eq)
            confidence = unc["confidence"]
            methods.append("Monte Carlo ensemble" if opts["uncertainty_method"] == "ensemble" else "bootstrap (uniform)")
        if main_eq is not None:
            main_eq["confidence"] = confidence if confidence is not None else None
        # temperature dependence
        tscan = self._temperature_scan(solver, main_eq, T, cond, system, opts, titration, all_species, reagents,
                                       gases, rules, P_bar, water_kg)

        status = "ok" if an.reaction_occurred else "no_reaction"
        message = None if an.reaction_occurred else "Реакция не идет при заданных условиях"
        if reliability:
            status = "unreliable"
            message = "Результат ненадежен: " + "; ".join(reliability)
            warnings.insert(0, message)
        base.update({
            "status": status,
            "message": message,
            "balanced_equations": equations,
            "ionic_equation": ionic,
            "products": products,
            "final_composition": self._composition(solver, eq),
            "kinetics": kinetics,
            "uncertainty": unc,
            "thermo": tscan,
            "explanation": explanation,
            "rules_fired": rules.fired,
        })
        base["summary"] = {
            "main_product": products[0]["formula"] if products else None,
            "main_product_kind": products[0]["kind"] if products else None,
            "delta_G_kJ_mol": main_eq["delta_G_kJ_mol"] if main_eq else None,
            "delta_G_uncertainty": main_eq["delta_G_uncertainty"] if main_eq else None,
            "confidence": confidence,
            "reaction_occurred": an.reaction_occurred,
            "pH": self._pH(solver, eq),
            "ionic_strength_M": eq.ionic_strength if aqueous else None,
        }
        base["metadata"]["methods_used"] = sorted(set(methods), key=methods.index)
        base["metadata"]["compute_time_s"] = round(time.perf_counter() - t_start, 3)
        return base

    # ----------------------------------------------------------------------------------
    def _base_result(self, req, reaction_id, input_hash, warnings, resolver, system, T, P_bar) -> dict:
        return {
            "reaction_id": reaction_id,
            "input_hash": input_hash,
            "status": None,
            "message": None,
            "input": {"reagents": req["reagents"], "conditions": req["conditions"],
                      "known_energies": req.get("known_energies") or {}, "constraints": req["constraints"]},
            "options": req["options"],
            "balanced_equations": [],
            "ionic_equation": None,
            "products": [],
            "kinetics": None,
            "warnings": warnings,
            "energy_chain": resolver.chain_status(),
            "system": {"T_K": T, "P_bar": P_bar, "aqueous": system.aqueous, "water_mol": system.water_mol,
                       "components": system.components, "n_species": len(system.species),
                       "inert_reagents": [r.formula for r in system.inert]},
            "metadata": {
                "compute_time_s": None, "methods_used": [], "version": __version__, "offline": True,
                "platform": platform.platform(), "python": platform.python_version(),
                "database": {k: v for k, v in self.db.meta.items()}, "random_seed": req["options"]["random_seed"],
            },
        }

    def _self_equilibrated_initial(self, solver: _Solver, system: ChemSystem) -> None:
        """Initial state for mixing reactions: each aqueous reagent equilibrated alone in the same
        amount of water. Then own hydrolysis/dissociation of a reagent is not reported as a reaction product.
        Single-reagent systems keep the nominal state (their 'reaction' is exactly that equilibrium)."""
        if not system.aqueous or len(system.reagents) < 2:
            return
        from .search.hypotheses import species_components
        share = system.water_mol  # each reagent alone in the full amount of water
        wrow = species_components(parse_formula("H2O").elements, 0, system.rules.decouple)
        total = np.zeros(len(system.species))
        n_aq = 0
        for r in system.reagents:
            elemental = len(r.comp.elements) == 1
            if (elemental or r.comp.charge != 0 or RuleContext.is_strong_oxidant(r.comp)
                    or RuleContext.is_peroxide(r.comp)):
                m = nominal_species_for_reagent(system.species, r.comp, r.phase, True)
                if m is None:
                    return
                for i, k in m:
                    total[i] += k * r.moles
                continue
            n_aq += 1
            b = np.zeros(len(system.components))
            rrow = species_components(r.comp.elements, r.comp.charge, system.rules.decouple)
            for row, mult in ((rrow, r.moles), (wrow, share)):
                for k, v in row.items():
                    if k not in system.components:
                        return
                    b[system.components.index(k)] += v * mult
            try:
                eq = solver.run(b=b)
            except Exception:  # noqa: BLE001
                return
            if eq.residual > 1e-5:
                return
            total += eq.n
        wi = next((i for i, k in enumerate(system.kinds) if k == SOLVENT), None)
        if wi is not None:
            if n_aq == 0:
                return
            total[wi] -= (n_aq - 1) * system.water_mol
        if system.atm_initial is not None:
            total += system.atm_initial
        system.initial = total

    def _equilibrium(self, solver: _Solver, titration: float | None):
        if titration is None:
            return solver.run(), None
        sysm = solver.system
        hcl = np.zeros(len(sysm.components))
        naoh = np.zeros(len(sysm.components))
        from .search.hypotheses import species_components
        for vec, f in ((hcl, "HCl"), (naoh, "NaOH")):
            c = parse_formula(f)
            for k, v in species_components(c.elements, c.charge, sysm.rules.decouple).items():
                if k in sysm.components:
                    vec[sysm.components.index(k)] = v
        cap = 10.0 * sum(r.moles for r in sysm.reagents) + 1.0

        def pH_at(x):
            b = sysm.b + (hcl * x if x > 0 else naoh * (-x))
            eq = solver.run(b=b)
            return self._pH(solver, eq), eq, b

        lo, hi = -cap, cap
        eq_lo = pH_at(lo)
        eq_hi = pH_at(hi)
        best = None
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            ph, eq, b = pH_at(mid)
            best = (eq, b)
            if ph is None:
                break
            if abs(ph - titration) < 1e-4:
                break
            if ph > titration:
                lo = mid
            else:
                hi = mid
        _ = (eq_lo, eq_hi)
        return best

    def _register_titrant(self, solver, system, b_used, target, eq, warnings) -> None:
        """pH-stat: the added HCl/NaOH becomes part of the system (b, initial state, reagents)."""
        extra = b_used - system.b
        system.b = b_used
        from .search.hypotheses import species_components
        for f in ("HCl", "NaOH"):
            c = parse_formula(f)
            row = species_components(c.elements, c.charge, system.rules.decouple)
            el = "Cl" if f == "HCl" else "Na"
            if el in system.components:
                x = float(extra[system.components.index(el)])
                if x > 1e-12:
                    m = nominal_species_for_reagent(system.species, c, "aq", True)
                    if m:
                        for i, k in m:
                            system.initial[i] += k * x
                    system.reagents.append(Reagent(f, c, x, "aq"))
                    warnings.append(f"Для поддержания pH добавлено {x:.3g} моль {f}")
            _ = row
        ph = self._pH(solver, eq)
        if ph is None or abs(ph - target) > 0.01:
            warnings.append(f"Заданный pH {target} не достигнут (получено {ph if ph is None else round(ph, 3)})")

    def _pH(self, solver: _Solver, eq) -> float | None:
        sysm = solver.system
        if not sysm.aqueous:
            return None
        ih = next((i for i, s in enumerate(sysm.species) if s.formula == "H+" and s.phase == "aq"), None)
        if ih is None or eq.water_kg <= 0:
            return None
        m = eq.n[ih] / eq.water_kg
        if m <= 0:
            return None
        return float(-(math.log(m) + eq.ln_gamma[ih]) / LN10)

    def _activity(self, solver: _Solver, eq, i: int) -> float | None:
        sysm = solver.system
        k = sysm.kinds[i]
        if k == AQ:
            if eq.water_kg <= 0:
                return None
            return float(eq.n[i] / eq.water_kg * math.exp(eq.ln_gamma[i]))
        if k == GAS:
            return float(eq.n[i] / eq.gas_total * solver.P_bar) if eq.gas_total > 0 else None
        return 1.0 if eq.n[i] > 0 else None

    def _SI(self, solver: _Solver, eq, i: int) -> float:
        """log10 saturation index of a condensed species from element potentials."""
        a = solver.system.A[i]
        return float((a @ eq.lam - solver.G[i] / (R * solver.T)) / LN10)

    def _products(self, solver: _Solver, an: Analysis, eq, cons) -> list[dict]:
        out = []
        sysm = solver.system
        for p in an.products[: int(cons.get("max_products") or 10)]:
            if p.parts:
                g, s, _ = _species_G(solver, p.parts)
                src = sorted({sysm.species[i].source for i, _ in p.parts})
                act = None
                ci, ai = p.parts[0][0], p.parts[1][0]
                si = None
            else:
                i = p.species_idx[0]
                g, s = float(solver.G[i]), float(solver.sigma[i])
                src = [sysm.species[i].source]
                act = self._activity(solver, eq, i)
                si = self._SI(solver, eq, i) if sysm.kinds[i] == COND else None
            out.append({
                "formula": p.formula, "name_ru": p.name_ru, "phase": p.phase, "kind": p.kind,
                "kind_ru": KIND_RU[p.kind], "moles": p.moles, "mass_g": p.mass_g,
                "delta_Gf_kJ_mol": g, "uncertainty": s, "source": "+".join(src), "activity": act,
                "saturation_index": si, "score": p.score,
                "_parts_formulas": [sysm.species[i].formula for i, _ in p.parts],
            })
        return out

    def _participant_G(self, solver: _Solver, entry) -> tuple[list[tuple[int, float]] | None, str]:
        if isinstance(entry, ProductEntry):
            if entry.parts:
                return entry.parts, entry.formula
            return [(entry.species_idx[0], 1.0)], entry.formula
        return None, ""

    def _equations(self, solver: _Solver, system: ChemSystem, an: Analysis, T: float):
        if not an.reaction_occurred:
            return [], None
        prods = [p for p in an.products if p.kind != "ion" or not any(
            q.parts and p.species_idx[0] in [i for i, _ in q.parts] for q in an.products)]
        # keep a compact set: condensed, gases, salts, molecules, water, uncovered ions
        prods = prods[:8]
        reag = []
        for r in system.reagents:  # drop pH-stat placeholders, merge repeated formulas
            if r.moles <= 1e-10:
                continue
            same = next((x for x in reag if x.comp.key == r.comp.key), None)
            if same:
                same.moles += r.moles
            else:
                reag.append(Reagent(r.formula, r.comp, r.moles, r.phase))
        # water and consumed atmospheric gases can be reagents of the overall equation
        net: dict[tuple, float] = {}
        for sp_, d in zip(system.species, an.delta):
            net[sp_.key] = net.get(sp_.key, 0.0) + d
        pkeys = {p.key for p in prods}
        wkey = parse_formula("H2O").key
        if system.aqueous and wkey not in pkeys and net.get(wkey, 0.0) < -1e-3 * an.ref_moles:
            reag.append(Reagent("H2O", parse_formula("H2O"), -net[wkey], "l"))
        for k in sorted(system.atm_keys, key=str):
            if net.get(k, 0.0) < -1e-3 * an.ref_moles and k not in pkeys:
                c = Composition(k[0], k[1])
                reag.append(Reagent(display_formula(c), c, -net[k], "g"))
        rc = [dict(r.comp.elements) for r in reag]
        rq = [r.comp.charge for r in reag]
        pc = [dict(p.key[0]) for p in prods]
        pq = [p.key[1] for p in prods]
        parallel = False
        res = balance(rc, rq, pc, pq, [p.moles for p in prods])
        if res is None:
            res = balance(rc, rq, pc, pq)
        if res is None:
            # several parallel reactions: equation of the main product with the smallest consistent set
            from itertools import combinations
            all_idx = list(range(len(prods)))
            for size in range(min(4, len(prods)), 0, -1):
                for comb in combinations(all_idx, size):
                    if 0 not in comb:
                        continue
                    sel = list(comb)
                    r2 = balance(rc, rq, [pc[i] for i in sel], [pq[i] for i in sel], [prods[i].moles for i in sel])
                    if r2 is not None:
                        dropped = [prods[i] for i in range(len(prods)) if i not in sel]
                        parallel = any(d.moles >= 0.1 * prods[0].moles for d in dropped)
                        prods = [prods[i] for i in sel]
                        pc = [pc[i] for i in sel]
                        pq = [pq[i] for i in sel]
                        res = r2
                        break
                if res is not None:
                    break
        eqs = []
        main = None
        if res is not None:
            cr, cp = res
            rnames = [r.formula for r in reag]
            pnames = [p.formula + ("↓" if p.kind == "precipitate" else "↑" if p.kind == "gas" else "") for p in prods]
            text = format_side(cr, rnames) + " -> " + format_side(cp, pnames)
            # energetics
            parts: list[tuple[int, float]] = []
            srcs: dict[str, str] = {}
            ok = True
            for c, r in zip(cr, reag):
                if c == 0:
                    continue
                m = nominal_species_for_reagent(system.species, r.comp, r.phase, system.aqueous)
                if m is None:
                    ok = False
                    break
                parts += [(i, -c * k) for i, k in m]
                srcs[r.formula] = "+".join(sorted({system.species[i].source for i, _ in m}))
            for c, p in zip(cp, prods):
                if c == 0:
                    continue
                pp, _ = self._participant_G(solver, p)
                parts += [(i, c * k) for i, k in pp]
                srcs[p.formula] = "+".join(sorted({system.species[i].source for i, _ in pp}))
            if ok:
                merged: dict[int, float] = {}
                for i, c in parts:
                    merged[i] = merged.get(i, 0.0) + c
                idx = [(i, c) for i, c in merged.items() if abs(c) > 1e-12]
                dG, sG, dH = _species_G(solver, idx)
                lnK = -dG / (R * T)
                K = math.exp(lnK) if abs(lnK) < 700 else None  # outside float range: see log10_K
                dS = (dH - dG) / T * 1000.0 if dH is not None else None
                main = {"equation": text, "delta_G_kJ_mol": dG, "delta_G_uncertainty": sG,
                        "delta_H_kJ_mol": dH, "delta_S_J_mol_K": dS, "equilibrium_constant": K,
                        "log10_K": -dG / (R * T * LN10), "log10_K_uncertainty": sigma_logK(sG, T),
                        "feasible": bool(dG < 0 and an.reaction_occurred), "confidence": None,
                        "parallel_reactions": parallel,
                        "energy_sources": srcs, "type": "molecular",
                        "_parts": idx, "_coef_reagents": dict(zip([r.formula for r in reag], cr)),
                        "_extent_mol": (prods[0].moles / cp[0]) if cp and cp[0] else None,
                        "_reagents": [(r.formula, c, r.moles) for r, c in zip(reag, cr)]}
            else:
                main = {"equation": text, "delta_G_kJ_mol": None, "delta_G_uncertainty": None,
                        "delta_H_kJ_mol": None, "delta_S_J_mol_K": None, "equilibrium_constant": None,
                        "feasible": an.reaction_occurred, "confidence": None, "energy_sources": srcs,
                        "type": "molecular"}
            eqs.append(main)
        return eqs, main

    def _ionic_equation(self, system: ChemSystem, an: Analysis) -> dict | None:
        if not an.reaction_occurred:
            return None
        sp = system.species
        # net change per substance; strong-acid anion HSO4- is shown as SO4(2-) + H+
        net: dict[tuple, float] = {}
        rep: dict[tuple, int] = {}
        rep_d: dict[tuple, float] = {}
        idx_of = {(s.formula, s.phase): i for i, s in enumerate(sp)}
        from .search.ranker import hydroxo_parents
        hp = hydroxo_parents(sp)
        for i, d in enumerate(an.delta):
            items = [(i, 1.0)]
            if sp[i].formula == "HSO4-" and ("SO4-2", "aq") in idx_of and ("H+", "aq") in idx_of:
                items = [(idx_of[("SO4-2", "aq")], 1.0), (idx_of[("H+", "aq")], 1.0)]
            elif i in hp and ("OH-", "aq") in idx_of:
                items = [(hp[i][0], 1.0), (idx_of[("OH-", "aq")], float(hp[i][1]))]
            for j, k in items:
                key = sp[j].key
                net[key] = net.get(key, 0.0) + k * d
                # representative species of a substance: the phase with the largest change
                if key not in rep or abs(k * d) > rep_d.get(key, 0.0):
                    rep[key] = j
                    rep_d[key] = abs(k * d)
        kH, kOH, kW = (parse_formula(f).key for f in ("H+", "OH-", "H2O"))
        if kH in net and kOH in net and kW in net and net[kH] * net[kOH] < 0:
            t = min(abs(net[kH]), abs(net[kOH]))
            sgn = 1.0 if net[kOH] > 0 else -1.0  # OH- formed while H+ consumed -> fewer H+ consumed, water formed
            net[kOH] -= sgn * t
            net[kH] += sgn * t
            net[kW] += sgn * t
        big = max([abs(v) for v in net.values()] + [1e-300])
        cons = [(rep[k], -v) for k, v in net.items() if -v > 0.01 * big]
        form = [(rep[k], v) for k, v in net.items() if v > 0.01 * big]
        if not cons or not form:
            return None
        res = balance([dict(sp[i].elements) for i, _ in cons], [sp[i].charge for i, _ in cons],
                      [dict(sp[i].elements) for i, _ in form], [sp[i].charge for i, _ in form],
                      [d for _, d in form])
        def lab(i, formed=False):
            s = sp[i]
            if not formed:
                return s.formula
            suffix = "↓" if (s.phase == "s" and system.aqueous) else "↑" if s.phase == "g" else ""
            return s.formula + suffix
        if res is None:
            txt = " + ".join(lab(i) for i, _ in cons) + " -> " + " + ".join(lab(i, True) for i, _ in form) + \
                  " (коэффициенты не подобраны)"
            return {"equation": txt, "balanced": False}
        cr, cp = res
        return {"equation": format_side(cr, [lab(i) for i, _ in cons]) + " -> " +
                            format_side(cp, [lab(i, True) for i, _ in form]), "balanced": True}

    def _composition(self, solver: _Solver, eq) -> list[dict]:
        sysm = solver.system
        rows = []
        for i, s in enumerate(sysm.species):
            n0, n1 = float(sysm.initial[i]), float(eq.n[i])
            if max(n0, n1) < 1e-10:
                continue
            rows.append({"formula": s.formula, "phase": s.phase, "initial_mol": n0, "final_mol": n1,
                         "change_mol": n1 - n0, "activity": self._activity(solver, eq, i),
                         "source": s.source})
        rows.sort(key=lambda r: -r["final_mol"])
        return rows

    def _saturation_warnings(self, solver: _Solver, eq, system: ChemSystem) -> list[str]:
        out = []
        if not system.aqueous:
            return out
        for i, s in enumerate(system.species):
            if system.kinds[i] != COND or eq.n[i] > 1e-12:
                continue
            si = self._SI(solver, eq, i)
            if -0.5 < si < 0:
                out.append(f"{s.formula}: раствор близок к насыщению (SI = {si:.2f}); возможна "
                           "кристаллизация при охлаждении или упаривании")
        return out[:5]

    def _kinetics(self, opts, cond, system: ChemSystem, an: Analysis, main_eq, eq, T):
        if opts.get("kinetics_model") == "none":
            return None
        user = opts.get("kinetics") or {}
        consumed_ions = {system.species[i].formula for i, _ in an.consumed}
        klass = barrier_mod.classify({p.kind for p in an.products}, consumed_ions)
        catalyst = cond.get("catalyst") if opts.get("include_catalysis") or (cond.get("catalyst") or {}).get("barrier_kJ_mol") else None
        info = barrier_mod.resolve(user, T, klass, catalyst)
        out = {"barrier_kJ_mol": info.barrier_kJ_mol, "rate_constant": info.rate_constant,
               "rate_constant_units": "М^-1·с^-1" if info.order >= 2 else "с^-1", "order": info.order,
               "half_life_s": None, "model": info.model, "uncertainty": info.sigma_kJ, "note": info.note,
               "requested_model": opts.get("kinetics_model"), "profile": None}
        if opts.get("kinetics_model") in ("ml_ts", "neb"):
            out["note"] = (f"Модель {opts['kinetics_model']} недоступна офлайн (нет весов/структур); "
                           + (out["note"] or ""))
        cat_txt = cat_mod.describe(cond.get("catalyst"))
        if cat_txt:
            out["catalyst"] = cat_txt
        if info.rate_constant and main_eq and main_eq.get("_reagents") and eq.water_kg >= 0:
            V = float(cond["volume_L"])
            reag = [(f, c, m) for f, c, m in main_eq["_reagents"] if c > 0]
            if reag:
                reag.sort(key=lambda x: x[2] / x[1])
                a0 = reag[0][2] / V / reag[0][1]
                b0 = (reag[1][2] / V / reag[1][1]) if len(reag) > 1 else a0
                xi_eq = (main_eq.get("_extent_mol") or 0.0) / V
                prof = integrate(info.rate_constant, info.order, a0, b0, min(xi_eq, a0, b0),
                                 n_points=max(20, int(cond["time"]["sample_points"]) * 3))
                out["half_life_s"] = prof["half_life_s"]
                out["profile"] = {"t_s": prof["t_s"], "extent_M": prof["extent_M"],
                                  "reagents": [reag[0][0]] + ([reag[1][0]] if len(reag) > 1 else [])}
                if cond["time"]["mode"] == "kinetic" and cond["time"].get("duration_s"):
                    d = float(cond["time"]["duration_s"])
                    xi_d = float(np.interp(d, prof["t_s"], prof["extent_M"]))
                    out["extent_at_duration"] = {"t_s": d, "fraction_of_equilibrium":
                                                 xi_d / xi_eq if xi_eq > 0 else None}
        return out

    def _ensemble(self, solver: _Solver, system: ChemSystem, an: Analysis, main_eq, opts, titration, eq0=None):
        size = opts.get("ensemble_size") or SIZES[opts["accuracy"]]
        sig_rt = solver.sigma
        dist = "uniform" if opts["uncertainty_method"] == "bootstrap" else "normal"
        D = draws(sig_rt, size, opts["random_seed"], dist)
        top0 = an.products[0].key if an.products else None
        amounts: dict[tuple, list[float]] = {p.key: [] for p in an.products[:10]}
        dGs: list[float] = []
        same_top = 0
        same_occ = 0
        failed = 0
        contrib = np.zeros(len(system.species))
        for k in range(size):
            try:
                # pH-stat titration is not repeated per member (cost); warm start from nominal
                eqk = solver.run(dG_shift=D[k], warm=eq0)
            except Exception:
                failed += 1
                continue
            ank = analyze(system, eqk.n)
            if ank.reaction_occurred == an.reaction_occurred:
                same_occ += 1
            topk = ank.products[0].key if ank.products else None
            if topk == top0:
                same_top += 1
            got = {p.key: p.moles for p in ank.products}
            for key in amounts:
                amounts[key].append(got.get(key, 0.0))
            if main_eq and main_eq.get("_parts"):
                G = solver.G + D[k]
                dGs.append(sum(G[i] * c for i, c in main_eq["_parts"]))
        n_ok = max(1, size - failed)
        if main_eq and main_eq.get("_parts"):
            for i, c in main_eq["_parts"]:
                contrib[i] = (c * solver.sigma[i]) ** 2
        tot = contrib.sum()
        contributions = []
        if tot > 0:
            for i in np.argsort(-contrib)[:8]:
                if contrib[i] <= 0:
                    break
                contributions.append({"species": system.species[i].label, "source": system.species[i].source,
                                      "share": float(contrib[i] / tot), "sigma_kJ": float(solver.sigma[i])})
        conf = (same_top / n_ok) if an.reaction_occurred else (same_occ / n_ok)
        return {
            "method": opts["uncertainty_method"], "members": size, "failed": failed,
            "confidence": round(float(conf), 3),
            "confidence_definition": ("доля членов ансамбля, в которых основной продукт тот же" if an.reaction_occurred
                                      else "доля членов ансамбля, в которых реакция тоже не идет"),
            "products": [{"formula": next(p.formula for p in an.products if p.key == key), **summarize(v)}
                         for key, v in amounts.items()],
            "delta_G": summarize(dGs) if dGs else None,
            "contributions": contributions,
        }

    def _temperature_scan(self, solver: _Solver, main_eq, T, cond, system, opts, titration, all_species,
                          reagents, gases, rules, P_bar, water_kg):
        out: dict[str, Any] = {"dG_T": [], "profile": []}
        if main_eq and main_eq.get("_parts"):
            for Tk in scan_range(T):
                G = 0.0
                sig2 = 0.0
                for i, c in main_eq["_parts"]:
                    g, s, _ = dGf_T(system.species[i], Tk)
                    G += c * g
                    sig2 += (c * s) ** 2
                out["dG_T"].append({"T_K": Tk, "delta_G_kJ_mol": G, "sigma": math.sqrt(sig2),
                                    "log10_K": -G / (R * Tk * LN10)})
        pts = profile_points(cond)
        if pts:
            for pt in pts:
                try:
                    sv = _Solver(system, pt["T_K"], P_bar, opts["activity_model"],
                                 solv_mod.dielectric(cond["solvent"], pt["T_K"]) if system.aqueous else None,
                                 cond["solvent"].get("ionic_strength_M") if system.aqueous else None)
                    eq = sv.run()
                    ank = analyze(system, eq.n)
                    out["profile"].append({"T_K": pt["T_K"], "t_s": pt["t_s"], "pH": self._pH(sv, eq),
                                           "products": {p.formula: p.moles for p in ank.products[:6]}})
                except Exception as e:  # noqa: BLE001
                    out["profile"].append({"T_K": pt["T_K"], "t_s": pt["t_s"], "error": str(e)})
            out["profile_note"] = ("Набор кандидатов и кинетические правила взяты при основной температуре; "
                                   "равновесие пересчитано в каждой точке профиля")
        return out


def predict(request: dict, **kw) -> Result:
    return Agent(**kw).predict(request=request)
