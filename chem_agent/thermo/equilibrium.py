"""Gibbs energy minimization via the convex dual (element potentials) and a barrier method.

Primal: minimize G(n) subject to A n = b, n >= 0, where the system consists of
  * pure condensed phases (solids, liquids; a = 1),
  * an ideal-dilute aqueous phase: solvent water + solutes, mu_i = g_i + ln(gamma_i m_i),
    mu_w = g_w - M_w * sum(m_i)  (exact convex form, homogeneous in (n_w, n_i)),
  * an ideal gas phase at fixed total pressure P: mu_i = g_i + ln(y_i P).
All g are dimensionless (mu0 / RT).

Dual: maximize b . lambda subject to
  * condensed:  a_c . lambda <= g_c
  * aqueous:    g_w - a_w . lambda - M_w * sum_i exp(a_i . lambda - g_i~) >= 0
  * gas:        ln P - logsumexp(a_j . lambda - g_j) >= 0
Phase amounts are the Lagrange multipliers of these constraints. The problem is convex,
so the minimum is unique; the barrier method is deterministic.
Activity coefficients are updated in an outer fixed-point loop (g_i~ = g_i + ln gamma_i).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

M_W = 0.018015268  # kg/mol

AQ, GAS, COND, SOLVENT = "aq", "g", "cond", "solvent"


@dataclass
class EqProblem:
    A: np.ndarray            # (n_species, n_components)
    g: np.ndarray            # (n_species,) dimensionless mu0/RT
    kind: list[str]          # AQ, GAS, COND, SOLVENT for each species
    b: np.ndarray            # (n_components,)
    charges: np.ndarray      # (n_species,)
    P_bar: float = 1.0
    gamma_fn: object = None  # callable(I, charges_aq) -> ln_gamma array; None = ideal
    fixed_I: float | None = None
    charge_col: int | None = None
    lam0: np.ndarray | None = None
    warm: tuple | None = None  # (lam, n, n_w, n_gas) of a nearby solution


@dataclass
class EqResult:
    n: np.ndarray
    lam: np.ndarray
    ln_gamma: np.ndarray
    ionic_strength: float
    water_kg: float
    converged: bool
    iterations: int
    residual: float
    gas_total: float
    messages: list[str] = field(default_factory=list)


class EquilibriumError(RuntimeError):
    pass


def _lse(z: np.ndarray) -> tuple[float, np.ndarray]:
    zmax = float(np.max(z))
    ez = np.exp(z - zmax)
    s = float(ez.sum())
    return zmax + np.log(s), ez / s


class _Barrier:
    def __init__(self, p: EqProblem, g_eff: np.ndarray):
        self.p = p
        k = np.array(p.kind)
        self.ic = np.where(k == COND)[0]
        self.ia = np.where(k == AQ)[0]
        self.ig = np.where(k == GAS)[0]
        iw = np.where(k == SOLVENT)[0]
        self.iw = int(iw[0]) if len(iw) else None
        self.g = g_eff
        self.A = p.A
        self.lnP = float(np.log(p.P_bar))
        self.has_aq = self.iw is not None
        self.has_gas = len(self.ig) > 0

    def slacks(self, lam: np.ndarray):
        A, g = self.A, self.g
        out = {}
        out["c"] = g[self.ic] - A[self.ic] @ lam
        if self.has_aq:
            za = A[self.ia] @ lam - g[self.ia]
            if len(za) and np.max(za) > 600:
                return None
            ea = np.exp(za) if len(za) else np.zeros(0)
            out["ea"] = ea
            out["w"] = g[self.iw] - A[self.iw] @ lam - M_W * ea.sum()
        if self.has_gas:
            zg = A[self.ig] @ lam - g[self.ig]
            lse, pg = _lse(zg)
            out["pg"] = pg
            out["gas"] = self.lnP - lse
        return out

    def feasible(self, s) -> bool:
        if s is None:
            return False
        if len(s["c"]) and np.min(s["c"]) <= 0:
            return False
        if self.has_aq and s["w"] <= 0:
            return False
        if self.has_gas and s["gas"] <= 0:
            return False
        return True

    def value(self, lam, t, s) -> float:
        v = t * float(self.p.b @ lam) + float(np.sum(np.log(s["c"])))
        if self.has_aq:
            v += np.log(s["w"])
        if self.has_gas:
            v += np.log(s["gas"])
        return v

    def delta(self, lam, cand, t, s, sc) -> float:
        """Barrier value difference computed without cancellation."""
        v = t * float(self.p.b @ (cand - lam))
        if len(s["c"]):
            v += float(np.sum(np.log1p((sc["c"] - s["c"]) / s["c"])))
        if self.has_aq:
            v += float(np.log(sc["w"] / s["w"]))
        if self.has_gas:
            v += float(np.log(sc["gas"] / s["gas"]))
        return v

    def grad_hess(self, lam, t, s):
        A = self.A
        m = A.shape[1]
        grad = t * self.p.b.copy()
        H = np.zeros((m, m))
        if len(self.ic):
            Ac = A[self.ic]
            inv = 1.0 / s["c"]
            grad -= Ac.T @ inv
            H -= (Ac * (inv ** 2)[:, None]).T @ Ac
        if self.has_aq:
            Aa = A[self.ia]
            ea = s["ea"]
            aw = A[self.iw]
            dh = -aw - M_W * (Aa.T @ ea)
            d2h = -M_W * (Aa * ea[:, None]).T @ Aa
            h = s["w"]
            grad += dh / h
            H += d2h / h - np.outer(dh, dh) / h ** 2
        if self.has_gas:
            Ag = A[self.ig]
            pg = s["pg"]
            dh = -Ag.T @ pg
            ap = Ag.T @ pg
            d2h = -((Ag * pg[:, None]).T @ Ag - np.outer(ap, ap))
            h = s["gas"]
            grad += dh / h
            H += d2h / h - np.outer(dh, dh) / h ** 2
        return grad, H

    def amounts(self, lam, t, s) -> tuple[np.ndarray, float, float]:
        n = np.zeros(len(self.p.g))
        if len(self.ic):
            n[self.ic] = 1.0 / (t * s["c"])
        n_w, n_gas = 0.0, 0.0
        if self.has_aq:
            n_w = 1.0 / (t * s["w"])
            n[self.iw] = n_w
            n[self.ia] = n_w * M_W * s["ea"]
        if self.has_gas:
            n_gas = 1.0 / (t * s["gas"])
            n[self.ig] = n_gas * s["pg"]
        return n, n_w, n_gas


def _initial_lambda(p: EqProblem, g: np.ndarray) -> np.ndarray:
    """Strictly feasible start: all element potentials very negative, charge potential 0."""
    A = p.A
    atoms = np.abs(A).sum(axis=1)
    is_charge = np.zeros(A.shape[1], dtype=bool)
    if p.charge_col is not None:
        is_charge[p.charge_col] = True
    atoms_nc = (np.abs(A[:, ~is_charge])).sum(axis=1)
    atoms_nc = np.where(atoms_nc > 0, atoms_nc, 1.0)
    # need g_i + M*atoms_i > margin for all species
    M = float(np.max((-g + 30.0) / atoms_nc))
    M = max(M, 50.0)
    lam = np.where(is_charge, 0.0, -M)
    return lam


def _lp_lambda(p: EqProblem, g: np.ndarray) -> np.ndarray | None:
    """Element potentials of the 'all species pure' LP (dual of min g.n, A n = b, n >= 0),
    shifted into the strict interior of the barrier domain."""
    from scipy.optimize import linprog
    A = p.A
    try:
        res = linprog(-p.b, A_ub=A, b_ub=g, bounds=[(None, None)] * A.shape[1], method="highs")
    except Exception:  # noqa: BLE001
        return None
    if res.status != 0:
        return None
    lam = res.x.copy()
    shift = np.full(A.shape[1], 3.0)
    if p.charge_col is not None:
        shift[p.charge_col] = 0.0
    return lam - shift


def _center(bar: _Barrier, lam, t, max_iter=150, tol=1e-7):
    s = bar.slacks(lam)
    it = 0
    for it in range(max_iter):
        grad, H = bar.grad_hess(lam, t, s)
        m = len(lam)
        d = np.abs(np.diag(H))
        d = 1.0 / np.sqrt(np.where(d > 1e-300, d, 1e-300))
        Hs = H * d[:, None] * d[None, :]
        Hs = 0.5 * (Hs + Hs.T)
        w, V = np.linalg.eigh(-Hs)  # -Hs is positive semidefinite
        keep = w > 1e-9 * max(1e-300, float(w.max()))
        gk = V.T @ (grad * d)
        y = V[:, keep] @ (gk[keep] / w[keep])
        step = d * y
        dec = float(grad @ step)  # Newton decrement^2 (>= 0: ascent direction)
        if dec / 2 < tol or float(np.max(np.abs(step))) < 1e-12:
            break
        smax = float(np.max(np.abs(step)))
        if smax > 20.0:  # trust region in units of RT
            step = step * (20.0 / smax)
        slope = float(grad @ step)
        alpha = 1.0
        accepted = False
        for _ in range(60):
            cand = lam + alpha * step
            sc = bar.slacks(cand)
            if bar.feasible(sc):
                if bar.delta(lam, cand, t, s, sc) >= 0.1 * alpha * slope:
                    lam, s = cand, sc
                    accepted = True
                    break
            alpha *= 0.5
        if not accepted or alpha * float(np.max(np.abs(step))) < 1e-13:
            break
    return lam, s, it + 1


def _polish(bar: _Barrier, lam, n, n_w, n_gas, scale, max_iter=60):
    """Active-set Newton on the KKT system for full precision."""
    p, A, g = bar.p, bar.A, bar.g
    E = A.shape[1]
    thr = 1e-10 * scale
    s0 = bar.slacks(lam)
    slack_c = s0["c"] if s0 is not None else np.full(len(bar.ic), np.inf)
    active_c = [int(i) for i, sl in zip(bar.ic, slack_c) if n[i] > thr and sl < 1e-2]
    gas_on = bar.has_gas and n_gas > thr and (s0 is None or s0["gas"] < 1e-2)
    aq_on = bar.has_aq and n_w > thr
    for _round in range(20):
        nc = len(active_c)
        x = np.concatenate([lam, [n_w if aq_on else 0.0], [n_gas if gas_on else 0.0], n[active_c]])

        def unpack(x):
            return x[:E], x[E], x[E + 1], x[E + 2:]

        def F_and_J(x):
            lam_, nw, ng, ncv = unpack(x)
            F = np.zeros(E + 2 + nc)
            J = np.zeros((E + 2 + nc, E + 2 + nc))
            mass = -p.b.astype(float).copy()
            Jm = np.zeros((E, E + 2 + nc))
            if aq_on:
                Aa = A[bar.ia]
                ea = np.exp(np.minimum(Aa @ lam_ - g[bar.ia], 700))
                aw = A[bar.iw]
                sol = M_W * ea
                mass += aw * nw + nw * (Aa.T @ sol)
                Jm[:, :E] += nw * (Aa * sol[:, None]).T @ Aa
                Jm[:, E] = aw + Aa.T @ sol
                F[E] = g[bar.iw] - aw @ lam_ - sol.sum()
                J[E, :E] = -aw - Aa.T @ sol
            else:
                F[E] = x[E]
                J[E, E] = 1.0
            if gas_on:
                Ag = A[bar.ig]
                lse, pg = _lse(Ag @ lam_ - g[bar.ig])
                mass += ng * (Ag.T @ pg)
                ap = Ag.T @ pg
                Jm[:, :E] += ng * ((Ag * pg[:, None]).T @ Ag - np.outer(ap, ap))
                Jm[:, E + 1] = ap
                F[E + 1] = bar.lnP - lse
                J[E + 1, :E] = -ap
            else:
                F[E + 1] = x[E + 1]
                J[E + 1, E + 1] = 1.0
            if nc:
                Ac = A[active_c]
                mass += Ac.T @ ncv
                Jm[:, E + 2:] = Ac.T
                F[E + 2:] = g[active_c] - Ac @ lam_
                J[E + 2:, :E] = -Ac
            F[:E] = mass / scale
            J[:E] = Jm / scale
            return F, J

        ok = False
        for _ in range(max_iter):
            F, J = F_and_J(x)
            nrm = float(np.linalg.norm(F))
            if nrm < 1e-13:
                ok = True
                break
            try:
                dx = np.linalg.lstsq(J, -F, rcond=None)[0]
            except np.linalg.LinAlgError:
                return None
            a = 1.0
            improved = False
            for _ls in range(40):
                xn = x + a * dx
                with np.errstate(all="ignore"):
                    Fn, _ = F_and_J(xn)
                    nn = float(np.linalg.norm(Fn))
                if np.isfinite(nn) and nn < (1 - 1e-4 * a) * nrm:
                    x = xn
                    improved = True
                    break
                a *= 0.5
            if not improved:
                ok = nrm < 1e-9
                break
        if not ok:
            return None
        lam_, nw, ng, ncv = unpack(x)
        # active-set checks
        old_amounts = {i: float(v) for i, v in zip(active_c, ncv)}
        changed = False
        if nc and np.min(ncv) < -thr:
            active_c.remove(active_c[int(np.argmin(ncv))])
            changed = True
        slack = g[bar.ic] - A[bar.ic] @ lam_
        cand = [int(i) for i, sl in zip(bar.ic, slack) if sl < -1e-9 and int(i) not in active_c]
        if cand and not changed:
            active_c.append(min(cand, key=lambda i: g[i] - A[i] @ lam_))
            changed = True
        if bar.has_gas and not gas_on:
            lse, _ = _lse(A[bar.ig] @ lam_ - g[bar.ig])
            if lse > bar.lnP + 1e-9:
                gas_on = True
                ng = 1e-6 * scale
                changed = True
        if gas_on and ng < -thr:
            gas_on = False
            changed = True
        lam, n_w, n_gas = lam_, nw, ng
        if not changed:
            n = np.zeros(len(g))
            if active_c:
                n[active_c] = np.maximum(ncv, 0.0)
            if aq_on:
                n[bar.iw] = nw
                n[bar.ia] = nw * M_W * np.exp(A[bar.ia] @ lam_ - g[bar.ia])
            if gas_on:
                _, pg = _lse(A[bar.ig] @ lam_ - g[bar.ig])
                n[bar.ig] = ng * pg
            return lam_, n, (nw if aq_on else 0.0), (ng if gas_on else 0.0)
        n = np.zeros(len(g))
        for i in active_c:
            n[i] = max(old_amounts.get(i, thr), thr)
        n_gas = max(ng, thr) if gas_on else 0.0
    return None


def solve(p: EqProblem, max_outer: int = 40) -> EqResult:
    A, g0 = p.A, p.g
    ncomp = A.shape[1]
    scale = float(np.sum(np.abs(p.b)))
    if scale <= 0:
        raise EquilibriumError("Пустая система: нет вещества")
    kind = np.array(p.kind)
    ia = np.where(kind == AQ)[0]
    ln_gamma = np.zeros(len(g0))
    lam = None
    msgs: list[str] = []
    I_val = 0.0
    total_iter = 0
    converged = False
    polish_failed = False
    n = np.zeros(len(g0))
    n_w = n_gas = 0.0
    for outer in range(max_outer):
        g = g0 + ln_gamma
        bar = _Barrier(p, g)
        pol = None
        if outer > 0 and lam is not None:
            pol = _polish(bar, lam, n, n_w, n_gas, scale)
        elif outer == 0 and p.warm is not None:
            pol = _polish(bar, *p.warm, scale)  # fast path: Newton from previous solution
        if pol is None:
            if lam is not None:
                lam0 = lam
            elif p.lam0 is not None:
                lam0 = p.lam0
            else:
                lam0 = _lp_lambda(p, g)
                if lam0 is None or not bar.feasible(bar.slacks(lam0)):
                    lam0 = _initial_lambda(p, g)
            if not bar.feasible(bar.slacks(lam0)):
                lam0 = _initial_lambda(p, g)
            m_constr = len(bar.ic) + int(bar.has_aq) + int(bar.has_gas)
            t = 1e3 * m_constr / scale
            lam_c = lam0
            while True:
                lam_c, s, it = _center(bar, lam_c, t)
                total_iter += it
                if m_constr / t < 1e-7 * scale:
                    break
                t *= 25.0
            lam = lam_c
            n, n_w, n_gas = bar.amounts(lam, t, s)
            pol = _polish(bar, lam, n, n_w, n_gas, scale)
            if pol is None:
                # tighten the barrier (smaller duality gap) and try the Newton polish again
                while m_constr / t > 1e-11 * scale:
                    t *= 25.0
                    lam_c, s, it = _center(bar, lam_c, t)
                    total_iter += it
                lam = lam_c
                n, n_w, n_gas = bar.amounts(lam, t, s)
                pol = _polish(bar, lam, n, n_w, n_gas, scale)
            if pol is None:
                polish_failed = True
                msgs.append("Уточнение Ньютоном не сошлось; использовано решение барьерного метода")
        if pol is not None:
            lam, n, n_w, n_gas = pol
        if p.gamma_fn is None or not len(ia) or n_w <= 0:
            converged = True
            break
        W = n_w * M_W
        m_aq = n[ia] / W
        z = p.charges[ia]
        I_new = p.fixed_I if p.fixed_I is not None else 0.5 * float(np.sum(m_aq * z ** 2))
        lg_new = p.gamma_fn(I_new, z)
        diff = float(np.max(np.abs(lg_new - ln_gamma[ia]))) if len(ia) else 0.0
        ln_gamma[ia] = 0.5 * ln_gamma[ia] + 0.5 * lg_new if outer > 3 else lg_new
        I_val = I_new
        if diff < 1e-7:
            converged = True
            break
    # residual per component, relative to the amount of that component in the system
    bb = np.abs(p.b)
    denom = np.where(bb > 1e-6 * scale, bb, 1e-6 * scale)
    resid = float(np.max(np.abs(A.T @ n - p.b) / denom))
    if resid > 1e-6:
        msgs.append(f"Невязка баланса масс {resid:.2e}")
    if not converged:
        msgs.append("Коэффициенты активности не сошлись за отведенное число итераций")
    return EqResult(n=n, lam=lam, ln_gamma=ln_gamma, ionic_strength=I_val,
                    water_kg=n_w * M_W, converged=converged and resid < 1e-5 and not polish_failed,
                    iterations=total_iter, residual=resid, gas_total=n_gas, messages=msgs)
