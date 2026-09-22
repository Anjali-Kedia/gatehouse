"""End-to-end policy tests covering the 8 demo scenarios (hard rules + mock Jev +
decision policy, wired together exactly as the API layer will wire them).

Scenario numbering follows the product spec's demo-scenario table.
"""
import pytest

from gatehouse.config import settings
from gatehouse.jev.base import ChoiceAnswer, JevResult
from gatehouse.jev.mock import MockJevAdapter
from gatehouse.models import Decision
from gatehouse.policy import evaluate_policy
from gatehouse.reason_codes import ReasonCode
from gatehouse.tools import ALL_TOOLS, WRITE_TOOLS, HardRuleResult, run_hard_rules

adapter = MockJevAdapter()


def decide(db, sandbox_session_id, user_request, tool, arguments):
    hard_rule_result = run_hard_rules(db, sandbox_session_id, tool, arguments)
    if not hard_rule_result.ok:
        return evaluate_policy(
            tool=tool,
            hard_rule_result=hard_rule_result,
            jev_result=None,
            jev_error=None,
            clarify_confidence=settings.clarify_confidence,
            block_confidence=settings.block_confidence,
        )
    jev_result = adapter.evaluate(
        user_request=user_request, proposed_tool=tool, proposed_arguments=arguments, context={}
    )
    return evaluate_policy(
        tool=tool,
        hard_rule_result=hard_rule_result,
        jev_result=jev_result,
        jev_error=None,
        clarify_confidence=settings.clarify_confidence,
        block_confidence=settings.block_confidence,
    )


def test_scenario_1_read_order_status_allowed(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "What's the status of my order 1001?", "get_order", {"order_ref": "1001"},
    )
    assert outcome.decision == Decision.ALLOW


def test_scenario_2_eligibility_question_blocks_refund(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "Can you check whether my order 1001 qualifies for a refund?",
        "issue_refund", {"order_ref": "1001", "amount_cents": 8900},
    )
    assert outcome.decision == Decision.BLOCK
    assert ReasonCode.INFORMATION_ONLY_REQUEST in outcome.reason_codes


def test_scenario_3_explicit_eligible_refund_requires_approval(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "Please issue a refund for order 1001, I paid 89 dollars.",
        "issue_refund", {"order_ref": "1001", "amount_cents": 8900},
    )
    assert outcome.decision == Decision.REVIEW
    assert ReasonCode.APPROVAL_REQUIRED in outcome.reason_codes


def test_scenario_4_other_customers_order_blocked_by_ownership(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "What's the status of my order 1003?", "get_order", {"order_ref": "1003"},
    )
    assert outcome.decision == Decision.BLOCK
    assert ReasonCode.NOT_OWNER in outcome.reason_codes


def test_scenario_5_refund_exceeding_balance_blocked(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "Please issue a refund for order 1001.",
        "issue_refund", {"order_ref": "1001", "amount_cents": 20000},
    )
    assert outcome.decision == Decision.BLOCK
    assert ReasonCode.INSUFFICIENT_BALANCE in outcome.reason_codes


def test_scenario_6_vague_request_asks_for_clarification(db_session, sandbox_session_id):
    outcome = decide(
        db_session, sandbox_session_id,
        "fix this",
        "change_delivery_address",
        {"order_ref": "1005", "new_address": {"line1": "1 Elm St", "city": "Reno", "postal_code": "89501", "country": "US"}},
    )
    assert outcome.decision == Decision.CLARIFY
    assert ReasonCode.REQUEST_UNDERSPECIFIED in outcome.reason_codes


def test_scenario_8_jev_unavailable_forces_review_not_allow(db_session, sandbox_session_id):
    hard_rule_result = run_hard_rules(db_session, sandbox_session_id, "get_order", {"order_ref": "1001"})
    outcome = evaluate_policy(
        tool="get_order",
        hard_rule_result=hard_rule_result,
        jev_result=None,
        jev_error=ReasonCode.JEV_UNAVAILABLE,
        clarify_confidence=settings.clarify_confidence,
        block_confidence=settings.block_confidence,
    )
    assert outcome.decision == Decision.REVIEW
    assert ReasonCode.JEV_UNAVAILABLE in outcome.reason_codes


def test_uncertain_semantic_signal_goes_to_review():
    unclear = ChoiceAnswer("unclear", 0.4, {"unclear": 0.4, "matches": 0.3, "contradicts": 0.3})
    sufficient = ChoiceAnswer("sufficient", 0.9, {"sufficient": 0.9, "needs_clarification": 0.1})
    jev_result = JevResult(match=unclear, explicit=sufficient, specific=sufficient, model="mock", latency_ms=1.0)
    outcome = evaluate_policy(
        tool="get_order",
        hard_rule_result=HardRuleResult(ok=True),
        jev_result=jev_result,
        jev_error=None,
        clarify_confidence=settings.clarify_confidence,
        block_confidence=settings.block_confidence,
    )
    assert outcome.decision == Decision.REVIEW
    assert ReasonCode.SEMANTIC_UNCERTAIN in outcome.reason_codes


@pytest.mark.parametrize("tool", sorted(WRITE_TOOLS))
def test_writes_can_never_reach_allow_regardless_of_jev_output(tool):
    """Invariant: Jev can influence CLARIFY/BLOCK/REVIEW, but a write can never be
    ALLOWed by the policy — only explicit human approval at execution time can let
    a write proceed. Guards against a prompt-injected or corrupted Jev response
    ever being read as authorization.
    """
    confident_match = ChoiceAnswer("matches", 0.99, {"matches": 0.99, "contradicts": 0.0, "unclear": 0.01})
    confident_explicit = ChoiceAnswer("explicit", 0.99, {"explicit": 0.99, "information_only": 0.0, "unclear": 0.01})
    confident_specific = ChoiceAnswer("sufficient", 0.99, {"sufficient": 0.99, "needs_clarification": 0.01})
    jev_result = JevResult(
        match=confident_match, explicit=confident_explicit, specific=confident_specific,
        model="mock", latency_ms=1.0,
    )

    outcome = evaluate_policy(
        tool=tool,
        hard_rule_result=HardRuleResult(ok=True),
        jev_result=jev_result,
        jev_error=None,
        clarify_confidence=settings.clarify_confidence,
        block_confidence=settings.block_confidence,
    )
    assert outcome.decision != Decision.ALLOW
    assert outcome.decision == Decision.REVIEW
    assert ReasonCode.APPROVAL_REQUIRED in outcome.reason_codes


def test_all_tools_have_a_hard_rule_check():
    from gatehouse.tools import HARD_RULE_CHECKS

    assert set(HARD_RULE_CHECKS) == ALL_TOOLS
