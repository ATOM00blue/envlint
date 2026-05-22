"""Tiny Levenshtein implementation for typo suggestions (no deps)."""

from __future__ import annotations

from typing import Optional


def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(
                min(
                    previous[j] + 1,       # deletion
                    current[j - 1] + 1,    # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
        previous = current
    return previous[-1]


def closest(word: str, candidates: list[str], *, max_distance: int = 2) -> Optional[str]:
    """Return the closest candidate within ``max_distance``, else ``None``.

    Comparison is case-insensitive for matching but the original candidate
    casing is returned. An exact (case-insensitive) match is ignored because
    that means the key is not actually a typo.
    """
    word_l = word.lower()
    best: Optional[str] = None
    best_dist = max_distance + 1
    for cand in candidates:
        if cand == word:
            return None  # exact match -> not a typo
        dist = levenshtein(word_l, cand.lower())
        if dist == 0:
            continue
        if dist < best_dist:
            best_dist = dist
            best = cand
    return best
