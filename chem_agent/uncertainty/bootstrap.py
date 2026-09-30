"""'bootstrap' method: the same ensemble with uniform error distribution of equal variance.

A true bootstrap needs several independent measurements per species; the CRC tables give
one value each. The method is kept for the option name in the ТЗ and is documented as such.
"""
from __future__ import annotations

from .ensemble import draws


def bootstrap_draws(sigmas_rt, n: int, seed: int):
    return draws(sigmas_rt, n, seed, distribution="uniform")
