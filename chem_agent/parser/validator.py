"""Input validation and defaults (schema from ТЗ, section 6)."""
from __future__ import annotations

import copy
import os
from typing import Any

from .formula import FormulaError, parse_formula

ACCURACY = ("fast", "balanced", "accurate")
ENERGY_SOURCES = ("auto", "db_only", "ml_only", "dft_only")
ACTIVITY = ("ideal", "debye_huckel", "davies", "pitzer", "sit")
KINETICS = ("none", "eyring", "ml_ts", "neb", "butler_volmer", "marcus", "bep")
UNCERTAINTY = ("ensemble", "bootstrap", "none")
PIPELINE = ("compact", "detailed")

DEFAULT_OPTIONS = {
    "accuracy": "balanced", "explain": True, "include_kinetics": True, "include_uncertainty": True,
    "output_formats": ["json"], "language": "ru", "theme": "light", "output_dir": None,
    "energy_source": "auto", "activity_model": None, "thermo_model": "extended",
    "kinetics_model": "eyring", "uncertainty_method": "ensemble", "max_reaction_steps": 3,
    "include_solvent_effects": True, "include_atmosphere": True, "include_catalysis": False,
    "device": "auto", "num_workers": max(1, (os.cpu_count() or 2) // 2), "random_seed": 42,
    "ensemble_size": None, "pipeline_mode": "compact", "separation": None,
}

DEFAULT_CONDITIONS = {
    "temperature_K": 298.15, "temperature_profile": None, "pressure_atm": 1.0, "volume_L": None,
    "water_kg": None,
    "solvent": None, "pH": None, "atmosphere": None, "mixing": None, "catalyst": None,
    "time": {"mode": "equilibrium", "duration_s": None, "sample_points": 10},
    "electrolysis": None, "method": None,
}

DEFAULT_CONSTRAINTS = {"forbidden_products": [], "max_products": 10, "max_reaction_steps": 3,
                       "require_balance": True, "require_charge_balance": True}


class ValidationError(ValueError):
    pass


def _num(v, name, lo=None, hi=None, allow_none=False):
    if v is None and allow_none:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{name}: ожидалось число, получено {v!r}")
    if lo is not None and x < lo:
        raise ValidationError(f"{name}: значение {x} меньше допустимого {lo}")
    if hi is not None and x > hi:
        raise ValidationError(f"{name}: значение {x} больше допустимого {hi}")
    return x


def _validate_solution(sol: dict, side_name: str) -> tuple[dict, list[str]]:
    """Валидирует раствор в одной камере (анод или катод)."""
    warnings = []
    if not isinstance(sol, dict):
        raise ValidationError(f"cell.{side_name}.solution должен быть объектом")

    solvent = sol.get("solvent", "water")
    if isinstance(solvent, str):
        solvent = {"name": solvent}
    if not isinstance(solvent, dict):
        raise ValidationError(f"cell.{side_name}.solution.solvent должен быть строкой или объектом")
    name = str(solvent.get("name", "water")).lower()
    if name in ("h2o", "вода"):
        name = "water"
    if name not in ("water", "none"):
        raise ValidationError(f"cell.{side_name}.solution.solvent: только 'water' или 'none'")
    solvent["name"] = name
    sol["solvent"] = solvent

    sol["volume_L"] = _num(sol.get("volume_L", 1.0), f"cell.{side_name}.solution.volume_L", lo=1e-6)

    species = sol.get("species", [])
    if not isinstance(species, list):
        raise ValidationError(f"cell.{side_name}.solution.species должен быть списком")

    norm_r = []
    for i, r in enumerate(species):
        if isinstance(r, str):
            r = {"formula": r, "moles": 1.0}
        if not isinstance(r, dict) or "formula" not in r:
            raise ValidationError(f"cell.{side_name}.solution.species[{i}]: нет поля formula")
        try:
            comp = parse_formula(str(r["formula"]))
        except FormulaError as e:
            raise ValidationError(f"cell.{side_name}.solution.species[{i}]: {e}")
        moles = _num(r.get("moles", 1.0), f"cell.{side_name}.solution.species[{i}].moles", lo=0.0)
        if moles <= 0:
            raise ValidationError(f"cell.{side_name}.solution.species[{i}].moles должно быть > 0")
        phase = r.get("phase") or comp.phase or "aq"
        if phase not in ("aq", "s", "l", "g"):
            raise ValidationError(f"cell.{side_name}.solution.species[{i}].phase: aq, s, l, g")
        formula = str(r["formula"])
        if comp.phase:
            formula = formula[: formula.rfind("(")]
        norm_r.append({"formula": formula, "moles": moles, "phase": phase})

    # Проверка электронейтральности
    q = sum(parse_formula(r["formula"]).charge * r["moles"] for r in norm_r)
    if abs(q) > 1e-9 * max(1.0, sum(r["moles"] for r in norm_r)):
        raise ValidationError(
            f"Суммарный заряд в cell.{side_name}.solution {q:+.4g} моль·e не равен нулю. "
            "Раствор каждой камеры должен быть электронейтральным."
        )

    sol["species"] = norm_r
    return sol, warnings


def validate(req: dict[str, Any]) -> tuple[dict, list[str]]:
    """Return normalized request and warnings. Raises ValidationError."""
    if not isinstance(req, dict):
        raise ValidationError("Вход должен быть JSON-объектом")

    warnings: list[str] = []
    out = copy.deepcopy(req)

    # =========================================================================
    # РЕЖИМ 1: ДВУХКАМЕРНАЯ ЭЛЕКТРОХИМИЧЕСКАЯ ЯЧЕЙКА
    # =========================================================================
    if "cell" in out and out["cell"] is not None:
        out["mode"] = "cell"
        cell = out["cell"]
        if not isinstance(cell, dict):
            raise ValidationError("cell должен быть объектом")

        # 1. Валидация камер
        for side in ("anode", "cathode"):
            if side not in cell or not isinstance(cell[side], dict):
                raise ValidationError(f"cell.{side} отсутствует или не объект")
            side_data = cell[side]

            # Электрод
            electrode = side_data.get("electrode", {})
            if not isinstance(electrode, dict):
                raise ValidationError(f"cell.{side}.electrode должен быть объектом")
            electrode["material"] = str(electrode.get("material", "Pt"))
            electrode["exchange_current_A_m2"] = _num(
                electrode.get("exchange_current_A_m2", 1e-3),
                f"cell.{side}.electrode.exchange_current_A_m2", lo=0,
            )
            side_data["electrode"] = electrode

            # Раствор
            if "solution" not in side_data:
                raise ValidationError(f"cell.{side}.solution отсутствует")
            side_data["solution"], w = _validate_solution(side_data["solution"], side)
            warnings.extend(w)

        # 2. Валидация мембраны
        membrane = cell.get("membrane", {})
        if not isinstance(membrane, dict):
            raise ValidationError("cell.membrane должен быть объектом")
        membrane["type"] = str(membrane.get("type", "cation_exchange"))
        if membrane["type"] not in ("cation_exchange", "anion_exchange", "porous", "none"):
            raise ValidationError(
                "cell.membrane.type: cation_exchange, anion_exchange, porous или none"
            )
        membrane["area_m2"] = _num(membrane.get("area_m2", 0.01), "cell.membrane.area_m2", lo=1e-9)
        membrane["thickness_m"] = _num(
            membrane.get("thickness_m", 0.001), "cell.membrane.thickness_m", lo=1e-9
        )
        cell["membrane"] = membrane

        # 3. Валидация внешней цепи
        circuit = cell.get("external_circuit", {})
        if not isinstance(circuit, dict):
            raise ValidationError("cell.external_circuit должен быть объектом")
        mode = str(circuit.get("mode", "potentiostatic")).lower()
        if mode not in ("galvanostatic", "potentiostatic"):
            raise ValidationError("cell.external_circuit.mode: galvanostatic или potentiostatic")
        circuit["mode"] = mode
        circuit["duration_s"] = _num(
            circuit.get("duration_s", 3600), "cell.external_circuit.duration_s", lo=0
        )

        if mode == "galvanostatic":
            circuit["current_density_A_m2"] = _num(
                circuit.get("current_density_A_m2", 100),
                "cell.external_circuit.current_density_A_m2", lo=0,
            )
        else:
            circuit["voltage_V"] = _num(
                circuit.get("voltage_V", 2.0), "cell.external_circuit.voltage_V", lo=0
            )
        cell["external_circuit"] = circuit

        out["cell"] = cell

        # Для ячейки options тоже валидируем (частично)
        opts = {**DEFAULT_OPTIONS, **(out.get("options") or {})}
        am = opts.get("activity_model") or "sit"
        if am not in ACTIVITY:
            raise ValidationError(f"activity_model: одно из {ACTIVITY}")
        opts["activity_model"] = am
        if opts["kinetics_model"] not in KINETICS:
            raise ValidationError(f"kinetics_model: одно из {KINETICS}")
        out["options"] = opts
        return out, warnings

    # =========================================================================
    # РЕЖИМ 2: ОДНОКАМЕРНАЯ РЕАКЦИЯ (Классическая)
    # =========================================================================
    out["mode"] = "single"

    reagents = out.get("reagents")
    if not reagents or not isinstance(reagents, list):
        raise ValidationError("Нужен непустой список reagents или объект cell для электрохимии")

    norm_r = []
    for i, r in enumerate(reagents):
        if isinstance(r, str):
            r = {"formula": r, "moles": 1.0}
        if "formula" not in r:
            raise ValidationError(f"reagents[{i}]: нет поля formula")
        try:
            comp = parse_formula(str(r["formula"]))
        except FormulaError as e:
            raise ValidationError(f"reagents[{i}]: {e}")
        moles = r.get("moles")
        if moles is None and r.get("mass_g") is not None:
            moles = float(r["mass_g"]) / comp.molar_mass()
        moles = _num(moles, f"reagents[{i}].moles", lo=0.0)
        if moles <= 0:
            raise ValidationError(f"reagents[{i}].moles должно быть > 0")
        phase = r.get("phase") or comp.phase
        if phase is not None and phase not in ("aq", "s", "l", "g"):
            raise ValidationError(f"reagents[{i}].phase: допустимо aq, s, l, g (получено {phase!r})")
        conc = _num(r.get("concentration_M"), f"reagents[{i}].concentration_M", lo=0.0, allow_none=True)
        if r.get("activity_coefficient") is not None:
            warnings.append(
                f"{r['formula']}: activity_coefficient задается моделью активности; "
                "поле учтено только как пометка"
            )
        formula = str(r["formula"])
        if comp.phase:
            formula = formula[: formula.rfind("(")]
        norm_r.append({
            "formula": formula, "moles": moles, "phase": phase, "concentration_M": conc,
            "known_energy": r.get("known_energy"),
        })
    out["reagents"] = norm_r

    q = sum(parse_formula(r["formula"]).charge * r["moles"] for r in norm_r)
    if abs(q) > 1e-9 * max(1.0, sum(r["moles"] for r in norm_r)):
        raise ValidationError(
            f"Суммарный заряд реагентов {q:+.4g} моль·e не равен нулю: раствор должен быть "
            "электронейтральным (добавьте противоионы)"
        )

    cond = {**DEFAULT_CONDITIONS, **(out.get("conditions") or {})}
    cond["temperature_K"] = _num(cond["temperature_K"], "temperature_K", lo=150.0, hi=4000.0)
    cond["pressure_atm"] = _num(cond["pressure_atm"], "pressure_atm", lo=1e-6, hi=1000.0)

    solvent = cond.get("solvent")
    if isinstance(solvent, str):
        solvent = {"name": solvent}
    if solvent is None:
        solvent = {"name": "water"} if any(r["phase"] in (None, "aq") for r in norm_r) else {"name": "none"}
    name = str(solvent.get("name", "water")).lower()
    if name in ("h2o", "вода"):
        name = "water"
    if name in ("", "null", "dry", "нет", "без растворителя"):
        name = "none"
    if name not in ("water", "none"):
        raise ValidationError(
            f"Растворитель '{solvent.get('name')}' не поддерживается: в базе есть термодинамика только "
            "водных растворов. Используйте 'water' или 'none' (сухая система)"
        )
    solvent["name"] = name
    cond["solvent"] = solvent
    aqueous = name == "water"

    for r in norm_r:
        if r["phase"] is None:
            r["phase_guessed"] = True
        if r["phase"] == "aq" and not aqueous:
            raise ValidationError(f"{r['formula']}: фаза aq, но растворитель 'none'")

    if cond.get("volume_L") is not None:
        cond["volume_L"] = _num(cond["volume_L"], "volume_L", lo=1e-6)
    else:
        vols = [r["moles"] / r["concentration_M"] for r in norm_r if r.get("concentration_M")]
        cond["volume_L"] = max(vols) if vols else 1.0
    if aqueous:
        vols = [r["moles"] / r["concentration_M"] for r in norm_r if r.get("concentration_M")]
        if vols and cond["volume_L"] + 1e-9 < max(vols) * 0.5:
            warnings.append(
                f"volume_L = {cond['volume_L']} л меньше объема растворов реагентов "
                f"({max(vols):.3g} л по concentration_M); используется volume_L"
            )

    if solvent.get("activity_model"):
        if solvent["activity_model"] not in ACTIVITY:
            raise ValidationError(f"activity_model: одно из {ACTIVITY}")
    if solvent.get("dielectric_constant") is not None:
        solvent["dielectric_constant"] = _num(solvent["dielectric_constant"], "dielectric_constant", lo=1.0)
    if solvent.get("ionic_strength_M") is not None:
        solvent["ionic_strength_M"] = _num(
            solvent["ionic_strength_M"], "ionic_strength_M", lo=0.0, hi=20.0
        )

    ph = cond.get("pH")
    if isinstance(ph, (int, float)):
        ph = {"initial": ph, "buffered": False}
    if ph and ph.get("initial") is not None:
        ph["initial"] = _num(ph["initial"], "pH.initial", lo=-1.0, hi=15.0)
    cond["pH"] = ph

    # --- Валидация электролиза (однокамерный режим) ---
    elec = cond.get("electrolysis")
    if elec is not None:
        if isinstance(elec, bool):
            elec = {"enabled": elec, "voltage_V": 1.23}
        if not isinstance(elec, dict):
            raise ValidationError("electrolysis должен быть объектом или boolean")

        elec["enabled"] = bool(elec.get("enabled", False))
        if elec["enabled"]:
            elec["voltage_V"] = _num(
                elec.get("voltage_V", 1.23), "electrolysis.voltage_V", lo=0.0, hi=20.0
            )
            if "anode" in elec and not isinstance(elec["anode"], str):
                raise ValidationError("electrolysis.anode должен быть строкой (материал анода)")
            if "cathode" in elec and not isinstance(elec["cathode"], str):
                raise ValidationError("electrolysis.cathode должен быть строкой (материал катода)")
        cond["electrolysis"] = elec
    # ----------------------------------------------------

    from ..synthesis import MethodError, apply_conditions, validate_method
    try:
        cond["method"] = validate_method(cond.get("method"))
    except MethodError as e:
        raise ValidationError(str(e))
    warnings.extend(apply_conditions(cond))

    prof = cond.get("temperature_profile")
    if prof:
        t = prof.get("type", "ramp")
        if t not in ("ramp", "constant", "points"):
            raise ValidationError("temperature_profile.type: ramp, constant или points")
        if t == "ramp":
            prof["start_K"] = _num(prof.get("start_K", cond["temperature_K"]), "start_K", lo=150, hi=4000)
            prof["end_K"] = _num(prof.get("end_K", cond["temperature_K"]), "end_K", lo=150, hi=4000)
            prof["rate_K_per_min"] = _num(
                prof.get("rate_K_per_min", 5.0), "rate_K_per_min", lo=1e-6
            )

    tm = {**DEFAULT_CONDITIONS["time"], **(cond.get("time") or {})}
    if tm["mode"] not in ("equilibrium", "kinetic"):
        raise ValidationError("time.mode: equilibrium или kinetic")
    tm["sample_points"] = int(_num(tm.get("sample_points", 10), "sample_points", lo=2, hi=500))
    cond["time"] = tm
    out["conditions"] = cond

    cons = {**DEFAULT_CONSTRAINTS, **(out.get("constraints") or {})}
    for f in cons.get("forbidden_products") or []:
        try:
            parse_formula(f)
        except FormulaError as e:
            raise ValidationError(f"forbidden_products: {e}")
    out["constraints"] = cons

    opts = {**DEFAULT_OPTIONS, **(out.get("options") or {})}
    if opts["accuracy"] not in ACCURACY:
        raise ValidationError(f"accuracy: одно из {ACCURACY}")
    if opts["energy_source"] not in ENERGY_SOURCES:
        raise ValidationError(f"energy_source: одно из {ENERGY_SOURCES}")
    if opts["kinetics_model"] not in KINETICS:
        raise ValidationError(f"kinetics_model: одно из {KINETICS}")
    if opts["uncertainty_method"] not in UNCERTAINTY:
        raise ValidationError(f"uncertainty_method: одно из {UNCERTAINTY}")
    if opts["pipeline_mode"] not in PIPELINE:
        raise ValidationError(f"pipeline_mode: одно из {PIPELINE}")
    sep = opts.get("separation") or []
    if isinstance(sep, str):
        sep = [x.strip() for x in sep.split(",") if x.strip()]
    from ..separation import METHODS as SEPARATION
    for m in sep:
        if m not in SEPARATION:
            raise ValidationError(f"separation: одно из {SEPARATION} (получено {m!r})")
    opts["separation"] = list(sep)

    am = opts.get("activity_model") or solvent.get("activity_model") or "pitzer"
    if am not in ACTIVITY:
        raise ValidationError(f"activity_model: одно из {ACTIVITY}")
    if not opts.get("include_solvent_effects", True):
        am = "ideal"
    opts["activity_model"] = am

    fmts = opts["output_formats"]
    if isinstance(fmts, str):
        fmts = [f.strip() for f in fmts.split(",")]
    for f in fmts:
        if f not in ("json", "html", "markdown", "md"):
            raise ValidationError(f"output_formats: json, html, markdown (получено {f!r})")
    opts["output_formats"] = ["markdown" if f == "md" else f for f in fmts]
    opts["random_seed"] = int(opts["random_seed"])
    if opts["theme"] not in ("light", "dark"):
        opts["theme"] = "light"
    out["options"] = opts
    out.setdefault("known_energies", {})
    return out, warnings