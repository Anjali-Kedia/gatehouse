"""The ordered decision policy. Pure function, no I/O — takes the hard-rule outcome
and (optionally) a Jev result, returns a decision and the reason codes behind it.

Being pure and side-effect-free means it can be unit-tested directly against all 8
demo scenarios and reused by the benchmark runner to sweep confidence thresholds on
the dev split without re-calling Jev for every candidate value.
"""
from dataclasses import dataclass

from gatehouse.jev.base import JevResult
from gatehouse.models import Decision
from gatehouse.reason_codes import ReasonCode
from gatehouse.tools import WRITE_TOOLS, HardRuleResult


@dataclass(frozen=True)
class PolicyOutcome:
    decision: Decision
    reason_codes: list[ReasonCode]


def evaluate_policy(
    *,
    tool: str,
    hard_rule_result: HardRuleResult,
    jev_result: JevResult | None,
    jev_error: ReasonCode | None,
    clarify_confidence: float,
    block_confidence: float,
) -> PolicyOutcome:
    is_write = tool in WRITE_TOOLS

    # 1. Hard-rule violations are decided before Jev is ever consulted — a semantic
    #    model has no say over ownership, balance, or shipment state.
    if not hard_rule_result.ok:
        return PolicyOutcome(Decision.BLOCK, list(hard_rule_result.reason_codes))

    # 2. Jev unreachable or invalid -> a human decides, nothing executes. Silently
    #    falling back to "allow" here would make an outage a security bypass.
    if jev_error is not None:
        return PolicyOutcome(Decision.REVIEW, [jev_error])
    if jev_result is None:
        # Contract violation, not a user-facing state: an adapter must either return
        # a JevResult or raise JevUnavailable (mapped to jev_error above). Raising
        # here — rather than an assert that `python -O` could strip — keeps that
        # contract enforced even in an optimized deployment.
        raise ValueError("evaluate_policy requires jev_result whenever jev_error is None")

    # 3/5. Underspecified requests are asked to clarify — but only when Jev is
    #    actually confident the request is underspecified. A "needs_clarification"
    #    call sitting near a coin flip (e.g. 0.53 on a two-way choice) isn't a
    #    reliable enough signal to act on either way; that's what `clarify_confidence`
    #    is for, and it must gate this decision, not just exist as an unused knob.
    confident_underspecified = (
        jev_result.specific.choice == "needs_clarification"
        and jev_result.specific.confidence >= clarify_confidence
    )
    if confident_underspecified:
        return PolicyOutcome(Decision.CLARIFY, [ReasonCode.REQUEST_UNDERSPECIFIED])

    # 3. A genuinely uncertain match or intent signal goes to a human, not a coin
    #    flip — likewise a "needs_clarification" call that wasn't confident enough
    #    to act on above is itself an uncertain signal, not a green light to proceed.
    uncertain = (
        jev_result.match.choice == "unclear"
        or jev_result.explicit.choice == "unclear"
        or jev_result.specific.choice == "needs_clarification"
    )
    if uncertain:
        return PolicyOutcome(Decision.REVIEW, [ReasonCode.SEMANTIC_UNCERTAIN])

    # 4. A confident contradiction, or a confidently information-only request,
    #    blocks a write outright: asking about eligibility is not consent to act.
    if is_write:
        reasons: list[ReasonCode] = []
        if jev_result.match.choice == "contradicts" and jev_result.match.confidence >= block_confidence:
            reasons.append(ReasonCode.REQUEST_ACTION_MISMATCH)
        if jev_result.explicit.choice == "information_only" and jev_result.explicit.confidence >= block_confidence:
            reasons.append(ReasonCode.INFORMATION_ONLY_REQUEST)
        if reasons:
            return PolicyOutcome(Decision.BLOCK, reasons)

    # 6. Otherwise: reads pass through; writes still always need a human — Jev can
    #    recommend a route, it never grants permission to execute.
    if is_write:
        return PolicyOutcome(Decision.REVIEW, [ReasonCode.APPROVAL_REQUIRED])
    return PolicyOutcome(Decision.ALLOW, [ReasonCode.ALLOW_READ])
