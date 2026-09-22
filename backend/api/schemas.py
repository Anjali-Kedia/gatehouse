from datetime import datetime

from pydantic import BaseModel, Field


class ProposedAction(BaseModel):
    tool: str = Field(max_length=64)
    arguments: dict = Field(default_factory=dict)


class EvaluationCreateRequest(BaseModel):
    # Bounded because this string flows straight into the real Jev API call —
    # unbounded input here is a trivial cost-abuse vector on a public demo.
    user_request: str = Field(max_length=2000)
    proposed_action: ProposedAction


class ChoiceAnswerOut(BaseModel):
    choice: str
    confidence: float
    probabilities: dict[str, float]


class JevResultOut(BaseModel):
    match: ChoiceAnswerOut
    explicit: ChoiceAnswerOut
    specific: ChoiceAnswerOut
    model: str
    latency_ms: float


class HardRuleResultOut(BaseModel):
    ok: bool
    reason_codes: list[str]
    data: dict | None = None


class EvaluationResponse(BaseModel):
    id: str
    decision: str
    reason_codes: list[str]
    reason_explanations: list[str]
    user_request: str
    proposed_tool: str
    proposed_arguments: dict
    hard_rule_result: HardRuleResultOut
    jev_result: JevResultOut | None = None
    gateway_latency_ms: float
    jev_latency_ms: float | None = None
    jev_model_version: str | None = None
    action_hash: str
    created_at: datetime


class ApprovalResponse(BaseModel):
    id: str
    evaluation_id: str
    status: str
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None = None


class ExecuteRequest(BaseModel):
    # Optional: omit to default to the evaluation id, which makes "click Execute
    # twice" and "click Retry" both naturally idempotent without any client-side
    # bookkeeping. Pass an explicit value only when the client wants to control
    # retry semantics itself (e.g. the benchmark runner issuing many distinct calls).
    idempotency_key: str | None = None


class ExecutionResponse(BaseModel):
    id: str
    evaluation_id: str
    status: str
    result: dict
    replayed: bool
    created_at: datetime


class EvaluationDetailResponse(EvaluationResponse):
    approval: ApprovalResponse | None = None
    execution: ExecutionResponse | None = None
