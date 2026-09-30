"""Equation balancing: element + charge conservation with small integer coefficients."""
from __future__ import annotations

from fractions import Fraction
from math import gcd
from functools import reduce

import numpy as np
from scipy.optimize import nnls


def _matrix(comps: list[dict], charges: list[int]) -> tuple[np.ndarray, list[str]]:
    keys = sorted({k for c in comps for k in c})
    M = np.array([[c.get(k, 0) for c in comps] for k in keys] + [list(charges)], dtype=float)
    return M, keys


def integerize(x: list[float], max_den: int = 12) -> list[int] | None:
    x = [abs(v) for v in x]
    m = min(v for v in x if v > 0)
    fr = [Fraction(v / m).limit_denominator(max_den) for v in x]
    den = reduce(lambda a, b: a * b // gcd(a, b), (f.denominator for f in fr), 1)
    ints = [int(f * den) for f in fr]
    g = reduce(gcd, [i for i in ints if i], 0) or 1
    ints = [i // g for i in ints]
    if max(ints) > 60:
        return None
    return ints


def balance(reac: list[dict], reac_q: list[int], prod: list[dict], prod_q: list[int],
            prod_amounts: list[float] | None = None) -> tuple[list[int], list[int]] | None:
    """Return integer coefficients (reactants, products) or None.

    If product amounts are given (from equilibrium), reactant coefficients are fitted by
    non-negative least squares; otherwise the null space is used.
    """
    comps = reac + prod
    charges = list(reac_q) + list(prod_q)
    M, _ = _matrix(comps, charges)
    nr = len(reac)
    if prod_amounts is not None and len(prod) and nr:
        Mr, Mp = M[:, :nr], M[:, nr:]
        target = Mp @ np.asarray(prod_amounts, dtype=float)
        x, res = nnls(Mr, target)
        if res <= 1e-6 * max(1.0, float(np.abs(target).sum())) and np.all(x >= 0):
            vec = list(x) + list(prod_amounts)
            keep = [i for i, v in enumerate(vec) if v > 1e-9 * max(vec)]
            ints = integerize([vec[i] for i in keep])
            if ints:
                full = [0] * len(vec)
                for i, v in zip(keep, ints):
                    full[i] = v
                signed = np.array([-v for v in full[:nr]] + full[nr:], dtype=float)
                if np.max(np.abs(M @ signed)) < 1e-9:
                    return full[:nr], full[nr:]
    # projection of the equilibrium amounts onto the exact null space (minor species ignored)
    if prod_amounts is not None and len(prod) and nr:
        Mr, Mp = M[:, :nr], M[:, nr:]
        target = Mp @ np.asarray(prod_amounts, dtype=float)
        x, res = nnls(Mr, target)
        if res <= 0.05 * max(1e-300, float(np.linalg.norm(target))):
            Ms = M.copy()
            Ms[:, :nr] *= -1
            _, sv, vt = np.linalg.svd(Ms)
            rank = int(np.sum(sv > 1e-9))
            N = vt[rank:].T
            if N.shape[1]:
                h = np.concatenate([x, np.asarray(prod_amounts, dtype=float)])
                v = N @ (N.T @ h)
                if np.all(v > 1e-9 * np.max(np.abs(v))) and np.linalg.norm(v - h) < 0.1 * np.linalg.norm(h):
                    ints = integerize(list(v), max_den=24)
                    if ints:
                        signed = np.array([-a for a in ints[:nr]] + ints[nr:], dtype=float)
                        if np.max(np.abs(M @ signed)) < 1e-9:
                            return ints[:nr], ints[nr:]
    # null space
    Ms = M.copy()
    Ms[:, :nr] *= -1
    u, s, vt = np.linalg.svd(Ms)
    rank = int(np.sum(s > 1e-9))
    null = vt[rank:]
    if null.shape[0] != 1:
        return None
    v = null[0]
    if np.all(v <= 1e-12):
        v = -v
    if np.any(v <= 1e-12):
        return None
    ints = integerize(list(v), max_den=24)
    if not ints:
        return None
    signed = np.array([-a for a in ints[:nr]] + ints[nr:], dtype=float)
    if np.max(np.abs(M @ signed)) > 1e-9:
        return None
    return ints[:nr], ints[nr:]


def format_side(coefs: list[int], names: list[str]) -> str:
    parts = []
    for c, n in zip(coefs, names):
        if c == 0:
            continue
        parts.append(n if c == 1 else f"{c} {n}")
    return " + ".join(parts)
