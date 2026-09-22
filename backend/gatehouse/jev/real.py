"""Real Jev adapter — wraps the TypeSafe SDK. Mirrors the request/response shape
already verified against the live API in scripts/jev_smoke_test.py.
"""
import time

from typesafe_sdk import Choice, TypeSafeAPIResponseValidationError, TypeSafeClient, TypeSafeError

from gatehouse.config import settings
from gatehouse.jev.base import ChoiceAnswer, JevResult, JevUnavailable
from gatehouse.reason_codes import ReasonCode

_MATCH_CRITERIA = {
    "matches": "The action directly fulfills what the user asked for.",
    "contradicts": "The action goes beyond or conflicts with what the user asked for.",
    "unclear": "Not enough information to tell.",
}
_EXPLICIT_CRITERIA = {
    "explicit": "The user directly asked for this specific action to be taken.",
    "information_only": "The user asked for information, not for this action to be taken.",
    "unclear": "Cannot tell from the request.",
}
_SPECIFIC_CRITERIA = {
    "sufficient": "The request has enough detail to act on safely.",
    "needs_clarification": "The request is missing key details needed to act safely.",
}


class RealJevAdapter:
    def __init__(self) -> None:
        if not settings.typesafe_api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set; cannot construct RealJevAdapter")
        self._client = TypeSafeClient(api_key=settings.typesafe_api_key, model=settings.jev_model)

    def evaluate(
        self, *, user_request: str, proposed_tool: str, proposed_arguments: dict, context: dict
    ) -> JevResult:
        state = {
            "user_request": user_request,
            "proposed_action": {"tool": proposed_tool, "arguments": proposed_arguments},
            "context": context,
        }
        start = time.perf_counter()
        try:
            response = self._client.system_one(
                state=state,
                questions={
                    "match": Choice(
                        instructions="Does the proposed action match what the user asked for?",
                        criteria=_MATCH_CRITERIA,
                    ),
                    "explicit": Choice(
                        instructions="Has the user explicitly requested this specific action?",
                        criteria=_EXPLICIT_CRITERIA,
                    ),
                    "specific": Choice(
                        instructions="Is the user's request specific enough to act on?",
                        criteria=_SPECIFIC_CRITERIA,
                    ),
                },
                timeout=settings.jev_timeout_seconds,
            )
        except TypeSafeAPIResponseValidationError as exc:
            raise JevUnavailable(ReasonCode.JEV_INVALID_RESPONSE, str(exc)) from exc
        except TypeSafeError as exc:
            # Timeouts, connection errors, auth failures, rate limits, 5xxs — every
            # other failure mode collapses to the same outcome: review it, don't guess.
            raise JevUnavailable(ReasonCode.JEV_UNAVAILABLE, str(exc)) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        try:
            match = response.choices["match"]
            explicit = response.choices["explicit"]
            specific = response.choices["specific"]
        except KeyError as exc:
            raise JevUnavailable(ReasonCode.JEV_INVALID_RESPONSE, f"Missing expected answer: {exc}") from exc

        return JevResult(
            match=ChoiceAnswer(match.choice, match.confidence, dict(match.probabilities)),
            explicit=ChoiceAnswer(explicit.choice, explicit.confidence, dict(explicit.probabilities)),
            specific=ChoiceAnswer(specific.choice, specific.confidence, dict(specific.probabilities)),
            model=response.model,
            latency_ms=latency_ms,
            usage=dict(response.usage.model_dump()),
        )
