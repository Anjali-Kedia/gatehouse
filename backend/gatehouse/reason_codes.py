"""Fixed reason codes. Jev never writes prose — the gateway maps outcomes to these."""
import enum


class ReasonCode(str, enum.Enum):
    # Hard rules (checked before Jev is ever called)
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    NOT_OWNER = "NOT_OWNER"
    ALREADY_REFUNDED = "ALREADY_REFUNDED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    SHIPMENT_ALREADY_DISPATCHED = "SHIPMENT_ALREADY_DISPATCHED"
    INCOMPLETE_ADDRESS = "INCOMPLETE_ADDRESS"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"

    # Jev availability / validity
    JEV_UNAVAILABLE = "JEV_UNAVAILABLE"
    JEV_INVALID_RESPONSE = "JEV_INVALID_RESPONSE"

    # Semantic outcomes
    SEMANTIC_UNCERTAIN = "SEMANTIC_UNCERTAIN"
    REQUEST_ACTION_MISMATCH = "REQUEST_ACTION_MISMATCH"
    INFORMATION_ONLY_REQUEST = "INFORMATION_ONLY_REQUEST"
    REQUEST_UNDERSPECIFIED = "REQUEST_UNDERSPECIFIED"

    # Allow / approval
    ALLOW_READ = "ALLOW_READ"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

    # Approval / execution outcomes
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_NOT_FOUND = "APPROVAL_NOT_FOUND"
    APPROVAL_ARGS_MISMATCH = "APPROVAL_ARGS_MISMATCH"
    APPROVAL_ALREADY_CONSUMED = "APPROVAL_ALREADY_CONSUMED"
    STATE_CHANGED_SINCE_EVALUATION = "STATE_CHANGED_SINCE_EVALUATION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    EXECUTION_REPLAYED = "EXECUTION_REPLAYED"


REASON_EXPLANATIONS: dict[ReasonCode, str] = {
    ReasonCode.ORDER_NOT_FOUND: "No such order exists in this sandbox.",
    ReasonCode.NOT_OWNER: "This order does not belong to the requesting customer.",
    ReasonCode.ALREADY_REFUNDED: "This order has no remaining refundable balance.",
    ReasonCode.INSUFFICIENT_BALANCE: "The requested refund amount exceeds the remaining balance.",
    ReasonCode.INVALID_AMOUNT: "The requested amount must be a positive number of cents.",
    ReasonCode.SHIPMENT_ALREADY_DISPATCHED: "The order has already shipped; the delivery address can no longer be changed.",
    ReasonCode.INCOMPLETE_ADDRESS: "The proposed address is missing required fields.",
    ReasonCode.UNKNOWN_TOOL: "The proposed tool is not one Gatehouse recognizes.",
    ReasonCode.INVALID_ARGUMENTS: "The proposed action's arguments don't match what this tool requires.",
    ReasonCode.JEV_UNAVAILABLE: "The semantic check was unavailable; the action requires human review.",
    ReasonCode.JEV_INVALID_RESPONSE: "The semantic check returned an invalid response; the action requires human review.",
    ReasonCode.SEMANTIC_UNCERTAIN: "The semantic check could not confidently determine intent; the action requires human review.",
    ReasonCode.REQUEST_ACTION_MISMATCH: "The proposed action contradicts what the user asked for.",
    ReasonCode.INFORMATION_ONLY_REQUEST: "The user asked for information, not for this action to be taken.",
    ReasonCode.REQUEST_UNDERSPECIFIED: "The user's request is not specific enough to act on.",
    ReasonCode.ALLOW_READ: "Read-only action permitted through the gateway.",
    ReasonCode.APPROVAL_REQUIRED: "This action changes state and requires human approval before it can execute.",
    ReasonCode.APPROVAL_EXPIRED: "The approval for this exact action has expired.",
    ReasonCode.APPROVAL_NOT_FOUND: "No approval was found for this exact action.",
    ReasonCode.APPROVAL_ARGS_MISMATCH: "The action's arguments changed since it was approved; the prior approval no longer applies.",
    ReasonCode.APPROVAL_ALREADY_CONSUMED: "This approval has already been used to execute an action.",
    ReasonCode.STATE_CHANGED_SINCE_EVALUATION: "Order state changed since this action was evaluated; it was re-blocked on execution.",
    ReasonCode.IDEMPOTENCY_CONFLICT: "This idempotency key was already used for a different action.",
    ReasonCode.EXECUTION_REPLAYED: "This exact execution was already performed; returning the original result.",
}
