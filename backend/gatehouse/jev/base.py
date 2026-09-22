"""Adapter boundary between the decision policy and whichever Jev backend answers it.

The policy engine only ever sees `JevResult` or a `JevUnavailable` exception — it has
no idea whether the answer came from the live TypeSafe API or the mock heuristic used
during development. That's the point: swapping adapters is a config change, never a
policy-code change.
"""
from dataclasses import dataclass
from typing import Protocol

from gatehouse.reason_codes import ReasonCode


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class JevResult:
    match: ChoiceAnswer          # matches | contradicts | unclear
    explicit: ChoiceAnswer       # explicit | information_only | unclear
    specific: ChoiceAnswer       # sufficient | needs_clarification
    model: str
    latency_ms: float
    usage: dict[str, int] | None = None  # {"input_tokens": .., "output_tokens": ..} — real adapter only


class JevUnavailable(Exception):
    """Raised by an adapter for any failure mode: timeout, connection error, auth
    failure, or a response that doesn't parse into a JevResult. The policy engine
    treats all of these identically — REVIEW, execute nothing — because guessing
    which failure is "safe enough" to ignore is exactly the mistake this gateway
    exists to prevent.
    """

    def __init__(self, reason_code: ReasonCode, detail: str = ""):
        super().__init__(detail or reason_code.value)
        self.reason_code = reason_code


class JevAdapter(Protocol):
    def evaluate(
        self,
        *,
        user_request: str,
        proposed_tool: str,
        proposed_arguments: dict,
        context: dict,
    ) -> JevResult:
        """Answer the three fixed questions for one proposed action.

        Must raise `JevUnavailable` rather than return a partial or best-guess
        result — there is no valid `JevResult` that represents "I'm not sure this
        is right."
        """
        ...
