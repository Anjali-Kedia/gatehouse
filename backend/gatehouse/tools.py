"""The four sandbox tools. Hard rules here are the source of truth and are
enforced regardless of what Jev or the agent says. Every check reloads state
from the database — proposed-action arguments are never trusted for
ownership, balance, or shipment-state facts.
"""
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session

from gatehouse.models import Execution, Order, RefundLedgerEntry, ShipmentState
from gatehouse.reason_codes import ReasonCode
from gatehouse.sandbox import ACTING_CUSTOMER_ID, load_order

READ_TOOLS = {"get_order", "check_refund_eligibility"}
WRITE_TOOLS = {"issue_refund", "change_delivery_address"}
ALL_TOOLS = READ_TOOLS | WRITE_TOOLS

REQUIRED_ADDRESS_FIELDS = ("line1", "city", "postal_code", "country")


@dataclass
class HardRuleResult:
    ok: bool
    reason_codes: list[ReasonCode] = field(default_factory=list)
    data: dict | None = None


def _ownership_check(order: Order | None, order_ref: str) -> HardRuleResult | None:
    if order is None:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.ORDER_NOT_FOUND])
    if order.owner_id != ACTING_CUSTOMER_ID:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.NOT_OWNER])
    return None


def check_get_order(db: Session, sandbox_session_id: str, order_ref: str) -> HardRuleResult:
    order = load_order(db, sandbox_session_id, order_ref)
    violation = _ownership_check(order, order_ref)
    if violation:
        return violation
    return HardRuleResult(
        ok=True,
        data={
            "order_ref": order.order_ref,
            "shipment_state": order.shipment_state.value,
            "total_amount_cents": order.total_amount_cents,
            "remaining_balance_cents": order.remaining_balance_cents,
            "address": {
                "line1": order.address_line1,
                "city": order.address_city,
                "postal_code": order.address_postal_code,
                "country": order.address_country,
            },
        },
    )


def check_refund_eligibility(db: Session, sandbox_session_id: str, order_ref: str) -> HardRuleResult:
    order = load_order(db, sandbox_session_id, order_ref)
    violation = _ownership_check(order, order_ref)
    if violation:
        return violation
    eligible = order.remaining_balance_cents > 0
    if not eligible:
        return HardRuleResult(
            ok=True,
            data={"eligible": False, "remaining_balance_cents": 0},
        )
    return HardRuleResult(
        ok=True,
        data={"eligible": True, "remaining_balance_cents": order.remaining_balance_cents},
    )


def check_issue_refund(
    db: Session, sandbox_session_id: str, order_ref: str, amount_cents: int
) -> HardRuleResult:
    order = load_order(db, sandbox_session_id, order_ref)
    violation = _ownership_check(order, order_ref)
    if violation:
        return violation
    if amount_cents <= 0:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.INVALID_AMOUNT])
    if order.remaining_balance_cents <= 0:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.ALREADY_REFUNDED])
    if amount_cents > order.remaining_balance_cents:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.INSUFFICIENT_BALANCE])
    return HardRuleResult(
        ok=True,
        data={
            "order_id": order.id,
            "order_ref": order.order_ref,
            "total_amount_cents": order.total_amount_cents,
            "remaining_balance_cents_before": order.remaining_balance_cents,
        },
    )


def check_change_delivery_address(
    db: Session, sandbox_session_id: str, order_ref: str, new_address: dict
) -> HardRuleResult:
    order = load_order(db, sandbox_session_id, order_ref)
    violation = _ownership_check(order, order_ref)
    if violation:
        return violation
    if order.shipment_state != ShipmentState.PROCESSING:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.SHIPMENT_ALREADY_DISPATCHED])
    missing = [f for f in REQUIRED_ADDRESS_FIELDS if not str(new_address.get(f, "")).strip()]
    if missing:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.INCOMPLETE_ADDRESS])
    return HardRuleResult(
        ok=True,
        data={
            "order_id": order.id,
            "order_ref": order.order_ref,
            "previous_address": {
                "line1": order.address_line1,
                "city": order.address_city,
                "postal_code": order.address_postal_code,
                "country": order.address_country,
            },
        },
    )


HARD_RULE_CHECKS = {
    "get_order": check_get_order,
    "check_refund_eligibility": check_refund_eligibility,
    "issue_refund": check_issue_refund,
    "change_delivery_address": check_change_delivery_address,
}


def run_hard_rules(db: Session, sandbox_session_id: str, tool: str, arguments: dict) -> HardRuleResult:
    check = HARD_RULE_CHECKS.get(tool)
    if check is None:
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.UNKNOWN_TOOL])
    try:
        return check(db, sandbox_session_id, **arguments)
    except (TypeError, AttributeError):
        # Malformed proposal — missing/extra arguments (TypeError from the call
        # itself) or a wrong-shaped one, e.g. `new_address` arriving as a string
        # instead of a dict (AttributeError from `.get()` inside the check). An
        # agent bug, not a permissions question — fail closed rather than crash.
        return HardRuleResult(ok=False, reason_codes=[ReasonCode.INVALID_ARGUMENTS])


# --- Write executors: called only after approval + hard-rule recheck pass, ---
# --- inside the single DB transaction that also writes the Execution row.  ---

def execute_issue_refund(db: Session, order: Order, amount_cents: int, execution_id: str) -> dict:
    order.refunded_amount_cents += amount_cents
    db.add(order)
    db.add(
        RefundLedgerEntry(
            sandbox_session_id=order.sandbox_session_id,
            order_id=order.id,
            execution_id=execution_id,
            amount_cents=amount_cents,
        )
    )
    return {
        "order_ref": order.order_ref,
        "refunded_amount_cents": amount_cents,
        "remaining_balance_cents": order.remaining_balance_cents,
    }


def execute_change_delivery_address(db: Session, order: Order, new_address: dict) -> dict:
    order.address_line1 = new_address["line1"]
    order.address_city = new_address["city"]
    order.address_postal_code = new_address["postal_code"]
    order.address_country = new_address["country"]
    db.add(order)
    return {"order_ref": order.order_ref, "address": new_address}
