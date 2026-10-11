"""HTTP client for System One decision models (Jev / Clef).

Backends (``CAI_JEV_PROVIDER``):

- ``beatapi`` — BeatAPI ``POST https://api.beatapi.io/v1/systemone`` with
  ``jev-1.13-free`` (TypeSafe Jev 1.13 at $0; zero balance OK; rate-limited).
  Needs ``BEATAPI_API_KEY``.
- ``cloudflare`` — Workers AI ``clef-flash`` (free daily Neurons) or paid
  ``typesafe/jev``. Needs ``CLOUDFLARE_ACCOUNT_ID`` + API token.
- ``typesafe`` — TypeSafe direct ``POST /v1/systemone`` (``TYPESAFE_API_KEY``).
- ``openrouter`` — OpenRouter System One API (``OPENROUTER_API_KEY``).
- ``auto`` (default) — prefer BeatAPI, then Cloudflare, TypeSafe, OpenRouter.

Uses ``httpx`` (CAI core dependency). Optional ``typesafe-sdk`` is not required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping

import httpx

Provider = Literal["auto", "beatapi", "cloudflare", "typesafe", "openrouter"]

DEFAULT_BEATAPI_BASE_URL = "https://api.beatapi.io"
DEFAULT_TYPESAFE_BASE_URL = "https://api.typesafe.ai"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api"
DEFAULT_BEATAPI_MODEL = "jev-1.13-free"
DEFAULT_TYPESAFE_MODEL = "jev-latest"
DEFAULT_CLOUDFLARE_MODEL = "clef-flash"
DEFAULT_OPENROUTER_MODEL = "typesafe/jev-1.13"
DEFAULT_TIMEOUT = 10.0

CLOUDFLARE_CLEF_MODELS = {
    "clef": "@cf/cloudflare/clef",
    "clef-flash": "@cf/cloudflare/clef-flash",
    "@cf/cloudflare/clef": "@cf/cloudflare/clef",
    "@cf/cloudflare/clef-flash": "@cf/cloudflare/clef-flash",
}

_VALID_PROVIDERS = frozenset({"auto", "beatapi", "cloudflare", "typesafe", "openrouter"})


class JevError(RuntimeError):
    """Raised when a System One request cannot be completed."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.request_id = request_id


@dataclass(frozen=True)
class JevResponse:
    """Normalized System One response."""

    model: str
    answers: dict[str, Any]
    usage: dict[str, Any]
    request_id: str | None = None
    provider: str | None = None
    raw: dict[str, Any] | None = None

    def noul(self, name: str) -> float:
        answer = self.answers[name]
        return float(answer["noul"])

    def choice(self, name: str) -> str:
        return str(self.answers[name]["choice"])

    def choice_confidence(self, name: str) -> float:
        return float(self.answers[name].get("confidence", 0.0))

    def score(self, name: str) -> float:
        return float(self.answers[name]["score"])

    def score_confidence(self, name: str) -> float:
        return float(self.answers[name].get("confidence", 0.0))


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def beatapi_configured() -> bool:
    return bool(_env("BEATAPI_API_KEY"))


def cloudflare_configured() -> bool:
    token = _env("CLOUDFLARE_API_TOKEN") or _env("CLOUDFLARE_AUTH_TOKEN")
    return bool(_env("CLOUDFLARE_ACCOUNT_ID") and token)


def typesafe_configured() -> bool:
    return bool(_env("TYPESAFE_API_KEY"))


def openrouter_configured() -> bool:
    return bool(_env("OPENROUTER_API_KEY"))


def resolve_provider(provider: str | None = None) -> Provider:
    """Pick an active backend from explicit value or ``CAI_JEV_PROVIDER``."""
    raw = (provider or _env("CAI_JEV_PROVIDER") or "auto").lower()
    if raw not in _VALID_PROVIDERS:
        raise JevError(
            f"Unknown CAI_JEV_PROVIDER={raw!r}; "
            "use auto, beatapi, cloudflare, typesafe, or openrouter"
        )
    if raw != "auto":
        return raw  # type: ignore[return-value]

    # Prefer real free Jev 1.13 via BeatAPI, then Cloudflare Clef Neurons.
    if beatapi_configured():
        return "beatapi"
    if cloudflare_configured():
        return "cloudflare"
    if typesafe_configured():
        return "typesafe"
    if openrouter_configured():
        return "openrouter"
    raise JevError(
        "No System One backend configured. Free Jev 1.13: set BEATAPI_API_KEY "
        "(model jev-1.13-free at https://api.beatapi.io — zero balance OK). "
        "Alt free: CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN (clef-flash Neurons). "
        "Paid: TYPESAFE_API_KEY or OPENROUTER_API_KEY."
    )


def is_jev_configured() -> bool:
    """True when any supported System One backend has credentials."""
    try:
        resolve_provider()
        return True
    except JevError:
        return False


def _default_model_for(provider: Provider) -> str:
    # CAI_JEV_MODEL always wins; TYPESAFE_DEFAULT_MODEL only applies to
    # TypeSafe/OpenRouter so it cannot override BeatAPI's free model id.
    if _env("CAI_JEV_MODEL"):
        return _env("CAI_JEV_MODEL")
    if provider == "beatapi":
        return DEFAULT_BEATAPI_MODEL
    if provider == "cloudflare":
        return DEFAULT_CLOUDFLARE_MODEL
    if provider == "openrouter":
        return _env("TYPESAFE_DEFAULT_MODEL") or DEFAULT_OPENROUTER_MODEL
    return _env("TYPESAFE_DEFAULT_MODEL") or DEFAULT_TYPESAFE_MODEL


class JevClient:
    """Minimal async/sync System One client with multi-backend routing."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        account_id: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._provider = resolve_provider(provider)
        self._timeout = timeout
        self._model = model or _default_model_for(self._provider)
        self._account_id = (account_id or _env("CLOUDFLARE_ACCOUNT_ID")).strip()
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = (api_key or "").strip()

        if self._provider == "beatapi":
            self._api_key = self._api_key or _env("BEATAPI_API_KEY")
            if not self._api_key:
                raise JevError(
                    "BEATAPI_API_KEY is required for beatapi backend. "
                    "Create a key at https://beatapi.io (jev-1.13-free needs no balance)."
                )
            self._base_url = (
                self._base_url
                or _env("BEATAPI_BASE_URL")
                or _env("TYPESAFE_BASE_URL")
                or DEFAULT_BEATAPI_BASE_URL
            )
        elif self._provider == "cloudflare":
            self._api_key = self._api_key or _env("CLOUDFLARE_API_TOKEN") or _env(
                "CLOUDFLARE_AUTH_TOKEN"
            )
            if not self._account_id or not self._api_key:
                raise JevError(
                    "Cloudflare backend needs CLOUDFLARE_ACCOUNT_ID and "
                    "CLOUDFLARE_API_TOKEN (Workers AI Read)."
                )
            self._base_url = (
                self._base_url
                or f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}"
            )
        elif self._provider == "openrouter":
            self._api_key = self._api_key or _env("OPENROUTER_API_KEY")
            if not self._api_key:
                raise JevError("OPENROUTER_API_KEY is required for openrouter backend")
            self._base_url = (
                self._base_url
                or _env("TYPESAFE_BASE_URL")
                or DEFAULT_OPENROUTER_BASE_URL
            )
        else:
            self._api_key = self._api_key or _env("TYPESAFE_API_KEY")
            if not self._api_key:
                raise JevError(
                    "TYPESAFE_API_KEY is required for typesafe backend. "
                    "Or use CAI_JEV_PROVIDER=beatapi with BEATAPI_API_KEY for free Jev."
                )
            self._base_url = (
                self._base_url
                or _env("TYPESAFE_BASE_URL")
                or DEFAULT_TYPESAFE_BASE_URL
            )

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "cai-framework-jev/1.0",
        }
        if self._provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/aliasrobotics/cai"
            headers["X-Title"] = "CAI Jev Integration"
        return headers

    def _endpoint_and_body(
        self,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
        *,
        model: str | None,
    ) -> tuple[str, dict[str, Any]]:
        if state is None:
            raise JevError("State is required.")
        if not questions:
            raise JevError("At least one question is required.")

        selected = model or self._model

        if self._provider == "cloudflare":
            return self._cloudflare_endpoint_and_body(state, questions, selected)

        # BeatAPI, TypeSafe, and OpenRouter share the System One body shape.
        return (
            f"{self._base_url}/v1/systemone",
            {
                "state": state,
                "model": selected,
                "questions": dict(questions),
            },
        )

    def _cloudflare_endpoint_and_body(
        self,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
        selected: str,
    ) -> tuple[str, dict[str, Any]]:
        clef_path = CLOUDFLARE_CLEF_MODELS.get(selected)
        if clef_path is not None:
            short = "clef-flash" if "flash" in clef_path else "clef"
            return (
                f"{self._base_url}/ai/run/{clef_path}",
                {
                    "model": short,
                    "state": state,
                    "questions": dict(questions),
                },
            )

        model_id = selected if "/" in selected else f"typesafe/{selected}"
        return (
            f"{self._base_url}/ai/run",
            {
                "model": model_id,
                "input": {
                    "state": state,
                    "questions": dict(questions),
                },
            },
        )

    def _parse_response(self, response: httpx.Response) -> JevResponse:
        request_id = (
            response.headers.get("x-typesafe-request-id")
            or response.headers.get("cf-ray")
        )
        try:
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise JevError(
                f"Invalid JSON from {self._provider} ({response.status_code})",
                status=response.status_code,
                body=response.text,
                request_id=request_id,
            ) from exc

        if response.status_code >= 400:
            detail = data.get("detail", data) if isinstance(data, dict) else data
            if isinstance(data, dict) and "errors" in data:
                detail = data.get("errors") or detail
            if isinstance(data, dict) and "error" in data:
                detail = data.get("error") or detail
            raise JevError(
                f"{self._provider} API error {response.status_code}: {detail}",
                status=response.status_code,
                body=data,
                request_id=request_id,
            )

        payload = data
        if (
            self._provider == "cloudflare"
            and isinstance(data, dict)
            and "result" in data
            and "answers" not in data
        ):
            if data.get("success") is False:
                raise JevError(
                    f"Cloudflare AI error: {data.get('errors')}",
                    status=response.status_code,
                    body=data,
                    request_id=request_id,
                )
            payload = data.get("result")

        if not isinstance(payload, dict) or "answers" not in payload:
            raise JevError(
                f"{self._provider} response missing answers",
                status=response.status_code,
                body=data,
                request_id=request_id,
            )

        # BeatAPI adds an `id` field on top of the TypeSafe response shape.
        if not request_id and isinstance(payload, dict):
            rid = payload.get("id")
            if rid is not None:
                request_id = str(rid)

        return JevResponse(
            model=str(payload.get("model", self._model)),
            answers=dict(payload.get("answers") or {}),
            usage=dict(payload.get("usage") or {}),
            request_id=request_id,
            provider=self._provider,
            raw=data if isinstance(data, dict) else {"value": data},
        )

    def system_one(
        self,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
        *,
        model: str | None = None,
    ) -> JevResponse:
        """Synchronous System One evaluation."""
        endpoint, body = self._endpoint_and_body(state, questions, model=model)
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                endpoint,
                headers=self._headers(),
                json=body,
            )
        return self._parse_response(response)

    async def asystem_one(
        self,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
        *,
        model: str | None = None,
    ) -> JevResponse:
        """Async System One evaluation."""
        endpoint, body = self._endpoint_and_body(state, questions, model=model)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                endpoint,
                headers=self._headers(),
                json=body,
            )
        return self._parse_response(response)
