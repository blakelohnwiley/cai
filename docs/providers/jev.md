# System One decisions (Jev / Clef)

CAI can call **System One** decision models for fast typed answers (noul / choice / score) — useful for injection screening and agent triage via `jev_decide`.

These are **not chat LLMs**. They return calibrated probabilities your code thresholds; they do not generate prose.

## Free path: BeatAPI `jev-1.13-free` (recommended)

BeatAPI exposes **TypeSafe Jev 1.13** at no charge:

| | |
|--|--|
| Endpoint | `POST https://api.beatapi.io/v1/systemone` |
| Model | `jev-1.13-free` |
| Cost | $0 input / $0 output — **zero balance OK**, no card required |
| Limit | 1 successful req/min before first top-up; up to 10/min after any top-up |

Same request/response contract as TypeSafe; only the base URL and model name change. Docs: [BeatAPI Decisions API](https://docs.beatapi.io/decisions).

```bash
export CAI_JEV_PROVIDER=beatapi
export BEATAPI_API_KEY="..."           # https://beatapi.io
# default model is jev-1.13-free
# export CAI_JEV_MODEL=jev-1.13-free
# paid on BeatAPI: CAI_JEV_MODEL=jev-1.13
```

## Alt free: Cloudflare Workers AI (`clef-flash`)

Jev-API-compatible **Clef-flash** uses Workers AI’s shared **10,000 Neurons/day**. Not the TypeSafe Jev weights — a Cloudflare decision model in the same family.

```bash
export CAI_JEV_PROVIDER=cloudflare
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="token-with-workers-ai-read"
```

## Paid: TypeSafe / OpenRouter

```bash
# TypeSafe direct
export CAI_JEV_PROVIDER=typesafe
export TYPESAFE_API_KEY="..."

# OpenRouter (no TypeSafe waitlist)
export CAI_JEV_PROVIDER=openrouter
export OPENROUTER_API_KEY="..."
```

## Auto provider selection

With `CAI_JEV_PROVIDER=auto` (default), CAI picks the first configured backend:

1. **BeatAPI** (`BEATAPI_API_KEY`) — free real Jev 1.13
2. Cloudflare (`CLOUDFLARE_ACCOUNT_ID` + token)
3. TypeSafe (`TYPESAFE_API_KEY`)
4. OpenRouter (`OPENROUTER_API_KEY`)

## Guardrails

When `CAI_GUARDRAILS=true` and any System One backend is configured, the input guardrail prefers Jev/Clef for prompt-injection screening (authorized-pentest-aware battery).

```bash
export CAI_GUARDRAILS=true
export BEATAPI_API_KEY=...
```

## Agent tool

`jev_decide` asks one typed question and returns JSON. Requires any configured backend above.

## GCP / AWS / Azure

There is no free managed Jev SKU on Vertex, Bedrock, or Azure AI Foundry. Use BeatAPI (or Cloudflare) from those clouds, or self-host a System One–compatible server and set `TYPESAFE_BASE_URL`.

## Example

See [`examples/cai/jev_decide_example.py`](../../examples/cai/jev_decide_example.py).
