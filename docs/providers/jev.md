# System One decisions (Jev / Clef)

CAI can call **System One** decision models for fast typed answers (noul / choice / score) — useful for injection screening and agent triage via `jev_decide`.

These are **not chat LLMs**. They return calibrated probabilities your code thresholds; they do not generate prose.

## Free path: Cloudflare Workers AI (`clef-flash`)

**GCP Vertex, AWS Bedrock, and Azure AI Foundry do not host Jev for free** (or at all in their model catalogs as of Oct 2026). The practical free hosted option is Cloudflare’s Jev-compatible **Clef-flash**, which draws from Workers AI’s shared **10,000 Neurons/day** free allocation (~3,455 Neurons per million input tokens).

```bash
export CAI_JEV_PROVIDER=cloudflare
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="token-with-workers-ai-read"
# default model is clef-flash
# export CAI_JEV_MODEL=clef-flash
```

Token setup: [Cloudflare API tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) with **Workers AI Read**. Model docs: [clef-flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/).

Paid upgrade on the same backend: `CAI_JEV_MODEL=clef` or `CAI_JEV_MODEL=typesafe/jev` (third-party Jev via Cloudflare AI Gateway — billed, not Neurons).

## Paid: TypeSafe Jev

```bash
export CAI_JEV_PROVIDER=typesafe
export TYPESAFE_API_KEY="..."
# optional
# export TYPESAFE_BASE_URL="https://api.typesafe.ai"
# export CAI_JEV_MODEL=jev-latest
```

Keys: [console.typesafe.ai/keys](https://console.typesafe.ai/keys). Docs: [docs.typesafe.ai](https://docs.typesafe.ai/).

## Paid: OpenRouter

No TypeSafe waitlist — bill Jev to an OpenRouter key:

```bash
export CAI_JEV_PROVIDER=openrouter
export OPENROUTER_API_KEY="..."
# export CAI_JEV_MODEL=typesafe/jev-1.13
```

## Auto provider selection

With `CAI_JEV_PROVIDER=auto` (default), CAI picks the first configured backend:

1. Cloudflare (`CLOUDFLARE_ACCOUNT_ID` + token)
2. TypeSafe (`TYPESAFE_API_KEY`)
3. OpenRouter (`OPENROUTER_API_KEY`)

## Guardrails

When `CAI_GUARDRAILS=true` and any System One backend is configured, the input guardrail prefers Jev/Clef for prompt-injection screening (authorized-pentest-aware battery — not a generic “block hacking” filter).

```bash
export CAI_GUARDRAILS=true
# optional overrides
# export CAI_JEV_GUARDRAILS=true
# export CAI_JEV_JAILBREAK_THRESHOLD=0.75
# export CAI_JEV_EXFIL_THRESHOLD=0.8
# export CAI_JEV_SEVERITY_BLOCK=2.0
```

Set `CAI_JEV_GUARDRAILS=false` to force the legacy LLM detector path.

## Agent tool

`jev_decide` asks one typed question and returns JSON:

```python
from cai.tools.misc.jev_decide import jev_decide

print(
    jev_decide(
        state="Web app returns 500 on /login; SQLi payload in username reflects in error",
        instructions="Should we prioritize SQL injection testing next?",
        question_type="noul",
    )
)
```

## Self-host on GCP / AWS / Azure

There is no free managed Jev SKU on those clouds. Options:

1. Use Cloudflare Neurons (above) from any CAI host.
2. Deploy an open System One–compatible server (e.g. Clef weights, Von, Laya) on Cloud Run / ECS / Azure Container Apps and point:

```bash
export CAI_JEV_PROVIDER=typesafe
export TYPESAFE_BASE_URL="https://your-systemone.example.com"
export TYPESAFE_API_KEY="local-or-gateway-token"
```

GPU free tiers on GCP/AWS/Azure are limited and usually not zero-cost for sustained inference; Cloudflare’s Neuron allotment is the straightforward free hosted path.

## Example

See [`examples/cai/jev_decide_example.py`](../../examples/cai/jev_decide_example.py).
