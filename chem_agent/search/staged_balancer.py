"""Staged balancer (W-02): уравнение через промежуточные частицы, когда balance() вернул None.

Почему balance() не справляется: он требует строго положительный коэффициент у каждого участника.
Агент добавляет в реагенты H2O (вода слегка расходуется на гидролиз), и Fe + CuSO4 + H2O -> Cu + FeSO4
решается только с нулем у воды. Так же мешают побочные продукты (H+ в Cl2 + KBr).

Алгоритм:
1. Промежуточные частицы: каждый участник раскладывается до ионов - соли (naming.salt_decomposition),
   комплексы (crc.db, complex_constants), гидроксо-формы M(OH)n.
2. Граф стадий: диссоциация реагентов -> ионная стадия -> ассоциация продуктов.
3. Коэффициенты: минимальное целочисленное решение баланса элементов и заряда (MILP),
   нули разрешены, главный продукт (первый) >= 1. Сначала требуем все значимые продукты
   (>= 10 % от главного), затем только главный.
4. Каждая стадия балансируется, сумма стадий сверяется с итоговым уравнением.
   Не сходится - None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..parser.elements import is_metal
from ..parser.formula import FormulaError, charge_suffix, parse_formula
from ..parser.naming import salt_decomposition
from .balance import format_side

MAX_COEF = 60
SIGNIFICANT = 0.1  # доля от главного продукта, при которой продукт обязателен в уравнении
MEDIUM = {((("H", 1.0),), 1), ((("H", 1.0), ("O", 1.0)), -1), ((("H", 2.0), ("O", 1.0)), 0)}


@dataclass
class StagedResult:
    reactants: list[int]
    products: list[int]
    stages: list[dict] = field(default_factory=list)
    dropped_products: list[int] = field(default_factory=list)


Key = tuple  # (elements tuple, charge) - ключ частицы, как Composition.key


def _key(els: dict, q: int) -> Key:
    return (tuple(sorted((k, float(v)) for k, v in els.items() if v)), int(q))


@lru_cache(maxsize=1)
def _complexes() -> dict[Key, tuple[str, str, int]]:
    """complex_constants: ключ комплекса -> (металл, лиганд, n)."""
    from ..energy.database import get_db
    out = {}
    for f, row in get_db().complex_constants.items():
        try:
            out[parse_formula(f).key] = (row["metal"], row["ligand"], int(row["n"]))
        except FormulaError:
            continue
    return out


_ION_LABELS: dict[Key, str] = {}  # ключ иона -> запись из разложения соли ("Ni(NH3)6+2")


def _ion_key(body: str, z: int) -> Key:
    label = body + charge_suffix(z)
    key = parse_formula(label).key
    _ION_LABELS.setdefault(key, label)
    return key


def is_complex_or_hydroxo(key: Key) -> bool:
    els, q = dict(key[0]), key[1]
    metals = [e for e in els if is_metal(e)]
    hydroxo = len(els) == 3 and len(metals) == 1 and els.get("O") == els.get("H") and q != 0
    return key in _complexes() or hydroxo


def decompose(key: Key, depth: int = 0, deep: bool = False) -> dict[Key, float]:
    """Частица -> промежуточные частицы. Соли - на ионы (комплексный ион остается целым).
    deep=True - комплексы и гидроксо-формы дальше: на металл и лиганды. Неразложимая - сама себя."""
    if depth > 3:
        return {key: 1.0}
    els, q = dict(key[0]), key[1]
    cx = _complexes().get(key) if deep else None
    if cx:
        metal, ligand, n = cx
        out: dict[Key, float] = {}
        for k, c in ((parse_formula(metal).key, 1.0), (parse_formula(ligand).key, float(n))):
            for kk, cc in decompose(k, depth + 1, deep).items():
                out[kk] = out.get(kk, 0.0) + c * cc
        return out
    metals = [e for e in els if is_metal(e)]
    # гидроксо-форма M(OH)n^z -> M^(z+n) + n OH-
    if deep and len(els) == 3 and len(metals) == 1 and els.get("O") == els.get("H") and q != 0:
        n = els["O"]
        m = metals[0]
        if els[m] == 1 and n == int(n):
            return {_key({m: 1}, q + int(n)): 1.0, _key({"O": 1, "H": 1}, -1): float(n)}
    if q == 0 and len(els) > 1 and not (set(els) <= {"H", "O"}):
        dec = salt_decomposition(key[0])
        if dec:
            cb, zc, p, ab, za, qq = dec
            if cb == "H" and not any(is_metal(e) for e in els):
                return {key: 1.0}  # кислоты не диссоциируем на стадии: слабые/сильные решает равновесие
            out = {}
            for body, z, c in ((cb, zc, p), (ab, za, qq)):
                try:
                    k = _ion_key(body, z)
                except FormulaError:
                    return {key: 1.0}
                for kk, cc in decompose(k, depth + 1, deep).items():
                    out[kk] = out.get(kk, 0.0) + c * cc
            return out
    return {key: 1.0}


def dissociate(key: Key) -> dict[Key, float]:
    """Ионы реагента в растворе, включая кислоты (HClO4 -> H+ + ClO4-), которые decompose не делит."""
    parts = decompose(key)
    if parts != {key: 1.0} or key[1] != 0:
        return parts
    dec = salt_decomposition(key[0])
    if not dec or dec[0] != "H":
        return parts
    cb, zc, p, ab, za, q = dec
    try:
        return {_ion_key("H", 1): float(p), _ion_key(ab, za): float(q)}
    except FormulaError:
        return parts


def _solve(M: np.ndarray, nr: int, required: list[int]) -> np.ndarray | None:
    n = M.shape[1]
    S = M.copy()
    S[:, :nr] *= -1
    lb = np.zeros(n)
    for j in required:
        lb[nr + j] = 1
    res = milp(c=np.ones(n), integrality=np.ones(n),
               bounds=Bounds(lb, np.full(n, MAX_COEF)),
               constraints=LinearConstraint(S, 0, 0),
               options={"time_limit": 2.0})
    if res.status != 0 or res.x is None:
        return None
    v = np.round(res.x).astype(int)
    if np.any(np.abs(S @ v) > 1e-9) or v[:nr].sum() == 0:
        return None
    return v


def _label(key: Key, names: dict[Key, str]) -> str:
    if key in names:
        return names[key]
    if key in _ION_LABELS:
        return _ION_LABELS[key]
    els, q = dict(key[0]), key[1]
    special = {(("H", 1.0), ("O", 1.0)): "OH", (("H", 3.0), ("N", 1.0)): "NH3", (("H", 4.0), ("N", 1.0)): "NH4",
               (("H", 2.0), ("O", 1.0)): "H2O"}
    from ..parser.formula import conventional_formula
    body = special.get(key[0])
    return (body + charge_suffix(q)) if body else conventional_formula(els, q)


def _eq(left: dict[Key, float], right: dict[Key, float], names: dict[Key, str]) -> str:
    def side(d):
        items = sorted(((k, c) for k, c in d.items() if c > 1e-9), key=lambda t: _label(t[0], names))
        return format_side([int(round(c)) for _, c in items], [_label(k, names) for k, _ in items])
    return side(left) + " -> " + side(right)


def staged_balance(reac: list[dict], reac_q: list[int], prod: list[dict], prod_q: list[int],
                   prod_amounts: list[float] | None = None, *,
                   reac_names: list[str] | None = None, prod_names: list[str] | None = None,
                   reac_dissolved: list[bool] | None = None,
                   prod_dissolved: list[bool] | None = None, main: int = 0) -> StagedResult | None:
    """Коэффициенты (реагенты, продукты) с нулями для неучаствующих, стадии и выброшенные продукты.
    main - индекс главного продукта (коэффициент >= 1)."""
    nr, npr = len(reac), len(prod)
    if not nr or not npr:
        return None
    keys = sorted({k for c in reac + prod for k in c})
    M = np.array([[c.get(k, 0) for c in reac + prod] for k in keys] + [list(reac_q) + list(prod_q)], dtype=float)

    required = [main]
    if prod_amounts is not None and prod_amounts[main] > 0:
        # среда (H+, OH-, H2O) не обязательна: иначе в уравнение попадает автоионизация воды
        medium = {_key(c, q) for c, q in zip(prod, prod_q)} & MEDIUM
        required = [j for j, a in enumerate(prod_amounts)
                    if j == main or (a >= SIGNIFICANT * prod_amounts[main] and _key(prod[j], prod_q[j]) not in medium)]
    v = _solve(M, nr, required)
    if v is None and len(required) > 1:
        v = _solve(M, nr, [main])
    if v is None:
        return None
    cr, cp = [int(x) for x in v[:nr]], [int(x) for x in v[nr:]]

    # стадии
    rkeys = [_key(c, q) for c, q in zip(reac, reac_q)]
    pkeys = [_key(c, q) for c, q in zip(prod, prod_q)]
    names = {k: n for k, n in zip(rkeys + pkeys, (reac_names or [""] * nr) + (prod_names or [""] * npr)) if n}
    rdis = reac_dissolved or [True] * nr
    pdis = prod_dissolved or [True] * npr
    stages, left_ions, right_ions = [], {}, {}

    def level(k, c, dissolved, kind, side):
        dec = decompose(k) if dissolved else {k: 1.0}
        if dec != {k: 1.0}:
            parts = {kk: c * cc for kk, cc in dec.items()}
            stages.append({"stage": kind, "equation": _eq({k: c}, parts, names) if kind == "dissociation"
                           else _eq(parts, {k: c}, names)})
        else:
            parts = {k: float(c)}
        for kk, cc in parts.items():
            side[kk] = side.get(kk, 0.0) + cc

    for k, c, d in zip(rkeys, cr, rdis):
        if c:
            level(k, c, d, "dissociation", left_ions)
    assoc = []
    for k, c, d in zip(pkeys, cp, pdis):
        if c:
            n0 = len(stages)
            level(k, c, d, "association", right_ions)
            assoc += stages[n0:]
            del stages[n0:]
    # ионная стадия: сокращаем частицы-зрители
    core_l, core_r = {}, {}
    for k in set(left_ions) | set(right_ions):
        d = right_ions.get(k, 0.0) - left_ions.get(k, 0.0)
        if d > 1e-9:
            core_r[k] = d
        elif d < -1e-9:
            core_l[k] = -d
    if not core_l or not core_r:
        return None

    # сумма стадий = итоговое уравнение (по элементам и заряду ионной стадии)
    def total(d):
        els, q = {}, 0.0
        for (e, z), c in d.items():
            for el, n in e:
                els[el] = els.get(el, 0.0) + c * n
            q += c * z
        return {k: round(v, 9) for k, v in els.items() if abs(v) > 1e-9}, round(q, 9)
    if total(core_l) != total(core_r):
        return None
    kind = "complexation" if any(is_complex_or_hydroxo(k) for k in core_r) else "ionic"
    stages.append({"stage": kind, "equation": _eq(core_l, core_r, names)})
    stages += assoc
    dropped = [j for j in range(npr) if cp[j] == 0]
    return StagedResult(cr, cp, stages, dropped)
