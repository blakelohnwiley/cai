"""Agent tool: ask TypeSafe Jev for a typed decision."""

from __future__ import annotations

import json
from typing import Any

from cai.integrations.jev.client import JevClient, JevError, is_jev_configured
from cai.integrations.jev.questions import choice, noul, score
from cai.sdk.agents import function_tool


def _build_questions(
    question_type: str,
    instructions: str,
    criteria_json: str,
) -> dict[str, dict[str, Any]]:
    qtype = question_type.strip().lower()
    criteria_raw = criteria_json.strip()
    parsed: Any = None
    if criteria_raw:
        try:
            parsed = json.loads(criteria_raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"criteria_json must be valid JSON: {exc}") from exc

    if qtype == "noul":
        true = None
        false = None
        if isinstance(parsed, dict):
            true = parsed.get("true")
            false = parsed.get("false")
        return {"decision": noul(instructions, true=true, false=false)}

    if qtype == "choice":
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError(
                'choice requires criteria_json object, e.g. '
                '{"recon":"gather info","exploit":"attempt foothold"}'
            )
        return {"decision": choice(instructions, parsed)}

    if qtype == "score":
        if not isinstance(parsed, list) or len(parsed) < 2:
            raise ValueError(
                'score requires criteria_json array of >=2 levels, e.g. '
                '["low","medium","high"]'
            )
        return {"decision": score(instructions, [str(x) for x in parsed])}

    raise ValueError("question_type must be one of: noul, choice, score")


@function_tool
def jev_decide(
    state: str,
    instructions: str,
    question_type: str = "noul",
    criteria_json: str = "",
) -> str:
    """Ask a System One model (Jev / Clef) for a fast typed decision.

    Use for triage, routing, and confidence-gated checks — not for generating
    text or code.

    Free: BEATAPI_API_KEY (jev-1.13-free, zero balance OK), or Cloudflare
    clef-flash Neurons. Paid: TYPESAFE_API_KEY or OPENROUTER_API_KEY.

    Args:
        state: Unstructured context to evaluate (findings, message, etc.).
        instructions: The decision question in natural language.
        question_type: One of ``noul`` (yes/no), ``choice``, or ``score``.
        criteria_json: JSON criteria. For choice: object of label->description.
            For score: array of level descriptions. For noul: optional
            ``{"true":"...","false":"..."}``.

    Returns:
        JSON string with the typed answer, confidence (when available), and
        request metadata.
    """
    if not is_jev_configured():
        return json.dumps(
            {
                "error": "No System One backend configured",
                "hint": (
                    "Free: BEATAPI_API_KEY (jev-1.13-free at api.beatapi.io). "
                    "Alt: CLOUDFLARE_* (clef-flash). Paid: TYPESAFE_API_KEY / OPENROUTER_API_KEY."
                ),
            }
        )

    try:
        questions = _build_questions(question_type, instructions, criteria_json)
        client = JevClient()
        response = client.system_one(state=state, questions=questions)
        answer = response.answers.get("decision", {})
        payload: dict[str, Any] = {
            "provider": response.provider or client.provider,
            "model": response.model,
            "request_id": response.request_id,
            "usage": response.usage,
            "answer": answer,
        }
        return json.dumps(payload)
    except (JevError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
