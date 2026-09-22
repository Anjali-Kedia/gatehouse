import enum
import uuid
from datetime import datetime

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint

from gatehouse.timeutil import utcnow


def _uuid() -> str:
    return uuid.uuid4().hex


class ShipmentState(str, enum.Enum):
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Decision(str, enum.Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CLARIFY = "CLARIFY"
    REVIEW = "REVIEW"


class ApprovalStatus(str, enum.Enum):
    # No PENDING state: an Approval row only exists once a human has
    # actually approved the exact action — there is no separate
    # request-approval step that materializes a row before that.
    APPROVED = "approved"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ExecutionStatus(str, enum.Enum):
    # Pre-flight rejections (missing/expired approval, state changed since
    # evaluation, idempotency-key conflict) are returned as request errors and
    # never persisted here — only a mutation that actually happened is an
    # Execution. There's no FAILED/CONFLICT status today because nothing in this
    # sandbox can fail *after* gating passes; a real external payment API would
    # need one, plus the reconciliation work that comes with it.
    SUCCESS = "success"


class Order(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    sandbox_session_id: str = Field(index=True)
    order_ref: str  # stable human label, e.g. "1001" — shared across template + every clone
    owner_id: str
    total_amount_cents: int
    refunded_amount_cents: int = 0
    shipment_state: ShipmentState
    address_line1: str
    address_city: str
    address_postal_code: str
    address_country: str
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def remaining_balance_cents(self) -> int:
        return self.total_amount_cents - self.refunded_amount_cents


class RefundLedgerEntry(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    sandbox_session_id: str = Field(index=True)
    order_id: str = Field(foreign_key="order.id", index=True)
    execution_id: str = Field(foreign_key="execution.id")
    amount_cents: int
    created_at: datetime = Field(default_factory=utcnow)


class Evaluation(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    sandbox_session_id: str = Field(index=True)
    user_request: str
    proposed_tool: str
    proposed_arguments: dict = Field(default_factory=dict, sa_column=Column(JSON))
    trusted_state_version: str
    hard_rule_result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    jev_result: dict | None = Field(default=None, sa_column=Column(JSON))
    jev_latency_ms: float | None = None
    jev_model_version: str | None = None
    gateway_latency_ms: float = 0.0
    decision: Decision
    reason_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    action_hash: str
    created_at: datetime = Field(default_factory=utcnow)


class Approval(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    evaluation_id: str = Field(foreign_key="evaluation.id", index=True)
    sandbox_session_id: str = Field(index=True)
    action_hash: str
    status: ApprovalStatus
    approver: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)
    consumed_at: datetime | None = None


class Execution(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("sandbox_session_id", "idempotency_key"),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    evaluation_id: str = Field(foreign_key="evaluation.id", index=True)
    sandbox_session_id: str = Field(index=True)
    idempotency_key: str = Field(index=True)
    action_hash: str
    status: ExecutionStatus
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
