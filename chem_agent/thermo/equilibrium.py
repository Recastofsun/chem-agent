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

Activity coefficients are updated in an outer loop. Fast path: Anderson acceleration.
If Anderson stagnates (diff > 1e-4 after 12 iterations), switch to full Newton on
(lambda, n_w, n_gas, n_cond, ln_gamma_aq) with numerical Jacobian (W-01).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import os

M_W = 0.018015268  # kg/mol

AQ, GAS, COND, SOLVENT = "aq", "g", "cond", "solvent"


@dataclass
class EqProblem:
    A: np.ndarray
    g: np.ndarray
    kind: list[str]
    b: np.ndarray
    charges: np.ndarray
    P_bar: float = 1.0
    gamma_fn: object = None
    fixed_I: float | None = None
    charge_col: int | None = None
    lam0: np.ndarray | None = None
    warm: tuple | None = None
    fixed_lambda: dict[int, float] | None = None


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
        if self.p.fixed_lambda:
            for idx in self.p.fixed_lambda:
                grad[idx] = 0.0
                H[idx, :] = 0.0
                H[:, idx] = 0.0
                H[idx, idx] = 1.0
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
    A = p.A
    atoms = np.abs(A).sum(axis=1)
    is_charge = np.zeros(A.shape[1], dtype=bool)
    if p.charge_col is not None:
        is_charge[p.charge_col] = True
    atoms_nc = (np.abs(A[:, ~is_charge])).sum(axis=1)
    atoms_nc = np.where(atoms_nc > 0, atoms_nc, 1.0)
    M = float(np.max((-g + 30.0) / atoms_nc))
    M = max(M, 50.0)
    lam = np.where(is_charge, 0.0, -M)
    return lam


def _lp_lambda(p: EqProblem, g: np.ndarray) -> np.ndarray | None:
    from scipy.optimize import linprog
    A = p.A
    try:
        res = linprog(-p.b, A_ub=A, b_ub=g, bounds=[(None, None)] * A.shape[1], method="highs")
    except Exception:
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
        w, V = np.linalg.eigh(-Hs)
        keep = w > 1e-9 * max(1e-300, float(w.max()))
        gk = V.T @ (grad * d)
        y = V[:, keep] @ (gk[keep] / w[keep])
        step = d * y
        if bar.p.fixed_lambda:
            for idx in bar.p.fixed_lambda:
                step[idx] = 0.0
        dec = float(grad @ step)
        if dec / 2 < tol or float(np.max(np.abs(step))) < 1e-12:
            break
        smax = float(np.max(np.abs(step)))
        if smax > 20.0:
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
    """Active-set Newton on the KKT system for full precision (gamma fixed)."""
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
            if p.fixed_lambda:
                for idx, val in p.fixed_lambda.items():
                    F[idx] = lam_[idx] - val
                    J[idx, :] = 0.0
                    J[idx, idx] = 1.0
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


def _polish_with_gamma(p: EqProblem, lam, n, n_w, n_gas, gamma_aq, scale, max_iter=30, jac_eps=1e-6):
    """
    Полный Newton по (λ, n_w, n_g, n_c, γ_aq) с численным Якобианом для γ.

    bar строится на g0 (без ln_gamma). gamma_aq - текущее приближение к ln(gamma)
    для aq-ионов. Система: KKT + (γ_i - f_i(I, m)) = 0.
    Возвращает (lam, n, n_w, n_gas, gamma_aq_new) или None.
    """
    A, g0 = p.A, p.g
    bar = _Barrier(p, g0)
    E = A.shape[1]
    ia = bar.ia
    n_aq = len(ia)
    if n_aq == 0:
        return None

    thr = 1e-10 * scale
    s0 = bar.slacks(lam)
    slack_c = s0["c"] if s0 is not None else np.full(len(bar.ic), np.inf)
    active_c = [int(i) for i, sl in zip(bar.ic, slack_c) if n[i] > thr and sl < 1e-2]
    gas_on = bar.has_gas and n_gas > thr and (s0 is None or s0["gas"] < 1e-2)
    aq_on = bar.has_aq and n_w > thr

    nc = len(active_c)
    size = E + 2 + nc + n_aq
    x = np.concatenate([lam, [n_w if aq_on else 0.0], [n_gas if gas_on else 0.0],
                        n[active_c], gamma_aq.copy()])

    def unpack(x):
        return x[:E], x[E], x[E + 1], x[E + 2:E + 2 + nc], x[E + 2 + nc:]

    def compute_F(x, with_jac=False):
        lam_, nw, ng, ncv, gamma_ = unpack(x)
        F = np.zeros(size)
        J = np.zeros((size, size)) if with_jac else None

        g_eff = g0.copy()
        g_eff[ia] += gamma_

        mass = -p.b.astype(float).copy()
        Jm = np.zeros((E, E + 2 + nc + n_aq)) if with_jac else None

        Aa = A[ia] if aq_on else None
        ea = None
        if aq_on:
            ea = np.exp(np.minimum(Aa @ lam_ - g_eff[ia], 700))
            aw = A[bar.iw]
            sol = M_W * ea
            mass += aw * nw + nw * (Aa.T @ sol)
            if with_jac:
                Jm[:, :E] += nw * (Aa * sol[:, None]).T @ Aa
                Jm[:, E] = aw + Aa.T @ sol
                Jm[:, E + 2 + nc:] = -nw * (Aa * sol[:, None]).T
            F[E] = g_eff[bar.iw] - aw @ lam_ - sol.sum()
            if with_jac:
                J[E, :E] = -aw - Aa.T @ sol
        else:
            F[E] = x[E]
            if with_jac:
                J[E, E] = 1.0

        if gas_on:
            Ag = A[bar.ig]
            lse, pg = _lse(Ag @ lam_ - g0[bar.ig])
            mass += ng * (Ag.T @ pg)
            ap = Ag.T @ pg
            if with_jac:
                Jm[:, :E] += ng * ((Ag * pg[:, None]).T @ Ag - np.outer(ap, ap))
                Jm[:, E + 1] = ap
            F[E + 1] = bar.lnP - lse
            if with_jac:
                J[E + 1, :E] = -ap
        else:
            F[E + 1] = x[E + 1]
            if with_jac:
                J[E + 1, E + 1] = 1.0

        if nc:
            Ac = A[active_c]
            mass += Ac.T @ ncv
            if with_jac:
                Jm[:, E + 2:E + 2 + nc] = Ac.T
            F[E + 2:E + 2 + nc] = g_eff[active_c] - Ac @ lam_
            if with_jac:
                J[E + 2:E + 2 + nc, :E] = -Ac

        F[:E] = mass / scale
        if with_jac:
            J[:E] = Jm / scale

        if aq_on and Aa is not None and ea is not None:
            m_aq_local = ea
            I_local = 0.5 * float(np.sum(m_aq_local * p.charges[ia] ** 2))
            f_val = p.gamma_fn(I_local, p.charges[ia], m=m_aq_local)
            # Масштабируем γ-блок так, чтобы невязки по массе и по γ были соизмеримы
            gamma_scale = 1.0
            F[E + 2 + nc:] = (gamma_ - f_val) * gamma_scale

            if with_jac:
                J[E + 2 + nc:, E + 2 + nc:] = np.eye(n_aq) * gamma_scale
                for j in range(n_aq):
                    gamma_plus = gamma_.copy()
                    gamma_plus[j] += jac_eps
                    g_eff_plus = g0.copy()
                    g_eff_plus[ia] += gamma_plus
                    m_plus = np.exp(np.minimum(Aa @ lam_ - g_eff_plus[ia], 700))
                    I_plus = 0.5 * float(np.sum(m_plus * p.charges[ia] ** 2))
                    f_plus = p.gamma_fn(I_plus, p.charges[ia], m=m_plus)
                    J[E + 2 + nc + j, E + 2 + nc:] = -(f_plus - f_val) / jac_eps * gamma_scale
                for j in range(E):
                    lam_plus = lam_.copy()
                    lam_plus[j] += jac_eps
                    m_plus = np.exp(np.minimum(Aa @ lam_plus - g_eff[ia], 700))
                    I_plus = 0.5 * float(np.sum(m_plus * p.charges[ia] ** 2))
                    f_plus = p.gamma_fn(I_plus, p.charges[ia], m=m_plus)
                    J[E + 2 + nc:, j] = -(f_plus - f_val) / jac_eps * gamma_scale
        else:
            F[E + 2 + nc:] = gamma_
            if with_jac:
                J[E + 2 + nc:, E + 2 + nc:] = np.eye(n_aq)

        return (F, J) if with_jac else F

    for _ in range(max_iter):
        F = compute_F(x, with_jac=False)
        nrm = float(np.linalg.norm(F))
        if nrm < 1e-10:
            break
        _, J = compute_F(x, with_jac=True)
        try:
            dx = np.linalg.lstsq(J, -F, rcond=None)[0]
        except np.linalg.LinAlgError:
            return None
        a = 1.0
        improved = False
        for _ls in range(40):
            xn = x + a * dx
            with np.errstate(all="ignore"):
                Fn = compute_F(xn, with_jac=False)
                nn = float(np.linalg.norm(Fn))
            if np.isfinite(nn) and nn < (1 - 1e-4 * a) * nrm:
                x = xn
                improved = True
                break
            a *= 0.5
        if not improved:
            break

    F_final = compute_F(x, with_jac=False)
    if float(np.linalg.norm(F_final)) > 1e-6:
        return None

    lam_, nw, ng, ncv, gamma_ = unpack(x)
    n_new = np.zeros(len(g0))
    if active_c:
        n_new[active_c] = np.maximum(ncv, 0.0)
    if aq_on:
        n_new[bar.iw] = nw
        g_eff = g0.copy()
        g_eff[ia] += gamma_
        n_new[ia] = nw * M_W * np.exp(np.minimum(A[ia] @ lam_ - g_eff[ia], 700))
    if gas_on:
        _, pg = _lse(A[bar.ig] @ lam_ - g0[bar.ig])
        n_new[bar.ig] = ng * pg
    return lam_, n_new, (nw if aq_on else 0.0), (ng if gas_on else 0.0), gamma_


def solve(p: EqProblem, max_outer: int = 40, newton_threshold: int = 12) -> EqResult:
    DEBUG_FORCE_NEWTON = os.environ.get("CHEM_AGENT_DEBUG_FORCE_NEWTON_AFTER")
    DEBUG_DISABLE_ANDERSON = os.environ.get("CHEM_AGENT_DEBUG_DISABLE_ANDERSON") == "1"
    A, g0 = p.A, p.g
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

    # Anderson
    anderson_m = 4
    X_hist: list[np.ndarray] = []
    F_hist: list[np.ndarray] = []
    damping = 1.0
    prev_diff = float("inf")
    anderson_fail = False

    for outer in range(max_outer):
        g = g0 + ln_gamma
        bar = _Barrier(p, g)
        pol = None
        if outer > 0 and lam is not None:
            pol = _polish(bar, lam, n, n_w, n_gas, scale)
        elif outer == 0 and p.warm is not None:
            pol = _polish(bar, *p.warm, scale)
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
        lg_new = p.gamma_fn(I_new, z, m=m_aq)
        I_val = I_new

        diff = float(np.max(np.abs(lg_new - ln_gamma[ia]))) if len(ia) else 0.0      
        if DEBUG_DISABLE_ANDERSON:
            anderson_fail = True
        if DEBUG_FORCE_NEWTON is not None:
            try:
                force_after = int(DEBUG_FORCE_NEWTON)
                if outer >= force_after:
                    anderson_fail = True
            except ValueError:
                pass

        # --- Production-фоллбэк: Anderson застрял ---
        if outer > newton_threshold and diff > 1e-4:
            anderson_fail = True
            msgs.append(f"Anderson не сошёлся за {newton_threshold} итераций — переключаемся на Newton")

        # --- Newton fallback (warm start) -
        # --- Переключение на Newton (только если Anderson сделал 3+ итерации) ---
        if anderson_fail:
            res = _polish_with_gamma(p, lam, n, n_w, n_gas, ln_gamma[ia], scale)
            if res is not None:
                lam, n, n_w, n_gas, gamma_new = res
                ln_gamma[ia] = gamma_new
                W = n_w * M_W
                m_aq = n[ia] / W if W > 0 else np.zeros(len(ia))
                I_val = p.fixed_I if p.fixed_I is not None else 0.5 * float(np.sum(m_aq * z ** 2))
                lg_check = p.gamma_fn(I_val, z, m=m_aq) if W > 0 else ln_gamma[ia]
                diff = float(np.max(np.abs(lg_check - ln_gamma[ia])))
                msgs.append(f"[Newton] итерация {outer}: |γ - f| = {diff:.2e}")
                # После успешного Newton сбрасываем флаг, чтобы не запускать его снова
                anderson_fail = False
                if diff < 1e-8:
                    converged = True
                    break
            else:
                msgs.append(f"[Newton] итерация {outer}: не сошёлся, продолжаем Anderson")
                anderson_fail = False  # отдаём управление Anderson

        x_cur = ln_gamma[ia].copy()
        f_cur = lg_new.copy()
        X_hist.append(x_cur)
        F_hist.append(f_cur)
        if len(X_hist) > anderson_m:
            X_hist.pop(0)
            F_hist.pop(0)

        if len(X_hist) == 1:
            ln_gamma[ia] = f_cur
        else:
            k = len(X_hist)
            R = np.array([F_hist[i] - X_hist[i] for i in range(k)])
            K = np.zeros((k + 1, k + 1))
            K[:k, :k] = R @ R.T
            K[:k, k] = 1.0
            K[k, :k] = 1.0
            rhs = np.zeros(k + 1)
            rhs[k] = 1.0
            try:
                sol = np.linalg.solve(K, rhs)
                c = sol[:k]
            except np.linalg.LinAlgError:
                c = np.zeros(k)
                c[-1] = 1.0
            ln_gamma_anderson = sum(ci * F_hist[i] for i, ci in enumerate(c))
            if diff >= prev_diff * 0.95:
                damping = max(0.3, damping * 0.7)
            else:
                damping = min(1.0, damping * 1.2)
            ln_gamma[ia] = (1.0 - damping) * f_cur + damping * ln_gamma_anderson

        prev_diff = diff

        if diff < 1e-8:
            converged = True
            break
    bb = np.abs(p.b)
    denom = np.where(bb > 1e-6 * scale, bb, 1e-6 * scale)
    resid = float(np.max(np.abs(A.T @ n - p.b) / denom))
    if resid > 1e-6:
        msgs.append(f"Невязка баланса масс {resid:.2e}")
    if not converged:
        msgs.append("Коэффициенты активности не сошлись за отведенное число итераций")

    return EqResult(
        n=n, lam=lam, ln_gamma=ln_gamma, ionic_strength=I_val,
        water_kg=n_w * M_W,
        converged=converged and resid < 1e-5 and not polish_failed,
        iterations=total_iter, residual=resid, gas_total=n_gas, messages=msgs,
    )