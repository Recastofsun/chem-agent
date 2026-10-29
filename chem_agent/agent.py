"""Orchestrator: validation -> strategy -> equilibrium -> analysis -> uncertainty -> report."""
from __future__ import annotations

import copy
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
from .parser.validator import validate, ValidationError
from .search.balance import balance, format_side
from .search.staged_balancer import staged_balance
from . import pipeline, synthesis
from .search.hypotheses import ChemSystem, build_system, nominal_species_for_reagent
from .search.ranker import KIND_RU, Analysis, ProductEntry, analyze
from .search.rules import Reagent, RuleContext, evaluate, RuleOutcome
from .thermo.activity import make_gamma_fn, validity_warning
from .thermo.equilibrium import AQ, COND, GAS, SOLVENT, EqProblem, EquilibriumError, solve
from .thermo.gibbs import R, T0, dGf_T
from .uncertainty.ensemble import SIZES, draws, summarize
from .uncertainty.propagation import sigma_logK, sigma_sum
from .utils.hashing import deterministic_uuid, sha256_of

STAGE_RU = {"dissociation": "диссоциация", "ionic": "ионная стадия", "complexation": "комплексообразование",
            "association": "ассоциация"}
SYNTH_RU = {"photochemical": "фотохимический", "sonochemical": "сонохимический",
            "hydrothermal": "гидротермальный", "mechanochemical": "механохимический",
            "sol_gel": "золь-гель"}

LN10 = math.log(10.0)


# ----------------------------------------------------------------------------- helpers
def _guess_phase(formula: str, aqueous: bool, db, T: float) -> str:
    comp = parse_formula(formula)
    cands = [s for s in db.find(comp) if s.dGf is not None]
    els = comp.as_dict
    if aqueous:
        if len(els) == 1 and comp.charge == 0:
            pass
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
                 fixed_I: float | None, voltage_V: float = 0.0):
        self.system = system
        self.T = T
        self.P_bar = P_bar
        self.voltage_V = voltage_V

        aqueous_species = [s for s in system.species if s.phase == "aq"]
        self.gamma_fn = make_gamma_fn(act_model, T, eps,
                                      species_list=aqueous_species if system.aqueous else None,
                                      db=get_db() if system.aqueous else None) if system.aqueous else None
        self.fixed_I = fixed_I

        g, sig, tdep = [], [], []
        for s in system.species:
            gg, ss, td = dGf_T(s, T)
            g.append(gg)
            sig.append(ss)
            tdep.append(td)

        self.G = np.array(g)
        self.sigma = np.array(sig)
        self.tdep = tdep

    def run(self, dG_shift: np.ndarray | None = None, b: np.ndarray | None = None, warm=None):
        G = self.G if dG_shift is None else self.G + dG_shift

        fixed_lambda = None
        if self.voltage_V > 0 and self.system.charge_col is not None:
            F = 96485.332
            R_gas = 8.31446
            fixed_lambda = {self.system.charge_col: -F * self.voltage_V / (R_gas * self.T)}

        p = EqProblem(A=self.system.A, g=G / (R * self.T), kind=self.system.kinds,
                      b=self.system.b if b is None else b,
                      charges=np.array([s.charge for s in self.system.species], dtype=float),
                      P_bar=self.P_bar, gamma_fn=self.gamma_fn, fixed_I=self.fixed_I,
                      charge_col=self.system.charge_col,
                      warm=None if warm is None else (warm.lam, warm.n, warm.water_kg / 0.018015268, warm.gas_total),
                      fixed_lambda=fixed_lambda)
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
    P_OPEN_DRY = 1e-6  # бар: открытая сухая система, газообразные продукты уходят
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
            request = {}

        raw = {
            "reagents": request.get("reagents") or reagents or [],
            "conditions": request.get("conditions") or conditions or {},
            "known_energies": request.get("known_energies") or known_energies or {},
            "constraints": request.get("constraints") or constraints or {},
            "options": request.get("options") or options or {}
        }
        if "cell" in request:          
            raw["cell"] = request["cell"]
        try:
            req, warnings = validate(raw)
        except ValidationError as e:
            return Result({"status": "error", "message": str(e)})

        if req.get("mode") == "cell":
            return Result(self._run_cell(req, warnings))

        opts = {**self.config.get("options", {}), **raw["options"]}
        raw["options"] = opts
        out = self._run(copy.deepcopy(raw))
        zone = (out.get("synthesis") or {}).get("zone")
        if zone and out.get("status") not in ("error", "unknown"):
            zraw = synthesis.zone_request(raw, zone)  # горячие точки метода синтеза (W-06, W-08)
            if zraw is not None:
                hot = self._run(zraw)
                if hot.get("status") not in ("error", "unknown"):
                    out = synthesis.merge_zone(out, hot, zone)
        return Result(out)

    # --- НОВЫЙ МЕТОД ДЛЯ ДВУХКАМЕРНОЙ ЯЧЕЙКИ -----------------------------------
    def _run_cell(self, req: dict, warnings: list[str]) -> dict:
        from .thermo.constrained_lagrange import solve_kkt
        from .electrochem.kinetics import select_dominant_reaction

        cell = req["cell"]
        T = 298.15
        if req.get("conditions") and req["conditions"].get("temperature_K"):
            T = float(req["conditions"]["temperature_K"])

        circuit = cell.get("external_circuit", {})
        U = circuit.get("voltage_V", 2.0)
        duration_s = circuit.get("duration_s", 3600)
        
        F = 96485.332
        area = cell.get("membrane", {}).get("area_m2", 0.01)
        
        if circuit.get("mode") == "galvanostatic":
            current = circuit.get("current_density_A_m2", 100) * area
        else:
            current = 100 * area
            
        max_electrons = (current * duration_s) / F

        def solve_chamber(side_name: str, side_potential: float):
            side = cell[side_name]
            sol = side["solution"]
            species_list = sol["species"]
            volume_L = sol.get("volume_L", 1.0)
            water_kg = volume_L

            # А) Строим начальную систему
            reagents_list = [
                Reagent(r["formula"], parse_formula(r["formula"]), r["moles"], r.get("phase", "aq"))
                for r in species_list
            ]
            ctx = RuleContext(T=T, aqueous=True, reagents=reagents_list, volume_L=volume_L, voltage_V=abs(side_potential))
            rules = evaluate(ctx, set())
            resolver = EnergyResolver.from_request(self.db, {}, species_list, "auto")
            all_species = resolver.apply(self.db.species, True)
            
            sys_chamber = build_system(all_species, reagents_list, T=T, P_bar=1.0, aqueous=True, water_kg=water_kg, rules=rules)
            if not sys_chamber.species:
                return None, False, sys_chamber

            # Б) СНАЧАЛА СЧИТАЕМ РАВНОВЕСИЕ (чтобы получить реальные ионы)
            g0_init = np.array([dGf_T(s, T)[0] / (R * T) for s in sys_chamber.species])
            charges_init = np.array([s.charge for s in sys_chamber.species])
            n_eq_init, _, ok_init = solve_kkt(
                sys_chamber.A, sys_chamber.b, g0_init, charges_init, 
                phi=0.0, T=T, kinds=sys_chamber.kinds, 
                charge_col=sys_chamber.charge_col, gamma_fn=None, max_iter=200
            )
            
            if n_eq_init is None:
                return None, False, sys_chamber

            # Теперь concentrations - это реальные ионы (Cu+2, Cl-, H+ и т.д.)
            concentrations = {s.formula: float(n_eq_init[i]) / volume_L for i, s in enumerate(sys_chamber.species)}
            
            # В) ВЫБИРАЕМ РЕАКЦИЮ (Нернст + Батлер-Фольмер)
            dominant = select_dominant_reaction(self.db, U=abs(side_potential), concentrations=concentrations, T=T, side=side_name)
            
            if dominant is None:
                warnings.append(f"{side_name}: доминирующая реакция не найдена (напряжения недостаточно).")
                return n_eq_init, ok_init, sys_chamber

            # Г) ФИКС: Принудительно добавляем продукты, даже если правила их запрещали
            for p_formula in [dominant["ox"], dominant["red"]]:
                p_key = parse_formula(p_formula).key
                rules.forbid_new.discard(p_key)
                
                if p_formula not in [s.formula for s in sys_chamber.species]:
                    sp_db = self.db.find_formula(p_formula)
                    phase = sp_db[0].phase if sp_db else ("g" if p_formula in ("H2", "O2", "Cl2") else "aq")
                    reagents_list.append(Reagent(p_formula, parse_formula(p_formula), 0.0, phase))

            # Пересобираем систему с продуктами
            sys_chamber = build_system(all_species, reagents_list, T=T, P_bar=1.0, aqueous=True, water_kg=water_kg, rules=rules)

            # Д) Считаем равновесие с новыми продуктами
            g0 = np.array([dGf_T(s, T)[0] / (R * T) for s in sys_chamber.species])
            charges = np.array([s.charge for s in sys_chamber.species])
            n_eq, lam, ok = solve_kkt(sys_chamber.A, sys_chamber.b, g0, charges, phi=0.0, T=T, kinds=sys_chamber.kinds, charge_col=sys_chamber.charge_col, gamma_fn=None, max_iter=200)
            
            if n_eq is None:
                return None, False, sys_chamber

            # Е) ПРИМЕНЯЕМ ЗАКОН ФАРАДЕЯ
            n_final = n_eq.copy()
            
            ox_idx = next((i for i, s in enumerate(sys_chamber.species) if s.formula == dominant["ox"]), None)
            red_idx = next((i for i, s in enumerate(sys_chamber.species) if s.formula == dominant["red"]), None)
            h2o_idx = next((i for i, s in enumerate(sys_chamber.species) if s.formula == "H2O" and s.phase == "l"), None)
            oh_idx = next((i for i, s in enumerate(sys_chamber.species) if s.formula == "OH-" and s.phase == "aq"), None)
            
            n_e = dominant["n"]
            xi = max_electrons / n_e

            if side_name == "anode" and red_idx is not None:
                max_xi = float(n_eq[red_idx]) / 1.0
                xi = min(xi, max_xi)
                n_final[red_idx] = max(0, n_final[red_idx] - xi)
                if ox_idx is not None:
                    n_final[ox_idx] += xi
                    
            elif side_name == "cathode":
                if dominant["red"] == "H2":
                    if h2o_idx is not None:
                        xi = min(xi, n_final[h2o_idx] / 2.0)
                    if red_idx is not None:
                        n_final[red_idx] += xi
                    if oh_idx is not None:
                        n_final[oh_idx] += 2 * xi
                    if h2o_idx is not None:
                        n_final[h2o_idx] -= 2 * xi
                elif ox_idx is not None:
                    max_xi = float(n_eq[ox_idx]) / 1.0
                    xi = min(xi, max_xi)
                    n_final[ox_idx] = max(0, n_final[ox_idx] - xi)
                    if red_idx is not None:
                        n_final[red_idx] += xi

            sys_chamber.initial = n_eq
            return n_final, True, sys_chamber

        # Анод (-U), Катод (+U)
        n_anode, ok_anode, sys_anode = solve_chamber("anode", -U)
        n_cathode, ok_cathode, sys_cathode = solve_chamber("cathode", U)

        def summarize(n_arr, sys_obj, ok):
            if not ok or n_arr is None:
                return {"converged": False, "species": []}
            out = []
            for i, s in enumerate(sys_obj.species):
                if n_arr[i] > 1e-4:
                    out.append({
                        "formula": s.formula,
                        "phase": s.phase,
                        "moles": float(n_arr[i]),
                    })
            out.sort(key=lambda x: -x["moles"])
            return {"converged": True, "species": out}

        return {
            "status": "ok" if (ok_anode and ok_cathode) else "error",
            "mode": "cell",
            "cell_result": {
                "anode": summarize(n_anode, sys_anode, ok_anode),
                "cathode": summarize(n_cathode, sys_cathode, ok_cathode),
            },
            "warnings": warnings,
        }

    # core ------------------------------------------------------------------------
    def _run(self, raw: dict) -> dict:
        t_start = time.perf_counter()
        req, warnings = validate(raw)

        req["conditions"] = req.get("conditions") or {}
        req["options"] = req.get("options") or {}
        req["constraints"] = req.get("constraints") or {}
        req["known_energies"] = req.get("known_energies") or {}
        req["reagents"] = req.get("reagents") or []

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

        ph = cond.get("pH") or {}
        titration = None
        if aqueous and ph.get("initial") is not None and not ph.get("buffered"):
            tr = ph_mod.titrant_for_initial_pH(ph["initial"], water_kg)
            if tr:
                reagents.append(Reagent(tr[0], parse_formula(tr[0]), tr[1], "aq"))
                warnings.append(f"Начальный pH {ph['initial']} задан добавкой {tr[1]:.3g} моль {tr[0]} к растворителю до смешивания реагентов")
        if aqueous and ph.get("initial") is not None and ph.get("buffered"):
            titration = float(ph["initial"])
            for f in ("HCl", "NaOH"):
                reagents.append(Reagent(f, parse_formula(f), 1e-12, "aq"))
            warnings.append(f"Буферный режим: pH поддерживается равным {titration} добавкой HCl/NaOH (pH-стат)")

        gases, atm_notes = atm_mod.gas_amounts(cond, T, bool(opts.get("include_atmosphere", True)))
        warnings.extend(atm_notes)

        electrolysis = cond.get("electrolysis") or {}
        voltage_V = float(electrolysis.get("voltage_V", 0.0)) if electrolysis.get("enabled") else 0.0
        if voltage_V > 0:
            warnings.append(f"Включен электролиз: приложено напряжение {voltage_V} В.")

        synth = synthesis.analyze(cond.get("method"), reagents, T, cond)
        if synth:
            warnings.extend(synth["notes"])
        is_open = (cond.get("atmosphere") or {}).get("mode") in ("open", "fixed")
        ctx = RuleContext(T=T, aqueous=aqueous, reagents=reagents, volume_L=float(cond["volume_L"]),
                          atmosphere_species=[parse_formula(f) for f in gases], open_system=is_open,
                          voltage_V=voltage_V,
                          catalyst=bool((cond.get("catalyst") or {}).get("formula")),
                          initiated=bool(synth and synth.get("initiated")))
        rules = evaluate(ctx, set(opts.get("disabled_rules") or []))

        resolver = EnergyResolver.from_request(self.db, req.get("known_energies"), req["reagents"],
                                               opts["energy_source"])
        all_species = resolver.apply(self.db.species, aqueous)
        warnings.extend(resolver.warnings)

        system = build_system(all_species, reagents, T=T, P_bar=P_bar, aqueous=aqueous, water_kg=water_kg,
                              rules=rules, atmosphere=gases, forbidden_products=cons.get("forbidden_products"),
                              allowed_products=synthesis.sol_gel.allowed_keys(synth),
                              extra_forbidden_keys=synthesis.sol_gel.forbidden_keys(synth, all_species))
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
        if voltage_V > 0 and aqueous:  # W-15: электролиз - последовательные полуреакции, не равновесие
            return self._electrolysis(base, reagents, water_kg, T, voltage_V, electrolysis, explanation, t_start)
        if system.inert:
            warnings.append("Не участвуют в реакции (кинетика): " + ", ".join(r.formula for r in system.inert))

        eps = solv_mod.dielectric(cond["solvent"], T) if aqueous else None
        fixed_I = cond["solvent"].get("ionic_strength_M") if aqueous else None

        atm = cond.get("atmosphere") or {}
        is_open = atm.get("mode") in ("open", "fixed")
        if voltage_V > 0:
            is_open = True
        if atm.get("headspace_L", 0) > 100.0:
            is_open = True
        # Открытая сухая система (прокаливание в тигле) или открытая без состава воздуха:
        # продукты-газы уходят (P -> 0), KNO3 -> KNO2 + O2 (h054).
        # Раствор под заданной атмосферой: открытость задана большим газовым пространством
        # (atmosphere.gas_amounts), давление реальное, иначе CO2/O2 воздуха не растворяются.
        P_bar_solver = self.P_OPEN_DRY if is_open and (not gases or not aqueous) else P_bar

        solver = _Solver(system, T, P_bar_solver, opts["activity_model"], eps, fixed_I, voltage_V=voltage_V)
        if P_bar_solver < 1e-3:
            self._no_sublimation(solver, warnings)
        self._self_equilibrated_initial(solver, system)
        methods += ["Gibbs minimization (dual barrier + Newton)", "CRC Handbook", "NBS-1982"]
        if aqueous:
            act_names = {
                "ideal": "ideal",
                "debye_huckel": "Debye-Huckel (extended)",
                "davies": "Davies",
                "pitzer": "Pitzer (Harvie-Moller-Weare 1984)",
                "sit": "SIT (Specific Ion Interaction)"
            }
            methods.append(act_names.get(opts["activity_model"], opts["activity_model"]))
        if any(s.source.startswith("user") for s in system.species):
            methods.append("user energies")
        if synth and synth.get("initiated"):
            methods.append("Photochemical initiation (photolysis threshold hc/λ)")

        # Pipeline (W-04): этапы диссоциация -> комплексы -> осаждение -> газ -> финал.
        # Финал - полный расчет, как без Pipeline; этапы нужны для отчета (detailed) и для тупика.
        pipe = pipeline.run(solver, lambda warm: self._equilibrium(solver, titration, warm), opts["pipeline_mode"])
        base["pipeline"] = pipe.report
        if pipe.status == "unknown":
            base["status"] = "unknown"
            base["message"] = ("неизвестно: равновесие не найдено ни прямым расчетом, ни по этапам Pipeline"
                               + (f" ({pipe.error})" if pipe.error else ""))
            base["warnings"].append(base["message"])
            base["metadata"]["compute_time_s"] = round(time.perf_counter() - t_start, 3)
            return base
        eq, b_used = pipe.eq, pipe.b_used
        if b_used is not None:
            self._register_titrant(solver, system, b_used, titration, eq, warnings)
        if pipe.report.get("fallback") == "warm_restart":
            warnings.append("Полный расчет равновесия не сошелся с нуля: повторен от состава этапов Pipeline")
        n = eq.n
        for m in eq.messages:
            warnings.append(m)

        if rules.no_reaction:  # правило gas_mix_no_igniter (rules.yaml)
            warnings.append("Смесь газов при T < 700 K без катализатора не реагирует самопроизвольно(нужна искра, пламя или освещение): реакция считается не идущей")
        an = analyze(system, n)
        if rules.no_reaction:
            an.reaction_occurred = False
            an.products = []
        products = self._products(solver, an, eq, cons)
        equations, main_eq = self._equations(solver, system, an, T)
        ionic = self._ionic_equation(system, an)
        if an.reaction_occurred and main_eq is None:
            if voltage_V > 0:
                warnings.append("Электролиз: уравнение не сбалансировано из-за параллельных процессов, но продукты определены.")
            else:
                warnings.append("Не удалось подобрать коэффициенты уравнения (возможно, параллельные реакции). Смотрите таблицу продуктов")
        if main_eq and main_eq.get("parallel_reactions"):
            warnings.append("Идут параллельные реакции: уравнение описывает только основную; полный итог - в таблице равновесного состава")
        reliability: list[str] = []
        if not eq.converged:
            if not an.reaction_occurred and eq.residual < 1e-2:
                warnings.append(f"Расчет равновесия имеет небольшую невязку ({eq.residual:.1e}), но реакция не идет.")
            elif voltage_V > 0:
                if an.reaction_occurred:
                    warnings.append("Электролиз: расчет имеет высокую невязку из-за экстремальных сдвигов энергий, но продукты определены.")
                else:
                    reliability.append("расчет не сошелся (возможно, напряжение слишком высокое для данной модели)")
            else:
                reliability.append("расчет равновесия не сошелся с нужной точностью (невязка баланса "
                                   f"{eq.residual:.1e})")
        if aqueous:
            limits = {"ideal": 0.1, "debye_huckel": 0.5, "davies": 1.0, "sit": 6.0, "pitzer": 20.0}
            max_I = limits.get(opts["activity_model"], 1.0)
            if eq.ionic_strength > max_I:
                reliability.append(f"ионная сила {eq.ionic_strength:.1f} моль/кг: модель '{opts['activity_model']}' не применима (лимит {max_I} М)")
        if synth and synth.get("water_state") == "supercritical":
            reliability.append("сверхкритическая вода: модели жидкой воды не применимы")
        if aqueous and "минус объем" in water_note and water_kg <= 0.05 * float(cond["volume_L"]) * 1.001:
            reliability.append("растворенные вещества занимают почти весь объем: оценка массы воды не работает, "
                               "задайте conditions.water_kg")
        if abs(T - T0) > 10:
            no_t = sorted({s.formula for i, s in enumerate(system.species)
                           if not solver.tdep[i] and (eq.n[i] > 1e-6 or system.initial[i] > 0)})
            if no_t:
                warnings.append("Нет ΔfH, зависимость от температуры не учтена для: " + ", ".join(no_t[:10]))
        explanation.append({"step": "Генерация гипотез и равновесие",
                            "text": f"Минимизация энергии Гиббса при T = {T:.2f} K, P = {P_bar:.4g} бар. "
                                    f"Итераций: {eq.iterations}, невязка баланса масс {eq.residual:.1e}."})
        for rf in rules.fired:
            explanation.append({"step": f"Правило: {rf['title']}", "text": rf["why"], "rule": rf["id"]})
        if opts["pipeline_mode"] == "detailed":
            explanation.extend(pipeline.explain(pipe.report))
            for e in equations:
                for st in e.get("stages") or []:
                    explanation.append({"step": f"Стадия уравнения ({STAGE_RU.get(st['stage'], st['stage'])})",
                                        "text": st["equation"]})

        if synth:
            explanation.append({"step": f"Метод синтеза: {SYNTH_RU.get(synth['method'], synth['method'])}",
                                "text": "; ".join(synth["notes"])})
            if synth.get("initiated") and not an.reaction_occurred:
                warnings.append("Фотолиз идет, но равновесие не сдвигается: продукты эндергоничны и рекомбинируют "
                                "в темноте. Фотостационарное состояние равновесная модель не описывает")
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

        kinetics = self._kinetics(opts, cond, system, an, main_eq, eq, T) if opts.get("include_kinetics") else None

        unc = None
        confidence = None
        if opts.get("include_uncertainty") and opts["uncertainty_method"] != "none":
            unc = self._ensemble(solver, system, an, main_eq, opts, titration, eq)
            confidence = unc["confidence"]
            methods.append("Monte Carlo ensemble" if opts["uncertainty_method"] == "ensemble" else "bootstrap (uniform)")
        if main_eq is not None:
            main_eq["confidence"] = confidence if confidence is not None else None
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
            "synthesis": synth,
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
        if opts.get("separation"):  # W-13: разделение равновесного состава
            from .separation import separate
            base["separation"] = separate(base, opts["separation"], self.db)
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

    @staticmethod
    def _no_sublimation(solver: _Solver, warnings: list) -> None:
        """W-16: открытая сухая система считается при P -> 0, чтобы газообразные продукты уходили (h054).
        Но при P -> 0 испаряется и все нелетучее: KCl при 900 K, Ag при 1000 K. Газовая форма вещества,
        у которого есть твердая или жидкая запись, исключается, если давление его пара при T ниже 1e-3 бар
        (0,02 моль в газовом пространстве 1000 л при 900 K - это 1,5e-3 бар): за время опыта такое вещество
        не улетучивается. Летучие (H2O, Hg, S, I2, NH3) остаются."""
        species = solver.system.species
        cond = {}
        for j, s in enumerate(species):
            if s.phase in ("s", "l"):
                cond[s.key] = min(cond.get(s.key, np.inf), solver.G[j])
        dropped = []
        for i, s in enumerate(species):
            if s.phase == "g" and s.key in cond:
                ln_p = -(solver.G[i] - cond[s.key]) / (R * solver.T)
                if ln_p < np.log(1e-3):
                    solver.G[i] += 300.0 * R * solver.T
                    dropped.append(s.formula)
        if dropped:
            warnings.append("Открытая система: нелетучие вещества не испаряются (давление пара < 1e-3 бар): "
                            + ", ".join(sorted(set(dropped))))

    def _electrolysis(self, base, reagents, water_kg, T, voltage_V, el, explanation, t_start) -> dict:
        from .electrochem.electrolysis import plan
        from .search.staged_balancer import decompose
        pl = plan(reagents, water_kg, T, voltage_V, self.db, el.get("current_A"), el.get("duration_s"))
        base["warnings"].extend(pl.notes)
        explanation.append({"step": "Электролиз", "text": "; ".join(pl.notes)})
        base["explanation"] = explanation
        base["metadata"]["methods_used"] = ["Electrolysis: half-reaction selection (Nernst + overpotential), Faraday"]

        def g_of(formula, phase):
            c = parse_formula(formula)
            if phase == "aq":
                parts = decompose(c.key) if c.charge == 0 else {c.key: 1.0}
                tot = 0.0
                for k, n in parts.items():
                    sp_ = [x for x in self.db.species if x.key == k and x.phase == "aq"]
                    if not sp_:
                        return None, ""
                    tot += n * sp_[0].dGf
                return tot, "CRC"
            sp_ = ([x for x in self.db.species if x.key == c.key and x.phase == phase]
                   or [x for x in self.db.species if x.key == c.key])
            return (sp_[0].dGf, sp_[0].source) if sp_ else (None, "")

        if not pl.ok:
            base.update({"status": "no_reaction", "message": "Электролиз не идет при заданном напряжении",
                         "products": [], "balanced_equations": [], "final_composition": [],
                         "summary": {"main_product": None, "main_product_kind": None, "delta_G_kJ_mol": None,
                                     "delta_G_uncertainty": None, "confidence": None, "reaction_occurred": False,
                                     "pH": None, "ionic_strength_M": None},
                         "rules_fired": [], "electrolysis": {"U_decomposition_V": pl.U_decomp_V}})
            base["metadata"]["compute_time_s"] = round(time.perf_counter() - t_start, 3)
            return base
        kinds = {"s": "precipitate", "g": "gas", "aq": "salt_solution", "l": "liquid"}
        products = []
        for f, ph, n in pl.products:
            g, src = g_of(f, ph)
            c = parse_formula(f)
            products.append({"formula": f, "name_ru": russian_name(c), "phase": ph, "kind": kinds[ph],
                             "kind_ru": KIND_RU[kinds[ph]], "moles": n, "mass_g": c.molar_mass() * n,
                             "delta_Gf_kJ_mol": g, "uncertainty": None, "source": src, "activity": None,
                             "saturation_index": None, "score": None})
        # уравнение: реагенты (нули допустимы) + H2O -> продукты
        reac = [(r.formula, r.comp, r.phase) for r in reagents]
        if pl.consumed.get("H2O", 0) > 1e-12:
            reac.append(("H2O", parse_formula("H2O"), "l"))
        rc = [dict(c.elements) for _, c, _ in reac]
        pc = [dict(parse_formula(f).elements) for f, _, _ in pl.products]
        st = staged_balance(rc, [0] * len(rc), pc, [0] * len(pc), [n for _, _, n in pl.products],
                            reac_names=[f for f, _, _ in reac], prod_names=[f for f, _, _ in pl.products], main=0)
        eqs, main_eq = [], None
        if st is not None:
            pn = [f + ("↓" if ph == "s" else "↑" if ph == "g" else "") for f, ph, _ in pl.products]
            text = format_side(st.reactants, [f for f, _, _ in reac]) + " -> " + format_side(st.products, pn)
            dG = 0.0
            for (f, _, ph), k in zip(reac, st.reactants):
                g, _ = g_of(f, ph)
                dG = None if g is None or dG is None else dG - k * g
            for (f, ph, _), k in zip(pl.products, st.products):
                g, _ = g_of(f, ph)
                dG = None if g is None or dG is None else dG + k * g
            main_eq = {"equation": text, "delta_G_kJ_mol": dG, "delta_G_uncertainty": None, "delta_H_kJ_mol": None,
                       "delta_S_J_mol_K": None, "equilibrium_constant": None, "feasible": True, "confidence": None,
                       "energy_sources": {}, "type": "molecular", "balancer": "electrolysis", "stages": [
                           {"stage": "cathode", "equation": f"{pl.cathode.species} -> {pl.cathode.product}"},
                           {"stage": "anode", "equation": f"{pl.anode.species} -> {pl.anode.product}"}],
                       "parallel_reactions": False}
            if dG is not None and dG > 0:
                base["warnings"].append(f"ΔG процесса +{dG:.0f} кДж/моль: идет только за счет работы тока "
                                        f"({pl.n_e:.3g} моль e-)")
            eqs.append(main_eq)
        rows = []
        init: dict[tuple, float] = {}
        for r in reagents:
            for k, n in decompose(r.comp.key).items():
                key = (display_formula(Composition(k[0], k[1])), "aq")
                init[key] = init.get(key, 0.0) + n * r.moles
        for (f, ph), n in init.items():
            fin = max(n - pl.consumed.get(f, 0.0), 0.0)
            rows.append({"formula": f, "phase": ph, "initial_mol": n, "final_mol": fin,
                         "change_mol": fin - n, "activity": None, "source": "CRC"})
        for f, ph, n in pl.products:
            rows.append({"formula": f, "phase": ph, "initial_mol": 0.0, "final_mol": n, "change_mol": n,
                         "activity": None, "source": "electrolysis"})
        base.update({
            "status": "ok", "message": None, "balanced_equations": eqs, "ionic_equation": None,
            "products": products, "final_composition": rows, "kinetics": None, "uncertainty": None, "thermo": None,
            "rules_fired": [],
            "electrolysis": {"cathode": dict(pl.cathode.__dict__), "anode": dict(pl.anode.__dict__),
                             "U_decomposition_V": pl.U_decomp_V, "n_electrons_mol": pl.n_e,
                             "charge_C": pl.n_e * 96485.332},
        })
        base["summary"] = {"main_product": products[0]["formula"], "main_product_kind": products[0]["kind"],
                           "delta_G_kJ_mol": main_eq["delta_G_kJ_mol"] if main_eq else None,
                           "delta_G_uncertainty": None, "confidence": None, "reaction_occurred": True,
                           "pH": None, "ionic_strength_M": None}
        base["metadata"]["compute_time_s"] = round(time.perf_counter() - t_start, 3)
        return base

    def _self_equilibrated_initial(self, solver: _Solver, system: ChemSystem) -> None:
        if not system.aqueous or len(system.reagents) < 2:
            return
        from .search.hypotheses import species_components
        share = system.water_mol
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
            except Exception:
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

    def _equilibrium(self, solver: _Solver, titration: float | None, warm=None):
        if titration is None:
            return solver.run(warm=warm), None
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
        prods = prods[:8]

        if solver.voltage_V > 0:
            prods = [p for p in prods if p.formula not in ("H+", "OH-")]

        reag = []
        for r in system.reagents:
            if r.moles <= 1e-10:
                continue
            same = next((x for x in reag if x.comp.key == r.comp.key), None)
            if same:
                same.moles += r.moles
            else:
                reag.append(Reagent(r.formula, r.comp, r.moles, r.phase))
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
        stages = None
        if res is None:  # W-02: стадии через промежуточные частицы
            st = staged_balance(rc, rq, pc, pq, [p.moles for p in prods],
                                reac_names=[r.formula for r in reag], prod_names=[p.formula for p in prods],
                                reac_dissolved=[r.phase == "aq" for r in reag],
                                prod_dissolved=[p.kind in ("salt_solution", "ion", "molecule_aq") for p in prods])
            if st is not None:
                res = (st.reactants, st.products)
                stages = st.stages
                parallel = any(prods[j].moles >= 0.1 * prods[0].moles for j in st.dropped_products)
        wi = next((i for i, k in enumerate(system.kinds) if k == SOLVENT), None)
        if res is None and wi is not None and wkey not in pkeys:
            # вода как продукт относительно реагентов в исходной форме: 2 Al(OH)3 + 2 SiO2 -> каолинит + H2O.
            # net по воде считается от самоуравновешенного начального состава (Al(OH)3 -> Al2O3 + H2O при 473 K)
            # и может показать ее расход, хотя относительно заданных реагентов вода выделяется
            w = ProductEntry("H2O", "l", "molecule", 0.0, wkey, species_idx=[wi])
            st = staged_balance(rc, rq, pc + [dict(wkey[0])], pq + [0], [p.moles for p in prods] + [0.0],
                                reac_names=[r.formula for r in reag], prod_names=[p.formula for p in prods] + ["H2O"],
                                reac_dissolved=[r.phase == "aq" for r in reag],
                                prod_dissolved=[p.kind in ("salt_solution", "ion", "molecule_aq") for p in prods] + [False])
            if st is not None:
                prods = prods + [w]
                res = (st.reactants, st.products)
                stages = st.stages
                parallel = any(prods[j].moles >= 0.1 * prods[0].moles for j in st.dropped_products if j < len(prods) - 1)
        eqs = []
        main = None
        if res is not None:
            cr, cp = res
            rnames = [r.formula for r in reag]
            pnames = [p.formula + ("↓" if p.kind == "precipitate" else "↑" if p.kind == "gas" or p.phase == "g" else "") for p in prods]
            text = format_side(cr, rnames) + " -> " + format_side(cp, pnames)
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
                K = math.exp(lnK) if abs(lnK) < 700 else None
                dS = (dH - dG) / T * 1000.0 if dH is not None else None
                main = {"equation": text, "delta_G_kJ_mol": dG, "delta_G_uncertainty": sG,
                        "delta_H_kJ_mol": dH, "delta_S_J_mol_K": dS, "equilibrium_constant": K,
                        "log10_K": -dG / (R * T * LN10), "log10_K_uncertainty": sigma_logK(sG, T),
                        "feasible": bool(dG < 0 and an.reaction_occurred), "confidence": None,
                        "parallel_reactions": parallel,
                        "energy_sources": srcs, "type": "molecular",
                        "balancer": "staged" if stages else "direct", "stages": stages,
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
                if key not in rep or abs(k * d) > rep_d.get(key, 0.0):
                    rep[key] = j
                    rep_d[key] = abs(k * d)
        kH, kOH, kW = (parse_formula(f).key for f in ("H+", "OH-", "H2O"))
        if kH in net and kOH in net and kW in net and net[kH] * net[kOH] < 0:
            t = min(abs(net[kH]), abs(net[kOH]))
            sgn = 1.0 if net[kOH] > 0 else -1.0
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
        if res is None:  # W-02
            st = staged_balance([dict(sp[i].elements) for i, _ in cons], [sp[i].charge for i, _ in cons],
                                [dict(sp[i].elements) for i, _ in form], [sp[i].charge for i, _ in form],
                                [d for _, d in form], reac_names=[sp[i].formula for i, _ in cons],
                                prod_names=[sp[i].formula for i, _ in form],
                                reac_dissolved=[False] * len(cons), prod_dissolved=[False] * len(form),
                                main=max(range(len(form)), key=lambda j: form[j][1]))
            if st is not None:
                res = (st.reactants, st.products)
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
        model_note = None
        if opts.get("kinetics_model") in ("marcus", "bep"):  # W-10: барьер из ΔG/ΔH основной реакции
            user, model_note = self._model_barrier(opts["kinetics_model"], user, main_eq)
        info = barrier_mod.resolve(user, T, klass, catalyst)
        if model_note:
            info.model, info.note = model_note
        out = {"barrier_kJ_mol": info.barrier_kJ_mol, "rate_constant": info.rate_constant,
               "rate_constant_units": "М⁻¹·с⁻¹" if info.order >= 2 else "с⁻¹", "order": info.order,
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

    @staticmethod
    def _model_barrier(model: str, user: dict, main_eq) -> tuple[dict, tuple[str, str] | None]:
        from .kinetics import bep, marcus
        user = dict(user)
        if model == "marcus":
            lam = user.get("lambda_kJ_mol")
            dG = (main_eq or {}).get("delta_G_kJ_mol")
            if lam is None or dG is None:
                return user, ("Marcus", "Нужны options.kinetics.lambda_kJ_mol и уравнение с ΔG; барьер не рассчитан")
            n = int(user.get("n_electrons", 1))
            user["barrier_kJ_mol"] = marcus.barrier(float(lam), float(dG), n)
            inv = " (инвертированная область: -ΔG° > λ)" if marcus.inverted(float(lam), float(dG), n) else ""
            return user, ("Marcus (внешнесферный перенос электрона)",
                          f"ΔG‡ = λ/4·(1 + ΔG°/λ)², λ = {float(lam):g}, ΔG° = {float(dG) / n:.1f} кДж/моль на e{inv}; "
                          "работа сближения не учтена")
        a, b = user.get("alpha"), user.get("beta_kJ_mol")
        dH = (main_eq or {}).get("delta_H_kJ_mol")
        if a is None or b is None or dH is None:
            return user, ("BEP", "Нужны options.kinetics.alpha, beta_kJ_mol и уравнение с ΔH; барьер не рассчитан")
        user["barrier_kJ_mol"] = bep.barrier(float(a), float(b), float(dH))
        return user, ("BEP (Белл-Эванс-Поляни)", f"Ea = {float(a):g}·ΔH + {float(b):g}, ΔH = {float(dH):.1f} кДж/моль; "
                      "параметры α, β - для семейства реакций, заданы пользователем")

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
                except Exception as e:
                    out["profile"].append({"T_K": pt["T_K"], "t_s": pt["t_s"], "error": str(e)})
            out["profile_note"] = ("Набор кандидатов и кинетические правила взяты при основной температуре; "
                                   "равновесие пересчитано в каждой точке профиля")
        return out


def predict(request: dict, **kw) -> Result:
    return Agent(**kw).predict(request=request)