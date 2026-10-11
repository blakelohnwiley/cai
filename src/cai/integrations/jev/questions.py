"""Builders for TypeSafe System One question dicts (HTTP API shape)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def noul(
    instructions: str,
    *,
    true: str | None = None,
    false: str | None = None,
) -> dict[str, Any]:
    """Yes/no question; answer ``noul`` is P(yes) in ``[0, 1]``."""
    question: dict[str, Any] = {
        "type": "noul",
        "instructions": instructions,
    }
    if true is not None or false is not None:
        question["criteria"] = {"true": true, "false": false}
    return question


def choice(
    instructions: str,
    criteria: Mapping[str, str | None],
) -> dict[str, Any]:
    """Pick one labeled option; answer includes ``choice`` and ``confidence``."""
    if not criteria:
        raise ValueError("choice criteria must be a non-empty mapping")
    return {
        "type": "choice",
        "instructions": instructions,
        "criteria": dict(criteria),
    }


def score(
    instructions: str,
    criteria: Sequence[str],
) -> dict[str, Any]:
    """Ordered rubric score; answer ``score`` may fall between levels."""
    levels = list(criteria)
    if len(levels) < 2:
        raise ValueError("score criteria must include at least two levels")
    return {
        "type": "score",
        "instructions": instructions,
        "criteria": levels,
    }
