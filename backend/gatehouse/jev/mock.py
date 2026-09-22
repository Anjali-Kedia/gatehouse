"""Deterministic keyword-heuristic stand-in for Jev, used for all development and
testing so iterating on the policy engine, persistence layer, and frontend doesn't
spend real API calls.

This is NOT a proxy for Jev's actual judgment quality — it exists purely to exercise
the CLARIFY/BLOCK/REVIEW/ALLOW code paths deterministically. Every result is tagged
`model="mock"` so it can never be mistaken for a live measurement in the UI, the
audit log, or the benchmark output. Only the benchmark's `--adapter live` runs and
`jev/real.py` speak to the actual API.
"""
import re
import time

from gatehouse.jev.base import ChoiceAnswer, JevResult
from gatehouse.tools import WRITE_TOOLS

_REFUND_SUBJECT = re.compile(r"refund|money back|charged|eligib", re.IGNORECASE)
_ADDRESS_SUBJECT = re.compile(r"address|deliver|ship", re.IGNORECASE)
# get_order is a general status lookup — almost any order-shaped question is "on
# subject" for it, unlike the narrower refund/address tools.
_ORDER_STATUS_SUBJECT = re.compile(r"order|status|deliver|ship|refund|address", re.IGNORECASE)
_INFO_ONLY_PHRASING = re.compile(
    r"\b(check|whether|can i|am i|is it|could i|would i|do i)\b", re.IGNORECASE
)
_EXPLICIT_ACTION_PHRASING = re.compile(
    r"\b(please (issue|refund|process|change|update)|go ahead|yes,? (please|refund|do it)"
    r"|issue (the|a|my) refund|refund me|update my address|change my address)\b",
    re.IGNORECASE,
)
_VAGUE_PHRASING = re.compile(r"\b(fix this|sort it out|do something|handle it|deal with it)\b", re.IGNORECASE)

_SUBJECT_BY_TOOL = {
    "get_order": _ORDER_STATUS_SUBJECT,
    "check_refund_eligibility": _REFUND_SUBJECT,
    "issue_refund": _REFUND_SUBJECT,
    "change_delivery_address": _ADDRESS_SUBJECT,
}


class MockJevAdapter:
    def evaluate(self, *, user_request: str, proposed_tool: str, proposed_arguments: dict, context: dict) -> JevResult:
        start = time.perf_counter()

        is_write = proposed_tool in WRITE_TOOLS
        subject_pattern = _SUBJECT_BY_TOOL.get(proposed_tool)
        on_subject = bool(subject_pattern and subject_pattern.search(user_request))
        explicit_hit = bool(_EXPLICIT_ACTION_PHRASING.search(user_request))
        info_only_hit = bool(_INFO_ONLY_PHRASING.search(user_request))
        vague_hit = bool(_VAGUE_PHRASING.search(user_request)) or len(user_request.strip()) < 8
        info_only_write = is_write and info_only_hit and not explicit_hit

        if vague_hit:
            specific = ChoiceAnswer("needs_clarification", 0.85, {"needs_clarification": 0.85, "sufficient": 0.15})
        else:
            specific = ChoiceAnswer("sufficient", 0.9, {"sufficient": 0.9, "needs_clarification": 0.1})

        if not is_write:
            explicit = ChoiceAnswer("explicit", 0.9, {"explicit": 0.9, "information_only": 0.05, "unclear": 0.05})
        elif explicit_hit and not info_only_hit:
            explicit = ChoiceAnswer("explicit", 0.9, {"explicit": 0.9, "information_only": 0.05, "unclear": 0.05})
        elif info_only_write:
            explicit = ChoiceAnswer("information_only", 0.9, {"information_only": 0.9, "explicit": 0.05, "unclear": 0.05})
        else:
            explicit = ChoiceAnswer("unclear", 0.5, {"unclear": 0.5, "explicit": 0.25, "information_only": 0.25})

        if vague_hit:
            match = ChoiceAnswer("unclear", 0.5, {"unclear": 0.5, "matches": 0.25, "contradicts": 0.25})
        elif info_only_write:
            match = ChoiceAnswer("contradicts", 0.9, {"contradicts": 0.9, "matches": 0.05, "unclear": 0.05})
        elif on_subject:
            match = ChoiceAnswer("matches", 0.9, {"matches": 0.9, "contradicts": 0.05, "unclear": 0.05})
        else:
            match = ChoiceAnswer("contradicts", 0.8, {"contradicts": 0.8, "matches": 0.1, "unclear": 0.1})

        return JevResult(
            match=match,
            explicit=explicit,
            specific=specific,
            model="mock",
            latency_ms=(time.perf_counter() - start) * 1000,
        )
