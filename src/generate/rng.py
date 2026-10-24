"""Deterministic random helpers.

Everything the generator draws is derived from ``(seed, *parts)`` so that two
runs with the same seed and the same dates produce byte-identical files,
independent of iteration order.
"""

from __future__ import annotations

import hashlib

import numpy as np

_MASK = (1 << 63) - 1


def hash_int(*parts: object) -> int:
    payload = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") & _MASK


def stable_id(prefix: str, *parts: object, width: int = 12) -> str:
    """A readable ID derived from natural-key parts instead of a counter.

    Counters shift whenever a run produces a different number of rows before
    the current position (an increment that adds hires, for example). Hashing
    the natural key keeps the same entity on the same ID in every process and
    every run length.
    """
    return f"{prefix}{hash_int(*parts):016x}"[: len(prefix) + width].upper()


def sub_rng(seed: int, *parts: object) -> np.random.Generator:
    """A generator seeded deterministically from ``seed`` and ``parts``."""
    return np.random.default_rng([int(seed) & _MASK, hash_int(*parts)])


def weighted_choice(rng: np.random.Generator, options, weights):
    return options[int(rng.choice(len(options), p=np.asarray(weights, dtype=float)))]


def exponential_wait(rng: np.random.Generator, hazard: float) -> float:
    """Days until the next event for a constant daily hazard."""
    if hazard <= 0:
        return float("inf")
    u = rng.random()
    if u <= 0:
        u = 1e-12
    return float(-np.log(u) / hazard)
