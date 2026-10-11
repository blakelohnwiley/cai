---
name: jev-anthropic-router
description: Classify the user's prompt with TypeSafe Jev (BeatAPI jev-1.13-free) and route it to the best Anthropic Claude model (Haiku / Sonnet / Opus / Fable). Use whenever the user asks which Claude model to use, wants model routing, runs /jev route, or wants cost-aware Anthropic selection before answering.
---

# Jev → Anthropic model router

Use **one free Jev call** to classify the prompt, then pick an Anthropic model and answer (or set `CAI_MODEL` / `--model`) with that choice. Do **not** use a chat model to choose the chat model.

## Route (Jev classifier)

| URL | Key | Model ID |
|---|---|---|
| `https://api.beatapi.io/v1/systemone` | `BEATAPI_API_KEY` | `jev-1.13-free` |

- BeatAPI is a third-party reseller of TypeSafe Jev — say so if asked.
- Free model only (`jev-1.13-free`). Do not switch to paid `jev-1.13` unless the user asks.
- Rate limit: **1 successful req/min** before first top-up; **10/min** after any top-up. Honor `Retry-After` on 429.
- Key must be in BeatAPI's default `auto` group. Never print or paste the key.

Load the key from the environment only:

```bash
# BEATAPI_API_KEY must already be set in the environment or host secrets.
test -n "$BEATAPI_API_KEY" || { echo "BEATAPI_API_KEY missing"; exit 1; }
```

## Anthropic targets (Claude API IDs)

| Tier | API ID | Use when |
|---|---|---|
| **Haiku** | `claude-haiku-5-5` | Short, latency-sensitive: classify, extract, rewrite, simple Q&A, thin tooling |
| **Sonnet** | `claude-sonnet-5-5` | Default for coding, agents, multi-step work, most product tasks |
| **Opus** | `claude-opus-5-5` | Hard coding, deep debugging, high-stakes enterprise judgment, long agent loops |
| **Fable** | `claude-fable-5-1` | Demanding reasoning / long-horizon planning where Sonnet/Opus still feel thin |

Aliases for older CAI catalogs (if the host only lists dated IDs): prefer the newest matching Haiku / Sonnet / Opus snapshot available in that host.

## Classification call (always this battery)

Send the user prompt (trim to fit: state + longest question ≤ 32K; total ≤ 64K) as `state`, with these questions in **one** request:

```json
{
  "model": "jev-1.13-free",
  "state": {
    "prompt": "<user prompt text>",
    "hints": {
      "has_code_or_diff": false,
      "approx_tokens": 0,
      "needs_tools": false
    }
  },
  "questions": {
    "anthropic_tier": {
      "type": "choice",
      "instructions": "Which Anthropic Claude tier should handle this prompt? Prefer the cheapest tier that can do the job well. Haiku for short/simple/latency-sensitive work. Sonnet for normal coding and multi-step agent work. Opus for hard coding, deep debugging, or high-stakes judgment. Fable only for demanding long-horizon reasoning that needs the top reasoning tier.",
      "criteria": {
        "haiku": "Short, simple, latency-sensitive: classify, extract, rewrite, FAQ, thin tool use.",
        "sonnet": "Balanced default: coding, agents, design, multi-step analysis.",
        "opus": "Hard / high-stakes: complex codebases, subtle bugs, enterprise judgment, long agent loops.",
        "fable": "Demanding long-horizon reasoning or research-grade planning beyond Sonnet/Opus."
      }
    },
    "task_family": {
      "type": "choice",
      "instructions": "Primary task family of the prompt.",
      "criteria": {
        "coding": "Write, edit, review, or debug code.",
        "reasoning": "Deep analysis, planning, math, research synthesis.",
        "writing": "Prose, docs, email, marketing copy.",
        "ops": "Commands, config, devops, incident triage.",
        "chat": "Casual Q&A or clarification with little work product."
      }
    },
    "complexity": {
      "type": "score",
      "instructions": "How demanding is this prompt for a coding/reasoning agent?",
      "criteria": [
        "trivial — one-shot answer",
        "light — a few steps",
        "moderate — multi-file or multi-constraint",
        "hard — deep debugging or architecture",
        "extreme — long-horizon / research-grade"
      ]
    },
    "needs_max_quality": {
      "type": "noul",
      "instructions": "Would a cheaper tier likely fail or produce a costly redo on this prompt?",
      "criteria": {
        "true": "Failure or redo risk is high if under-tiered.",
        "false": "A cheaper capable tier is fine."
      }
    }
  }
}
```

Fill `hints` from what you can observe without another model call (code fences, “debug”, tool needs, length). Hints are optional context for Jev; do not invent them.

### curl template

```bash
PROMPT_JSON=$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<'EOF'
USER_PROMPT_HERE
EOF
)

curl -sS https://api.beatapi.io/v1/systemone \
  -H "Authorization: Bearer $BEATAPI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"jev-1.13-free\",\"state\":{\"prompt\":$PROMPT_JSON},\"questions\":{...}}"
```

Prefer the host's HTTP client or CAI's `JevClient` / `/jev` instead of embedding secrets in shell history.

## How to turn answers into a model ID

Read `answers.anthropic_tier.choice` and `answers.anthropic_tier.confidence`, plus `complexity.score` and `needs_max_quality.noul`.

Deterministic post-rules (code owns the final pick):

1. Start with `anthropic_tier.choice` → map to API ID above.
2. **Upgrade one tier** if `needs_max_quality.noul ≥ 0.75` and confidence on the tier choice is `< 0.55`.
3. **Upgrade Haiku → Sonnet** if `complexity.score ≥ 2.0` (moderate+) or `task_family` is `coding` / `reasoning` with `complexity.score ≥ 1.5`.
4. **Upgrade Sonnet → Opus** if `complexity.score ≥ 3.0` (hard+) and `needs_max_quality.noul ≥ 0.6`.
5. **Upgrade Opus → Fable** only if tier choice was already `fable`, or `complexity.score ≥ 3.5` **and** `needs_max_quality.noul ≥ 0.85`.
6. **Never downgrade** below Jev's chosen tier when `anthropic_tier.confidence ≥ 0.7`.
7. If the Jev call fails (401/403/404/429 after retry): **default to `claude-sonnet-5-5`**, tell the user routing fell back, and continue.

### Confidence-gated announce

Before switching models, briefly tell the user:

```text
Routed via Jev → claude-sonnet-5-5
(tier=sonnet conf=0.81 · family=coding · complexity≈2.1 · max_quality=0.22)
```

Then proceed with that model. Do not ask the user to confirm unless they asked for interactive choice, or the upgrade rules moved **two** tiers above Jev's raw choice.

## CAI / Cursor wiring

When working inside CAI:

1. Prefer `BEATAPI_API_KEY` + `CAI_JEV_PROVIDER=beatapi`.
2. You may use the REPL helper once available:  
   `/jev route <prompt…>`  
   or the library client:

```python
from cai.integrations.jev import JevClient, choice, noul, score

client = JevClient()  # auto → beatapi when BEATAPI_API_KEY is set
resp = client.system_one(
    state={"prompt": user_prompt},
    questions={
        "anthropic_tier": choice(
            "Which Anthropic Claude tier should handle this prompt? Prefer cheapest sufficient.",
            {
                "haiku": "Short/simple/latency-sensitive",
                "sonnet": "Default coding/agents",
                "opus": "Hard/high-stakes",
                "fable": "Long-horizon reasoning top tier",
            },
        ),
        "task_family": choice(
            "Primary task family.",
            {
                "coding": None,
                "reasoning": None,
                "writing": None,
                "ops": None,
                "chat": None,
            },
        ),
        "complexity": score(
            "How demanding is this prompt?",
            [
                "trivial — one-shot answer",
                "light — a few steps",
                "moderate — multi-file or multi-constraint",
                "hard — deep debugging or architecture",
                "extreme — long-horizon / research-grade",
            ],
        ),
        "needs_max_quality": noul(
            "Would a cheaper tier likely fail or force a costly redo?",
            true="High redo risk if under-tiered",
            false="Cheaper capable tier is fine",
        ),
    },
)
tier = resp.choice("anthropic_tier")
```

3. Apply the post-rules, then set the session model (`/model <id>` or `CAI_MODEL`) before the heavy answer.

## Error handling

| Status | Action |
|---|---|
| 400 | Fix question body; do not invent answers |
| 401 | Missing/wrong `BEATAPI_API_KEY` — stop routing, ask user to set secret |
| 403 / 404 | Free model gone — tell user; default Sonnet; do not auto-switch to paid Jev |
| 429 | Wait `Retry-After`, retry once; else default Sonnet |
| 500 / 503 | Backoff once; else default Sonnet |

## What not to do

- Do not call Anthropic just to choose an Anthropic model.
- Do not send `temperature` / `top_p` / `seed` to Jev.
- Do not use OpenRouter/TypeSafe model IDs on the BeatAPI URL (or the reverse).
- Do not batch-route dozens of prompts on the free tier without respecting 1/min.

## Docs

- BeatAPI Decisions: https://docs.beatapi.io/decisions  
- Anthropic model IDs: https://docs.anthropic.com/en/docs/about-claude/models  
- Field names can change — prefer live docs over this skill when shipping production routers.
