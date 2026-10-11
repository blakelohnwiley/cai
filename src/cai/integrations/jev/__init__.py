"""System One decision-model integration for CAI (Jev / Clef).

Jev (TypeSafe) and Clef (Cloudflare) evaluate unstructured *state* against
typed questions (noul / choice / score) and return calibrated probabilities.

Free path: Cloudflare Workers AI ``clef-flash`` via ``CAI_JEV_PROVIDER=cloudflare``
(10,000 Neurons/day). Paid: TypeSafe or OpenRouter. Not hosted for free on
GCP Vertex, AWS Bedrock, or Azure AI Foundry.

Docs: https://docs.typesafe.ai/ · https://developers.cloudflare.com/workers-ai/models/clef-flash/
"""

from cai.integrations.jev.client import (
    JevClient,
    JevError,
    JevResponse,
    is_jev_configured,
    resolve_provider,
)
from cai.integrations.jev.questions import choice, noul, score

__all__ = [
    "JevClient",
    "JevError",
    "JevResponse",
    "choice",
    "is_jev_configured",
    "noul",
    "resolve_provider",
    "score",
]
