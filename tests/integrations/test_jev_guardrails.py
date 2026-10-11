"""Tests for Jev/Clef injection routing helpers."""

from __future__ import annotations

import pytest

from cai.integrations.jev.guardrails import (
    injection_battery,
    jev_guardrails_enabled,
    route_injection,
)


def test_injection_battery_keys():
    battery = injection_battery()
    assert set(battery) == {
        "jailbreak",
        "indirect_injection",
        "exfiltration",
        "severity",
    }
    assert battery["jailbreak"]["type"] == "noul"
    assert battery["severity"]["type"] == "score"


def test_route_injection_blocks_high_jailbreak():
    result = route_injection(
        {
            "jailbreak": {"type": "noul", "noul": 0.9},
            "indirect_injection": {"type": "noul", "noul": 0.1},
            "exfiltration": {"type": "noul", "noul": 0.1},
            "severity": {"type": "score", "score": 1.0, "confidence": 0.8},
        },
        jailbreak_threshold=0.75,
    )
    assert result["action"] == "blocked"
    assert any("jailbreak" in r for r in result["reasons"])


def test_route_injection_allows_clean():
    result = route_injection(
        {
            "jailbreak": {"type": "noul", "noul": 0.05},
            "indirect_injection": {"type": "noul", "noul": 0.04},
            "exfiltration": {"type": "noul", "noul": 0.02},
            "severity": {"type": "score", "score": 0.1, "confidence": 0.9},
        }
    )
    assert result["action"] == "allowed"


def test_jev_guardrails_auto(monkeypatch):
    monkeypatch.delenv("CAI_JEV_GUARDRAILS", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    assert jev_guardrails_enabled() is True

    monkeypatch.setenv("CAI_JEV_GUARDRAILS", "false")
    assert jev_guardrails_enabled() is False
