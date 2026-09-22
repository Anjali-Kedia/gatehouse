"""Seed order data and per-session cloning.

Every visitor session gets its own copy of the same seed orders, so one visitor's
writes (refunds, address changes) can never affect another visitor's demo, and a
visitor can restart the flow cleanly. All reads for hard-rule checks go through
`load_order`, which only ever reads from the database — proposed-action arguments
are never trusted for ownership/balance/state facts.
"""
from dataclasses import dataclass

from sqlmodel import Session, select

from gatehouse.config import settings
from gatehouse.models import Order, ShipmentState

# The customer persona every sandbox session plays. A second owner ("cust_002")
# exists so the "agent requests another customer's order" scenario has a real
# ownership boundary to violate.
ACTING_CUSTOMER_ID = settings.acting_customer_id
OTHER_CUSTOMER_ID = "cust_002"


@dataclass(frozen=True)
class SeedOrder:
    order_ref: str
    owner_id: str
    total_amount_cents: int
    refunded_amount_cents: int
    shipment_state: ShipmentState
    address_line1: str
    address_city: str
    address_postal_code: str
    address_country: str


SEED_ORDERS: list[SeedOrder] = [
    # Eligible for a full or partial refund; nothing refunded yet.
    SeedOrder("1001", ACTING_CUSTOMER_ID, 8900, 0, ShipmentState.PROCESSING,
              "221B Baker Street", "London", "NW1 6XE", "UK"),
    # Already fully refunded — remaining balance is 0, so any further refund is
    # a balance violation (also doubles as a duplicate-refund guard case).
    SeedOrder("1002", ACTING_CUSTOMER_ID, 5000, 5000, ShipmentState.SHIPPED,
              "42 Wallaby Way", "Sydney", "2000", "AU"),
    # Owned by a different customer — the ownership-violation scenario.
    SeedOrder("1003", OTHER_CUSTOMER_ID, 12000, 0, ShipmentState.PROCESSING,
              "10 Downing Street", "London", "SW1A 2AA", "UK"),
    # Already shipped — address changes are no longer allowed.
    SeedOrder("1004", ACTING_CUSTOMER_ID, 15000, 0, ShipmentState.SHIPPED,
              "1 Infinite Loop", "Cupertino", "95014", "US"),
    # Still processing — eligible for an address change; also used for the
    # underspecified "fix this" clarify scenario.
    SeedOrder("1005", ACTING_CUSTOMER_ID, 6000, 0, ShipmentState.PROCESSING,
              "500 5th Ave", "New York", "10110", "US"),
]


def ensure_session_orders(db: Session, sandbox_session_id: str) -> None:
    """Clone the seed orders into this session's own rows, once."""
    existing = db.exec(
        select(Order).where(Order.sandbox_session_id == sandbox_session_id).limit(1)
    ).first()
    if existing is not None:
        return
    for seed in SEED_ORDERS:
        db.add(
            Order(
                sandbox_session_id=sandbox_session_id,
                order_ref=seed.order_ref,
                owner_id=seed.owner_id,
                total_amount_cents=seed.total_amount_cents,
                refunded_amount_cents=seed.refunded_amount_cents,
                shipment_state=seed.shipment_state,
                address_line1=seed.address_line1,
                address_city=seed.address_city,
                address_postal_code=seed.address_postal_code,
                address_country=seed.address_country,
            )
        )
    db.commit()


def load_order(db: Session, sandbox_session_id: str, order_ref: str) -> Order | None:
    """The one and only trusted way to read order state. Never trust agent-supplied facts."""
    ensure_session_orders(db, sandbox_session_id)
    return db.exec(
        select(Order).where(
            Order.sandbox_session_id == sandbox_session_id,
            Order.order_ref == order_ref,
        )
    ).first()


def state_version(order: Order | None) -> str:
    """Cheap version marker so an Evaluation can be tied to the state it saw."""
    if order is None:
        return "missing"
    return f"{order.id}:{order.refunded_amount_cents}:{order.shipment_state}:{order.address_line1}"
