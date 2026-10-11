"""Tests for Jev → Anthropic routing helpers."""

from __future__ import annotations

from cai.integrations.jev.anthropic_route import (
    TIER_TO_MODEL,
    apply_routing_rules,
)


def test_confident_sonnet_stays():
    decision = apply_routing_rules(
        {
            "anthropic_tier": {
                "type": "choice",
                "choice": "sonnet",
                "confidence": 0.9,
            },
            "task_family": {"type": "choice", "choice": "coding"},
            "complexity": {"type": "score", "score": 2.0},
            "needs_max_quality": {"type": "noul", "noul": 0.2},
        }
    )
    assert decision["tier"] == "sonnet"
    assert decision["model"] == TIER_TO_MODEL["sonnet"]


def test_haiku_upgrades_on_coding_complexity():
    decision = apply_routing_rules(
        {
            "anthropic_tier": {
                "type": "choice",
                "choice": "haiku",
                "confidence": 0.8,
            },
            "task_family": {"type": "choice", "choice": "coding"},
            "complexity": {"type": "score", "score": 1.8},
            "needs_max_quality": {"type": "noul", "noul": 0.1},
        }
    )
    assert decision["tier"] == "sonnet"
    assert "complexity_or_coding" in decision["upgrades"]


def test_hard_sonnet_to_opus():
    decision = apply_routing_rules(
        {
            "anthropic_tier": {
                "type": "choice",
                "choice": "sonnet",
                "confidence": 0.6,
            },
            "task_family": {"type": "choice", "choice": "coding"},
            "complexity": {"type": "score", "score": 3.2},
            "needs_max_quality": {"type": "noul", "noul": 0.7},
        }
    )
    assert decision["tier"] == "opus"
    assert decision["model"] == TIER_TO_MODEL["opus"]


def test_never_downgrade_confident_jev_tier():
    # Rules might try to keep haiku, but confident opus must stick.
    decision = apply_routing_rules(
        {
            "anthropic_tier": {
                "type": "choice",
                "choice": "opus",
                "confidence": 0.85,
            },
            "task_family": {"type": "choice", "choice": "chat"},
            "complexity": {"type": "score", "score": 0.2},
            "needs_max_quality": {"type": "noul", "noul": 0.0},
        }
    )
    assert decision["tier"] == "opus"
