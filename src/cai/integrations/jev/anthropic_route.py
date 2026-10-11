"""Classify a prompt with Jev and pick an Anthropic Claude model tier."""

from __future__ import annotations

from typing import Any

from cai.integrations.jev.client import JevClient, JevError, JevResponse
from cai.integrations.jev.questions import choice, noul, score

TIER_TO_MODEL = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
    "fable": "claude-fable-5-1",
}

_TIER_ORDER = ("haiku", "sonnet", "opus", "fable")

DEFAULT_FALLBACK_MODEL = TIER_TO_MODEL["sonnet"]


def anthropic_routing_questions() -> dict[str, dict[str, Any]]:
    """Typed questions for prompt → Anthropic tier routing."""
    return {
        "anthropic_tier": choice(
            "Which Anthropic Claude tier should handle this prompt? Prefer the "
            "cheapest tier that can do the job well. Haiku for short/simple/"
            "latency-sensitive work. Sonnet for normal coding and multi-step "
            "agent work. Opus for hard coding, deep debugging, or high-stakes "
            "judgment. Fable only for demanding long-horizon reasoning that "
            "needs the top reasoning tier.",
            {
                "haiku": (
                    "Short, simple, latency-sensitive: classify, extract, "
                    "rewrite, FAQ, thin tool use."
                ),
                "sonnet": "Balanced default: coding, agents, design, multi-step analysis.",
                "opus": (
                    "Hard / high-stakes: complex codebases, subtle bugs, "
                    "enterprise judgment, long agent loops."
                ),
                "fable": (
                    "Demanding long-horizon reasoning or research-grade "
                    "planning beyond Sonnet/Opus."
                ),
            },
        ),
        "task_family": choice(
            "Primary task family of the prompt.",
            {
                "coding": "Write, edit, review, or debug code.",
                "reasoning": "Deep analysis, planning, math, research synthesis.",
                "writing": "Prose, docs, email, marketing copy.",
                "ops": "Commands, config, devops, incident triage.",
                "chat": "Casual Q&A or clarification with little work product.",
            },
        ),
        "complexity": score(
            "How demanding is this prompt for a coding/reasoning agent?",
            [
                "trivial — one-shot answer",
                "light — a few steps",
                "moderate — multi-file or multi-constraint",
                "hard — deep debugging or architecture",
                "extreme — long-horizon / research-grade",
            ],
        ),
        "needs_max_quality": noul(
            "Would a cheaper tier likely fail or produce a costly redo on this prompt?",
            true="Failure or redo risk is high if under-tiered.",
            false="A cheaper capable tier is fine.",
        ),
    }


def _bump(tier: str, steps: int = 1) -> str:
    try:
        idx = _TIER_ORDER.index(tier)
    except ValueError:
        return "sonnet"
    return _TIER_ORDER[min(idx + steps, len(_TIER_ORDER) - 1)]


def apply_routing_rules(answers: dict[str, Any]) -> dict[str, Any]:
    """Map Jev answers to a final Anthropic model id using deterministic rules."""
    tier_ans = answers.get("anthropic_tier") or {}
    family_ans = answers.get("task_family") or {}
    complexity_ans = answers.get("complexity") or {}
    max_q_ans = answers.get("needs_max_quality") or {}

    raw_tier = str(tier_ans.get("choice") or "sonnet").lower()
    if raw_tier not in TIER_TO_MODEL:
        raw_tier = "sonnet"
    tier_conf = float(tier_ans.get("confidence") or 0.0)
    family = str(family_ans.get("choice") or "chat").lower()
    complexity = float(complexity_ans.get("score") or 0.0)
    needs_max = float(max_q_ans.get("noul") or 0.0)

    tier = raw_tier
    upgrades: list[str] = []

    if needs_max >= 0.75 and tier_conf < 0.55:
        tier = _bump(tier)
        upgrades.append("low_confidence_max_quality")

    if tier == "haiku" and (
        complexity >= 2.0 or (family in ("coding", "reasoning") and complexity >= 1.5)
    ):
        tier = "sonnet"
        upgrades.append("complexity_or_coding")

    if tier == "sonnet" and complexity >= 3.0 and needs_max >= 0.6:
        tier = "opus"
        upgrades.append("hard_plus_max_quality")

    if (raw_tier == "fable") or (complexity >= 3.5 and needs_max >= 0.85):
        if tier != "fable":
            upgrades.append("extreme_reasoning")
        tier = "fable"

    # Never downgrade below Jev's choice when it was confident.
    if tier_conf >= 0.7:
        raw_idx = _TIER_ORDER.index(raw_tier)
        final_idx = _TIER_ORDER.index(tier)
        if final_idx < raw_idx:
            tier = raw_tier
            upgrades.append("restore_confident_jev_tier")

    return {
        "tier": tier,
        "model": TIER_TO_MODEL[tier],
        "raw_tier": raw_tier,
        "tier_confidence": tier_conf,
        "task_family": family,
        "complexity": complexity,
        "needs_max_quality": needs_max,
        "upgrades": upgrades,
    }


def route_prompt_to_anthropic(
    prompt: str,
    *,
    client: JevClient | None = None,
    hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Jev and return routing decision (or Sonnet fallback on error)."""
    state: dict[str, Any] = {"prompt": prompt}
    if hints:
        state["hints"] = hints

    try:
        jev = client or JevClient()
        response: JevResponse = jev.system_one(
            state=state,
            questions=anthropic_routing_questions(),
        )
    except JevError as exc:
        return {
            "tier": "sonnet",
            "model": DEFAULT_FALLBACK_MODEL,
            "raw_tier": "sonnet",
            "tier_confidence": 0.0,
            "task_family": "unknown",
            "complexity": 0.0,
            "needs_max_quality": 0.0,
            "upgrades": ["fallback_sonnet"],
            "error": str(exc),
            "provider": None,
            "jev_model": None,
            "request_id": getattr(exc, "request_id", None),
            "answers": {},
        }

    decision = apply_routing_rules(response.answers)
    decision.update(
        {
            "provider": response.provider,
            "jev_model": response.model,
            "request_id": response.request_id,
            "usage": response.usage,
            "answers": response.answers,
            "error": None,
        }
    )
    return decision
