"""System One decision-model integration for CAI (Jev / Clef).

Jev (TypeSafe) and Clef (Cloudflare) evaluate unstructured *state* against
typed questions (noul / choice / score) and return calibrated probabilities.

Free path: BeatAPI ``jev-1.13-free`` (``BEATAPI_API_KEY``, zero balance OK).
Alt free: Cloudflare Workers AI ``clef-flash`` Neurons. Paid: TypeSafe or OpenRouter.

Docs: https://docs.beatapi.io/decisions · https://docs.typesafe.ai/
"""

from cai.integrations.jev.anthropic_route import (
    apply_routing_rules,
    route_prompt_to_anthropic,
)
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
    "apply_routing_rules",
    "choice",
    "is_jev_configured",
    "noul",
    "resolve_provider",
    "route_prompt_to_anthropic",
    "score",
]
