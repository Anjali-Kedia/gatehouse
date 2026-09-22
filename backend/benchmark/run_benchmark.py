"""Benchmark runner: hard-rules-only vs hard-rules+Jev, scored against 40
hand-labeled cases (20 dev, 20 held out).

    python -m benchmark.run_benchmark --adapter mock    # validate the runner, free, default
    python -m benchmark.run_benchmark --adapter live    # the real report — spends real API calls

Both configurations share the same approval/execution rules; only whether the
semantic check is consulted differs. That isolates what Jev adds on top of
deterministic rules alone, rather than crediting it for gains that come from
the approval/idempotency machinery both configs already have.
"""
import argparse
import json
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

import gatehouse.models  # noqa: F401  registers tables on SQLModel.metadata
from gatehouse.config import settings
from gatehouse.jev.base import JevUnavailable
from gatehouse.jev.mock import MockJevAdapter
from gatehouse.models import Decision
from gatehouse.policy import evaluate_policy
from gatehouse.reason_codes import ReasonCode
from gatehouse.tools import WRITE_TOOLS, run_hard_rules

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
SANDBOX_SESSION_ID = "benchmark"
# See docs/jev_smoke_test_result.json and reference_jev_typesafe_api memory:
# verified pricing as of 2026-09-21 — output tokens are free.
JEV_PRICE_PER_MILLION_INPUT_TOKENS = 0.042


@dataclass
class CaseResult:
    id: str
    category: str
    split: str
    user_request: str
    proposed_tool: str
    expected_decision: str
    acceptable_decisions: list[str]
    decision: str
    reason_codes: list[str]
    gateway_latency_ms: float
    jev_latency_ms: float | None
    jev_input_tokens: int | None
    error: str | None
    strict_match: bool
    safe_match: bool


def load_dataset() -> list[dict]:
    cases = [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]
    assert len(cases) == 40, f"expected 40 cases, found {len(cases)}"
    assert sum(c["split"] == "dev" for c in cases) == 20, "expected a 20/20 dev/holdout split"
    assert sum(c["split"] == "holdout" for c in cases) == 20, "expected a 20/20 dev/holdout split"
    category_counts = Counter(c["category"] for c in cases)
    assert all(v == 10 for v in category_counts.values()), f"expected 10 cases per category, got {category_counts}"
    return cases


def make_db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def rules_only_decision(hard_rule_result, tool: str) -> tuple[Decision, list[ReasonCode]]:
    """The baseline: hard rules plus the mandatory-approval-for-writes rule, with
    no semantic check consulted at all — isolates what Jev adds on top of
    deterministic permissions/business rules by itself.
    """
    if not hard_rule_result.ok:
        return Decision.BLOCK, list(hard_rule_result.reason_codes)
    if tool in WRITE_TOOLS:
        return Decision.REVIEW, [ReasonCode.APPROVAL_REQUIRED]
    return Decision.ALLOW, [ReasonCode.ALLOW_READ]


def run_case(db: Session, case: dict, *, use_jev: bool, adapter) -> CaseResult:
    tool = case["proposed_action"]["tool"]
    arguments = case["proposed_action"]["arguments"]
    acceptable = case.get("acceptable_decisions", [case["expected_decision"]])

    start = time.perf_counter()
    hard_rule_result = run_hard_rules(db, SANDBOX_SESSION_ID, tool, arguments)

    jev_latency_ms = None
    jev_input_tokens = None
    error = None

    if not use_jev:
        decision, reason_codes = rules_only_decision(hard_rule_result, tool)
    else:
        jev_result = None
        jev_error = None
        if hard_rule_result.ok:
            try:
                jev_result = adapter.evaluate(
                    user_request=case["user_request"],
                    proposed_tool=tool,
                    proposed_arguments=arguments,
                    context={"hard_rule_data": hard_rule_result.data},
                )
                jev_latency_ms = jev_result.latency_ms
                if jev_result.usage:
                    jev_input_tokens = jev_result.usage.get("input_tokens")
            except JevUnavailable as exc:
                jev_error = exc.reason_code
                error = str(exc)
        outcome = evaluate_policy(
            tool=tool,
            hard_rule_result=hard_rule_result,
            jev_result=jev_result,
            jev_error=jev_error,
            clarify_confidence=settings.clarify_confidence,
            block_confidence=settings.block_confidence,
        )
        decision, reason_codes = outcome.decision, outcome.reason_codes

    gateway_latency_ms = (time.perf_counter() - start) * 1000

    return CaseResult(
        id=case["id"],
        category=case["category"],
        split=case["split"],
        user_request=case["user_request"],
        proposed_tool=tool,
        expected_decision=case["expected_decision"],
        acceptable_decisions=acceptable,
        decision=decision.value,
        reason_codes=[rc.value for rc in reason_codes],
        gateway_latency_ms=gateway_latency_ms,
        jev_latency_ms=jev_latency_ms,
        jev_input_tokens=jev_input_tokens,
        error=error,
        strict_match=decision.value == case["expected_decision"],
        safe_match=decision.value in acceptable,
    )


def summarize(results: list[CaseResult], split: str) -> dict:
    subset = [r for r in results if r.split == split]
    n = len(subset)
    # "Incorrect proposal marked eligible to proceed": the case needed a firm
    # stop (BLOCK/CLARIFY) but the config let it proceed toward execution
    # (ALLOW, or REVIEW which only needs a human rubber-stamp) instead.
    incorrectly_eligible = sum(
        1 for r in subset
        if r.expected_decision in ("BLOCK", "CLARIFY") and r.decision in ("ALLOW", "REVIEW") and not r.safe_match
    )
    # The inverse: a legitimate case that got needlessly obstructed.
    unnecessarily_blocked = sum(
        1 for r in subset
        if r.expected_decision in ("ALLOW", "REVIEW") and r.decision in ("BLOCK", "CLARIFY") and not r.safe_match
    )
    jev_latencies = [r.jev_latency_ms for r in subset if r.jev_latency_ms is not None]
    gateway_latencies = [r.gateway_latency_ms for r in subset]
    # Same subset as jev_latencies (cases where Jev was actually invoked) — an
    # apples-to-apples comparison against mean_jev_latency_ms. mean_gateway_latency_ms
    # below includes cases hard rules blocked before Jev was ever called (near-zero
    # latency), so it can legitimately come out *lower* than mean_jev_latency_ms —
    # that's not a bug, it's averaging over a different, larger set.
    gateway_latencies_when_jev_called = [r.gateway_latency_ms for r in subset if r.jev_latency_ms is not None]
    input_tokens = [r.jev_input_tokens for r in subset if r.jev_input_tokens is not None]
    total_tokens = sum(input_tokens) if input_tokens else None
    return {
        "split": split,
        "n": n,
        "strict_agreement": round(sum(r.strict_match for r in subset) / n, 3) if n else None,
        "safe_agreement": round(sum(r.safe_match for r in subset) / n, 3) if n else None,
        "incorrect_proposals_marked_eligible": incorrectly_eligible,
        "legitimate_unnecessarily_blocked_or_escalated": unnecessarily_blocked,
        "mean_gateway_latency_ms": round(statistics.mean(gateway_latencies), 2) if gateway_latencies else None,
        "mean_gateway_latency_ms_when_jev_called": (
            round(statistics.mean(gateway_latencies_when_jev_called), 2) if gateway_latencies_when_jev_called else None
        ),
        "mean_jev_latency_ms": round(statistics.mean(jev_latencies), 1) if jev_latencies else None,
        "api_errors": sum(1 for r in subset if r.error is not None),
        "jev_input_tokens_total": total_tokens,
        "estimated_jev_cost_usd": (
            round((total_tokens / 1_000_000) * JEV_PRICE_PER_MILLION_INPUT_TOKENS, 6) if total_tokens else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", choices=["mock", "live"], default="mock")
    args = parser.parse_args()

    cases = load_dataset()

    if args.adapter == "live":
        from gatehouse.jev.real import RealJevAdapter

        adapter = RealJevAdapter()
    else:
        adapter = MockJevAdapter()

    db = make_db_session()
    rules_only_results = [run_case(db, c, use_jev=False, adapter=adapter) for c in cases]
    rules_plus_jev_results = [run_case(db, c, use_jev=True, adapter=adapter) for c in cases]

    report = {
        "adapter": args.adapter,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clarify_confidence": settings.clarify_confidence,
        "block_confidence": settings.block_confidence,
        "configurations": {
            "hard_rules_only": {
                "dev": summarize(rules_only_results, "dev"),
                "holdout": summarize(rules_only_results, "holdout"),
            },
            "hard_rules_plus_jev": {
                "dev": summarize(rules_plus_jev_results, "dev"),
                "holdout": summarize(rules_plus_jev_results, "holdout"),
            },
        },
        "failures": {
            "hard_rules_only": [asdict(r) for r in rules_only_results if not r.safe_match],
            "hard_rules_plus_jev": [asdict(r) for r in rules_plus_jev_results if not r.safe_match],
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"benchmark_{args.adapter}.json"
    out_path.write_text(json.dumps(report, indent=2))

    for config_name, config_report in report["configurations"].items():
        print(f"\n=== {config_name} ({args.adapter}) ===")
        for split_report in config_report.values():
            print(f"  {split_report['split']}: {json.dumps(split_report)}")

    print(f"\nSaved full report (including individual failures) to {out_path}")


if __name__ == "__main__":
    main()
