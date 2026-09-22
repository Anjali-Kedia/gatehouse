from gatehouse.reason_codes import ReasonCode
from gatehouse.tools import (
    check_change_delivery_address,
    check_issue_refund,
    check_refund_eligibility,
    run_hard_rules,
)

COMPLETE_ADDRESS = {"line1": "9 New St", "city": "Boston", "postal_code": "02108", "country": "US"}


def test_get_order_allows_owner(db_session, sandbox_session_id):
    result = run_hard_rules(db_session, sandbox_session_id, "get_order", {"order_ref": "1001"})
    assert result.ok
    assert result.data["order_ref"] == "1001"


def test_get_order_blocks_other_customers_order(db_session, sandbox_session_id):
    result = run_hard_rules(db_session, sandbox_session_id, "get_order", {"order_ref": "1003"})
    assert not result.ok
    assert ReasonCode.NOT_OWNER in result.reason_codes


def test_get_order_not_found(db_session, sandbox_session_id):
    result = run_hard_rules(db_session, sandbox_session_id, "get_order", {"order_ref": "9999"})
    assert not result.ok
    assert ReasonCode.ORDER_NOT_FOUND in result.reason_codes


def test_refund_eligibility_true_when_balance_remains(db_session, sandbox_session_id):
    result = check_refund_eligibility(db_session, sandbox_session_id, "1001")
    assert result.ok
    assert result.data["eligible"] is True


def test_refund_eligibility_false_when_already_refunded(db_session, sandbox_session_id):
    result = check_refund_eligibility(db_session, sandbox_session_id, "1002")
    assert result.ok
    assert result.data["eligible"] is False


def test_issue_refund_ok_within_balance(db_session, sandbox_session_id):
    result = check_issue_refund(db_session, sandbox_session_id, "1001", 4000)
    assert result.ok


def test_issue_refund_blocks_over_balance(db_session, sandbox_session_id):
    result = check_issue_refund(db_session, sandbox_session_id, "1001", 999_999)
    assert not result.ok
    assert ReasonCode.INSUFFICIENT_BALANCE in result.reason_codes


def test_issue_refund_blocks_already_refunded_order(db_session, sandbox_session_id):
    result = check_issue_refund(db_session, sandbox_session_id, "1002", 100)
    assert not result.ok
    assert ReasonCode.ALREADY_REFUNDED in result.reason_codes


def test_issue_refund_blocks_non_owner(db_session, sandbox_session_id):
    result = check_issue_refund(db_session, sandbox_session_id, "1003", 100)
    assert not result.ok
    assert ReasonCode.NOT_OWNER in result.reason_codes


def test_issue_refund_blocks_invalid_amount(db_session, sandbox_session_id):
    result = check_issue_refund(db_session, sandbox_session_id, "1001", 0)
    assert not result.ok
    assert ReasonCode.INVALID_AMOUNT in result.reason_codes


def test_change_address_ok_while_processing(db_session, sandbox_session_id):
    result = check_change_delivery_address(db_session, sandbox_session_id, "1005", COMPLETE_ADDRESS)
    assert result.ok


def test_change_address_blocks_after_shipped(db_session, sandbox_session_id):
    result = check_change_delivery_address(db_session, sandbox_session_id, "1004", COMPLETE_ADDRESS)
    assert not result.ok
    assert ReasonCode.SHIPMENT_ALREADY_DISPATCHED in result.reason_codes


def test_change_address_blocks_incomplete_address(db_session, sandbox_session_id):
    incomplete = {"line1": "9 New St", "city": "", "postal_code": "02108", "country": "US"}
    result = check_change_delivery_address(db_session, sandbox_session_id, "1005", incomplete)
    assert not result.ok
    assert ReasonCode.INCOMPLETE_ADDRESS in result.reason_codes


def test_unknown_tool_is_rejected(db_session, sandbox_session_id):
    result = run_hard_rules(db_session, sandbox_session_id, "delete_account", {})
    assert not result.ok
    assert ReasonCode.UNKNOWN_TOOL in result.reason_codes


def test_missing_argument_fails_closed_not_crashes(db_session, sandbox_session_id):
    result = run_hard_rules(db_session, sandbox_session_id, "issue_refund", {"order_ref": "1001"})
    assert not result.ok
    assert ReasonCode.INVALID_ARGUMENTS in result.reason_codes


def test_wrong_shaped_argument_fails_closed_not_crashes(db_session, sandbox_session_id):
    # new_address arriving as a string instead of a dict must not crash with an
    # unhandled AttributeError from the `.get()` call inside the check.
    result = run_hard_rules(
        db_session, sandbox_session_id, "change_delivery_address",
        {"order_ref": "1005", "new_address": "not a dict"},
    )
    assert not result.ok
    assert ReasonCode.INVALID_ARGUMENTS in result.reason_codes
