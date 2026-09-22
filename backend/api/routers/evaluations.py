"""The five Gatehouse endpoints.

Design notes that matter for correctness, not just style:

- Every evaluation/approval/execution is scoped to `sandbox_session_id`. `approve`
  and `execute` both verify the caller's session matches the stored one — an
  evaluation ID by itself never grants access to someone else's sandbox.
- `execute` re-runs the hard rules against *current* state, never the state
  captured at evaluation time — that snapshot is only kept for the audit trail.
- Approval is required whenever `decision == REVIEW`, not just for writes. A read
  that reached REVIEW (Jev was unavailable, or the semantic signal was genuinely
  uncertain) still needs a human before Gatehouse will act on it.
- A cross-session lookup and a genuinely missing evaluation both return 404, not
  404-vs-403 — the two cases are made to look identical on purpose, so probing
  evaluation IDs can't be used to distinguish "not yours" from "doesn't exist."
"""
import time
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.schemas import (
    ApprovalResponse,
    EvaluationCreateRequest,
    EvaluationDetailResponse,
    EvaluationResponse,
    ExecuteRequest,
    ExecutionResponse,
)
from api.session import get_sandbox_session_id, verify_csrf
from gatehouse.config import settings
from gatehouse.db import get_session
from gatehouse.hashing import compute_action_hash
from gatehouse.jev import JevResult, JevUnavailable, get_jev_adapter
from gatehouse.models import (
    Approval,
    ApprovalStatus,
    Decision,
    Evaluation,
    Execution,
    ExecutionStatus,
)
from gatehouse.policy import evaluate_policy
from gatehouse.rate_limit import RateLimiter
from gatehouse.reason_codes import REASON_EXPLANATIONS, ReasonCode
from gatehouse.sandbox import load_order, state_version
from gatehouse.timeutil import as_utc, utcnow
from gatehouse.tools import (
    execute_change_delivery_address,
    execute_issue_refund,
    run_hard_rules,
)

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

# Per-session limit on evaluation creation — the only endpoint that can trigger
# a real, billed Jev call. Protects against a runaway client racking up API
# cost, not against a determined attacker (who can just clear cookies); see
# gatehouse/rate_limit.py for what a real deployment would need instead.
_evaluation_rate_limiter = RateLimiter(max_requests=settings.rate_limit_per_minute, window_seconds=60)


def _reason_error(status_code: int, reason_codes: list[ReasonCode]) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "reason_codes": [rc.value for rc in reason_codes],
            "reason_explanations": [REASON_EXPLANATIONS[rc] for rc in reason_codes],
        },
    )


def _serialize_jev_result(jev_result: JevResult | None) -> dict | None:
    if jev_result is None:
        return None
    return {
        "match": jev_result.match.__dict__,
        "explicit": jev_result.explicit.__dict__,
        "specific": jev_result.specific.__dict__,
        "model": jev_result.model,
        "latency_ms": jev_result.latency_ms,
    }


def _approval_response(approval: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        evaluation_id=approval.evaluation_id,
        status=approval.status.value,
        expires_at=as_utc(approval.expires_at),
        created_at=as_utc(approval.created_at),
        consumed_at=as_utc(approval.consumed_at) if approval.consumed_at else None,
    )


def _execution_response(execution: Execution, *, replayed: bool) -> ExecutionResponse:
    return ExecutionResponse(
        id=execution.id,
        evaluation_id=execution.evaluation_id,
        status=execution.status.value,
        result=execution.result,
        replayed=replayed,
        created_at=as_utc(execution.created_at),
    )


def _evaluation_response(evaluation: Evaluation) -> EvaluationResponse:
    return EvaluationResponse(
        id=evaluation.id,
        decision=evaluation.decision.value,
        reason_codes=list(evaluation.reason_codes),
        reason_explanations=[REASON_EXPLANATIONS[ReasonCode(rc)] for rc in evaluation.reason_codes],
        user_request=evaluation.user_request,
        proposed_tool=evaluation.proposed_tool,
        proposed_arguments=evaluation.proposed_arguments,
        hard_rule_result=evaluation.hard_rule_result,
        jev_result=evaluation.jev_result,
        gateway_latency_ms=evaluation.gateway_latency_ms,
        jev_latency_ms=evaluation.jev_latency_ms,
        jev_model_version=evaluation.jev_model_version,
        action_hash=evaluation.action_hash,
        created_at=as_utc(evaluation.created_at),
    )


@router.post("", response_model=EvaluationResponse, status_code=201, dependencies=[Depends(verify_csrf)])
def create_evaluation(
    body: EvaluationCreateRequest,
    db: Session = Depends(get_session),
    sandbox_session_id: str = Depends(get_sandbox_session_id),
) -> EvaluationResponse:
    if not _evaluation_rate_limiter.check(sandbox_session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Too many evaluations — limit is {settings.rate_limit_per_minute} per minute. Try again shortly.",
        )

    start = time.perf_counter()
    tool = body.proposed_action.tool
    arguments = body.proposed_action.arguments

    hard_rule_result = run_hard_rules(db, sandbox_session_id, tool, arguments)

    jev_result: JevResult | None = None
    jev_error: ReasonCode | None = None
    if hard_rule_result.ok:
        adapter = get_jev_adapter()
        try:
            jev_result = adapter.evaluate(
                user_request=body.user_request,
                proposed_tool=tool,
                proposed_arguments=arguments,
                context={"hard_rule_data": hard_rule_result.data},
            )
        except JevUnavailable as exc:
            jev_error = exc.reason_code

    outcome = evaluate_policy(
        tool=tool,
        hard_rule_result=hard_rule_result,
        jev_result=jev_result,
        jev_error=jev_error,
        clarify_confidence=settings.clarify_confidence,
        block_confidence=settings.block_confidence,
    )

    order_ref = arguments.get("order_ref")  # arguments is already a validated dict (ProposedAction.arguments)
    order = load_order(db, sandbox_session_id, order_ref) if order_ref else None

    evaluation = Evaluation(
        sandbox_session_id=sandbox_session_id,
        user_request=body.user_request,
        proposed_tool=tool,
        proposed_arguments=arguments,
        trusted_state_version=state_version(order),
        hard_rule_result={
            "ok": hard_rule_result.ok,
            "reason_codes": [rc.value for rc in hard_rule_result.reason_codes],
            "data": hard_rule_result.data,
        },
        jev_result=_serialize_jev_result(jev_result),
        jev_latency_ms=jev_result.latency_ms if jev_result else None,
        jev_model_version=jev_result.model if jev_result else None,
        gateway_latency_ms=(time.perf_counter() - start) * 1000,
        decision=outcome.decision,
        reason_codes=[rc.value for rc in outcome.reason_codes],
        action_hash=compute_action_hash(tool, arguments),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return _evaluation_response(evaluation)


@router.get("", response_model=list[EvaluationResponse])
def list_evaluations(
    db: Session = Depends(get_session),
    sandbox_session_id: str = Depends(get_sandbox_session_id),
) -> list[EvaluationResponse]:
    evaluations = db.exec(
        select(Evaluation)
        .where(Evaluation.sandbox_session_id == sandbox_session_id)
        .order_by(Evaluation.created_at.desc())
    ).all()
    return [_evaluation_response(e) for e in evaluations]


def _get_owned_evaluation(db: Session, evaluation_id: str, sandbox_session_id: str) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None or evaluation.sandbox_session_id != sandbox_session_id:
        # Deliberately identical for "doesn't exist" and "not yours" — see module docstring.
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.get("/{evaluation_id}", response_model=EvaluationDetailResponse)
def get_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_session),
    sandbox_session_id: str = Depends(get_sandbox_session_id),
) -> EvaluationDetailResponse:
    evaluation = _get_owned_evaluation(db, evaluation_id, sandbox_session_id)

    approval = db.exec(
        select(Approval)
        .where(Approval.evaluation_id == evaluation.id)
        .order_by(Approval.created_at.desc())
    ).first()
    execution = db.exec(
        select(Execution)
        .where(Execution.evaluation_id == evaluation.id)
        .order_by(Execution.created_at.desc())
    ).first()

    base = _evaluation_response(evaluation)
    return EvaluationDetailResponse(
        **base.model_dump(),
        approval=_approval_response(approval) if approval else None,
        execution=_execution_response(execution, replayed=False) if execution else None,
    )


@router.post("/{evaluation_id}/approve", response_model=ApprovalResponse, dependencies=[Depends(verify_csrf)])
def approve_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_session),
    sandbox_session_id: str = Depends(get_sandbox_session_id),
) -> ApprovalResponse:
    evaluation = _get_owned_evaluation(db, evaluation_id, sandbox_session_id)

    if evaluation.decision != Decision.REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"Evaluation decision is {evaluation.decision.value}; only REVIEW decisions can be approved.",
        )

    approval = Approval(
        evaluation_id=evaluation.id,
        sandbox_session_id=sandbox_session_id,
        action_hash=evaluation.action_hash,
        status=ApprovalStatus.APPROVED,
        approver=sandbox_session_id,
        expires_at=utcnow() + timedelta(minutes=settings.approval_ttl_minutes),
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return _approval_response(approval)


@router.post("/{evaluation_id}/execute", response_model=ExecutionResponse, dependencies=[Depends(verify_csrf)])
def execute_evaluation(
    evaluation_id: str,
    body: ExecuteRequest,
    db: Session = Depends(get_session),
    sandbox_session_id: str = Depends(get_sandbox_session_id),
) -> ExecutionResponse:
    evaluation = _get_owned_evaluation(db, evaluation_id, sandbox_session_id)

    if evaluation.decision not in (Decision.ALLOW, Decision.REVIEW):
        raise HTTPException(
            status_code=409,
            detail=f"Evaluation decision is {evaluation.decision.value}; nothing to execute.",
        )

    idempotency_key = body.idempotency_key or evaluation.id

    existing = db.exec(
        select(Execution).where(
            Execution.sandbox_session_id == sandbox_session_id,
            Execution.idempotency_key == idempotency_key,
        )
    ).first()
    if existing is not None:
        if existing.action_hash != evaluation.action_hash:
            raise _reason_error(409, [ReasonCode.IDEMPOTENCY_CONFLICT])
        return _execution_response(existing, replayed=True)

    # REVIEW always means a human must approve first — including reads that
    # landed in REVIEW because Jev was unavailable or genuinely uncertain, not
    # only writes. ALLOW is the only decision that skips this.
    approval: Approval | None = None
    if evaluation.decision == Decision.REVIEW:
        approval = db.exec(
            select(Approval)
            .where(
                Approval.sandbox_session_id == sandbox_session_id,
                Approval.action_hash == evaluation.action_hash,
            )
            .order_by(Approval.created_at.desc())
        ).first()
        if approval is None:
            raise _reason_error(403, [ReasonCode.APPROVAL_NOT_FOUND])
        if approval.status == ApprovalStatus.CONSUMED:
            raise _reason_error(409, [ReasonCode.APPROVAL_ALREADY_CONSUMED])
        if approval.status == ApprovalStatus.EXPIRED or approval.expires_at < utcnow():
            approval.status = ApprovalStatus.EXPIRED
            db.add(approval)
            db.commit()
            raise _reason_error(409, [ReasonCode.APPROVAL_EXPIRED])

    # Recheck against *current* state — not the snapshot the evaluation saw.
    hard_rule_result = run_hard_rules(db, sandbox_session_id, evaluation.proposed_tool, evaluation.proposed_arguments)
    if not hard_rule_result.ok:
        raise _reason_error(409, [ReasonCode.STATE_CHANGED_SINCE_EVALUATION, *hard_rule_result.reason_codes])

    execution_id = uuid.uuid4().hex
    order_ref = evaluation.proposed_arguments["order_ref"]
    order = load_order(db, sandbox_session_id, order_ref)
    if order is None:
        # Hard rules just confirmed this order exists and is owned by the caller,
        # so this branch is unreachable in practice — but never assume a caller
        # elsewhere can't skip run_hard_rules, so fail loudly instead of typing `order!`.
        raise _reason_error(409, [ReasonCode.ORDER_NOT_FOUND])

    if evaluation.proposed_tool == "issue_refund":
        result = execute_issue_refund(db, order, evaluation.proposed_arguments["amount_cents"], execution_id)
    elif evaluation.proposed_tool == "change_delivery_address":
        result = execute_change_delivery_address(db, order, evaluation.proposed_arguments["new_address"])
    else:
        result = hard_rule_result.data  # fresh read, re-fetched above

    # Consume whichever approval gated this execution — applies to any REVIEW
    # decision that required one, not only writes (see the REVIEW branch above).
    if approval is not None:
        approval.status = ApprovalStatus.CONSUMED
        approval.consumed_at = utcnow()
        db.add(approval)

    execution = Execution(
        id=execution_id,
        evaluation_id=evaluation.id,
        sandbox_session_id=sandbox_session_id,
        idempotency_key=idempotency_key,
        action_hash=evaluation.action_hash,
        status=ExecutionStatus.SUCCESS,
        result=result,
    )
    db.add(execution)
    try:
        db.commit()  # order mutation + ledger entry + approval consumption + execution row, one transaction
    except IntegrityError:
        # Two concurrent requests raced on the same idempotency key (e.g. a
        # double-click before the UI disabled the button) — both passed the
        # `existing is None` check above before either committed. The unique
        # constraint on (sandbox_session_id, idempotency_key) is the real
        # backstop; this just turns the loser's crash into a clean replay
        # instead of an unhandled 500, and rolling back discards its half-applied
        # mutation so only the winner's write actually persists.
        db.rollback()
        winner = db.exec(
            select(Execution).where(
                Execution.sandbox_session_id == sandbox_session_id,
                Execution.idempotency_key == idempotency_key,
            )
        ).first()
        if winner is not None and winner.action_hash == evaluation.action_hash:
            return _execution_response(winner, replayed=True)
        raise _reason_error(409, [ReasonCode.IDEMPOTENCY_CONFLICT]) from None
    db.refresh(execution)
    return _execution_response(execution, replayed=False)
