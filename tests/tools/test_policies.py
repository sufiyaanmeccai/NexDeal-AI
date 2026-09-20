"""
tests/tools/test_policies.py — NexDeal AI  |  Phase 2

Tests for app/tools/policies.py.
Explicitly verifies that policy thresholds come from business_rules.json,
NOT from hardcoded Python constants.
Uses REAL Phase 1 data via data_loader.
"""

from decimal import Decimal

import pytest

from app.tools.policies import (
    ApprovalPolicyOutcome,
    CreditPolicyOutcome,
    DiscountPolicyOutcome,
    MarginPolicyOutcome,
    check_approval_policy,
    check_credit_policy,
    check_discount_policy,
    check_margin_policy,
)
from app.tools.customers import CustomerNotFoundError
from app.tools.data_loader import (
    get_approval_policy,
    get_credit_policy,
    get_discount_policy,
    get_margin_policy,
)


# ---------------------------------------------------------------------------
# Known customer data
# ---------------------------------------------------------------------------
# CUST-001: enterprise, discount_limit=20, credit_limit=500000, active, good
ENTERPRISE_ID = "CUST-001"
ENTERPRISE_LIMIT = 20
ENTERPRISE_CREDIT = Decimal("500000.00")

# CUST-002: premium, discount_limit=12, credit_limit=150000, active, good
PREMIUM_ID = "CUST-002"
PREMIUM_LIMIT = 12

# CUST-006: standard, discount_limit=5, credit_limit=30000, active, good
STANDARD_ID = "CUST-006"
STANDARD_LIMIT = 5

# CUST-003: standard, credit_hold, risk
CREDIT_HOLD_ID = "CUST-003"

# CUST-008: standard, suspended, risk, credit_limit=10000
SUSPENDED_ID = "CUST-008"
SUSPENDED_CREDIT = Decimal("10000.00")


class TestCheckDiscountPolicyThresholdsFromJSON:
    """These tests explicitly verify that thresholds come from JSON."""

    def test_enterprise_cap_matches_json_exactly(self):
        policy = get_discount_policy()
        json_cap = Decimal(str(policy["max_discount_by_tier"]["enterprise"]))
        # Exactly at cap → WITHIN_LIMIT
        result = check_discount_policy(ENTERPRISE_ID, json_cap)
        assert result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT
        assert result["tier_cap"] == json_cap

    def test_enterprise_one_above_cap_exceeds(self):
        policy = get_discount_policy()
        json_cap = Decimal(str(policy["max_discount_by_tier"]["enterprise"]))
        # CUST-001 discount_limit=20 which equals enterprise cap; +1 should exceed
        result = check_discount_policy(ENTERPRISE_ID, json_cap + 1)
        assert result["outcome"] == DiscountPolicyOutcome.EXCEEDS_LIMIT

    def test_premium_cap_matches_json(self):
        policy = get_discount_policy()
        json_cap = Decimal(str(policy["max_discount_by_tier"]["premium"]))
        # CUST-005 is premium tier with discount_limit=10; the tier cap is 15.
        # Proposing exactly the tier cap (15) exceeds CUST-005's personal limit (10).
        # Use CUST-007 (enterprise, discount_limit=15) for a clean cap equality test
        # -- instead verify the tier_cap key in the result equals the JSON value.
        result = check_discount_policy(PREMIUM_ID, 5)  # well within any limit
        assert result["tier_cap"] == json_cap, (
            f"tier_cap {result['tier_cap']} does not match JSON premium cap {json_cap}"
        )

    def test_standard_cap_matches_json(self):
        policy = get_discount_policy()
        json_cap = Decimal(str(policy["max_discount_by_tier"]["standard"]))
        result = check_discount_policy(STANDARD_ID, json_cap)
        assert result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT
        assert result["tier_cap"] == json_cap


class TestCheckDiscountPolicyOutcomes:
    def test_within_limit(self):
        result = check_discount_policy(ENTERPRISE_ID, 5)
        assert result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT

    def test_exceeds_limit(self):
        # Standard customer, cap=5; propose 10%
        result = check_discount_policy(STANDARD_ID, 10)
        assert result["outcome"] == DiscountPolicyOutcome.EXCEEDS_LIMIT

    def test_exceeds_by_correct_amount(self):
        result = check_discount_policy(STANDARD_ID, 8)
        # standard cap = 5, proposed = 8 → exceeds_by = 3
        assert result["exceeds_by"] == Decimal("3")

    def test_returns_required_keys(self):
        result = check_discount_policy(ENTERPRISE_ID, 10)
        required = {
            "customer_id", "customer_tier", "proposed_discount",
            "tier_cap", "customer_limit", "effective_cap", "outcome", "exceeds_by",
        }
        assert required.issubset(result.keys())

    def test_customer_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            check_discount_policy("CUST-999", 5)

    def test_negative_discount_raises_value_error(self):
        with pytest.raises(ValueError):
            check_discount_policy(ENTERPRISE_ID, -1)

    def test_discount_over_100_raises_value_error(self):
        with pytest.raises(ValueError):
            check_discount_policy(ENTERPRISE_ID, 101)

    def test_zero_discount_always_within_limit(self):
        for cid in [ENTERPRISE_ID, PREMIUM_ID, STANDARD_ID]:
            result = check_discount_policy(cid, 0)
            assert result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT


class TestCheckMarginPolicyThresholdsFromJSON:
    """Verify thresholds are read from margin_policy JSON, not hardcoded."""

    def test_absolute_minimum_from_json(self):
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        # At abs_min with no category: ACCEPTABLE (category_min == abs_min here)
        result = check_margin_policy(abs_min)
        assert result["absolute_minimum"] == abs_min

    def test_servers_category_minimum_from_json(self):
        policy = get_margin_policy()
        cat_min = Decimal(str(policy["minimum_margin_pct_by_category"]["Servers"]))
        result = check_margin_policy(cat_min, "Servers")
        assert result["category_minimum"] == cat_min

    def test_below_absolute_minimum_is_below_minimum(self):
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        result = check_margin_policy(abs_min - 1, "Servers")
        assert result["outcome"] == MarginPolicyOutcome.BELOW_MINIMUM

    def test_between_abs_and_category_min_is_low_margin_flag(self):
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        cat_min = Decimal(str(policy["minimum_margin_pct_by_category"]["Servers"]))
        # midpoint between abs_min and cat_min
        midpoint = (abs_min + cat_min) / 2
        if midpoint > abs_min and midpoint < cat_min:
            result = check_margin_policy(midpoint, "Servers")
            assert result["outcome"] == MarginPolicyOutcome.LOW_MARGIN_FLAG

    def test_at_category_minimum_is_acceptable(self):
        policy = get_margin_policy()
        cat_min = Decimal(str(policy["minimum_margin_pct_by_category"]["Servers"]))
        result = check_margin_policy(cat_min, "Servers")
        assert result["outcome"] == MarginPolicyOutcome.ACCEPTABLE

    def test_high_margin_is_acceptable(self):
        result = check_margin_policy(Decimal("50.00"), "Security")
        assert result["outcome"] == MarginPolicyOutcome.ACCEPTABLE

    def test_no_category_uses_absolute_minimum(self):
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        result = check_margin_policy(abs_min, None)
        assert result["outcome"] == MarginPolicyOutcome.ACCEPTABLE

    def test_unknown_category_uses_absolute_minimum(self):
        """Unknown category → no category_minimum → abs_min applies."""
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        result = check_margin_policy(abs_min, "Unicorn Products")
        # category_minimum should be None
        assert result["category_minimum"] is None
        assert result["outcome"] == MarginPolicyOutcome.ACCEPTABLE

    def test_returns_required_keys(self):
        result = check_margin_policy(25, "Servers")
        required = {
            "margin_percent", "product_category", "absolute_minimum",
            "category_minimum", "low_margin_flag_at", "outcome",
        }
        assert required.issubset(result.keys())


class TestCheckApprovalPolicyThresholdsFromJSON:
    def test_auto_approved_under_threshold(self):
        policy = get_approval_policy()
        auto_thresh = Decimal(str(policy["auto_approve_threshold_usd"]))
        result = check_approval_policy(auto_thresh - 1, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.AUTO_APPROVED

    def test_exact_auto_approve_boundary(self):
        """At exact auto-approve threshold ($25,000), order is AUTO_APPROVED (if no triggers)."""
        policy = get_approval_policy()
        auto_thresh = Decimal(str(policy["auto_approve_threshold_usd"]))
        result = check_approval_policy(auto_thresh, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.AUTO_APPROVED
        assert len(result["triggers_fired"]) == 0

    def test_just_above_auto_approve_boundary(self):
        """At $25,000.01, auto-approve threshold is exceeded → MANAGER_APPROVAL_REQUIRED."""
        policy = get_approval_policy()
        auto_thresh = Decimal(str(policy["auto_approve_threshold_usd"]))
        result = check_approval_policy(auto_thresh + Decimal("0.01"), 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED
        assert "order_value_exceeds_auto_approve_threshold" in result["triggers_fired"]

    def test_exact_manager_threshold_boundary(self):
        """At exact manager threshold ($75,000), outcome is MANAGER_APPROVAL_REQUIRED."""
        policy = get_approval_policy()
        mgr_thresh = Decimal(str(policy["manager_approval_threshold_usd"]))
        result = check_approval_policy(mgr_thresh, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED

    def test_just_above_manager_threshold_boundary(self):
        """At $75,000.01, outcome remains MANAGER_APPROVAL_REQUIRED (director requires > $250,000)."""
        policy = get_approval_policy()
        mgr_thresh = Decimal(str(policy["manager_approval_threshold_usd"]))
        result = check_approval_policy(mgr_thresh + Decimal("0.01"), 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED

    def test_manager_required_above_auto_threshold(self):
        policy = get_approval_policy()
        auto_thresh = Decimal(str(policy["auto_approve_threshold_usd"]))
        mgr_thresh = Decimal(str(policy["manager_approval_threshold_usd"]))
        mid = (auto_thresh + mgr_thresh) / 2
        result = check_approval_policy(mid, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED

    def test_exact_director_threshold_boundary(self):
        """At exact director threshold ($250,000), not yet strictly exceeding director limit."""
        policy = get_approval_policy()
        dir_thresh = Decimal(str(policy["director_approval_threshold_usd"]))
        result = check_approval_policy(dir_thresh, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED

    def test_just_above_director_threshold_boundary(self):
        """At $250,000.01, director approval is strictly required."""
        policy = get_approval_policy()
        dir_thresh = Decimal(str(policy["director_approval_threshold_usd"]))
        result = check_approval_policy(dir_thresh + Decimal("0.01"), 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.DIRECTOR_APPROVAL_REQUIRED

    def test_director_required_above_director_threshold(self):
        policy = get_approval_policy()
        dir_thresh = Decimal(str(policy["director_approval_threshold_usd"]))
        board_thresh = Decimal(str(policy["board_approval_threshold_usd"]))
        mid = (dir_thresh + board_thresh) / 2
        result = check_approval_policy(mid, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.DIRECTOR_APPROVAL_REQUIRED

    def test_exact_board_threshold_boundary(self):
        """At exact board threshold ($500,000), board threshold is not yet strictly exceeded."""
        policy = get_approval_policy()
        board_thresh = Decimal(str(policy["board_approval_threshold_usd"]))
        result = check_approval_policy(board_thresh, 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.DIRECTOR_APPROVAL_REQUIRED

    def test_just_above_board_threshold_boundary(self):
        """At $500,000.01, board approval is strictly required."""
        policy = get_approval_policy()
        board_thresh = Decimal(str(policy["board_approval_threshold_usd"]))
        result = check_approval_policy(board_thresh + Decimal("0.01"), 0, 30)
        assert result["outcome"] == ApprovalPolicyOutcome.BOARD_APPROVAL_REQUIRED


    def test_thresholds_returned_from_json(self):
        policy = get_approval_policy()
        result = check_approval_policy(0, 0, 30)
        assert result["auto_approve_threshold"] == Decimal(str(policy["auto_approve_threshold_usd"]))
        assert result["manager_threshold"] == Decimal(str(policy["manager_approval_threshold_usd"]))
        assert result["director_threshold"] == Decimal(str(policy["director_approval_threshold_usd"]))
        assert result["board_threshold"] == Decimal(str(policy["board_approval_threshold_usd"]))

    def test_discount_trigger_fires_when_exceeds_customer_limit(self):
        # STANDARD_ID has discount_limit=5; propose 10%
        result = check_approval_policy(0, 10, 30, customer_id=STANDARD_ID)
        assert "discount_exceeds_tier_limit" in result["triggers_fired"]

    def test_margin_trigger_fires_when_below_minimum(self):
        policy = get_margin_policy()
        abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
        result = check_approval_policy(0, 0, float(abs_min) - 1)
        assert "margin_below_category_minimum" in result["triggers_fired"]

    def test_triggers_fired_is_list(self):
        result = check_approval_policy(0, 0, 30)
        assert isinstance(result["triggers_fired"], list)

    def test_returns_required_keys(self):
        result = check_approval_policy(10000, 0, 25)
        required = {
            "order_value", "discount_percent", "margin_percent",
            "triggers_fired", "outcome",
            "auto_approve_threshold", "manager_threshold",
            "director_threshold", "board_threshold",
        }
        assert required.issubset(result.keys())

    def test_negative_order_value_raises(self):
        with pytest.raises(ValueError):
            check_approval_policy(-1, 0, 30)


class TestCheckCreditPolicyThresholdsFromJSON:
    def test_active_customer_within_limit_is_credit_ok(self):
        result = check_credit_policy(ENTERPRISE_ID, Decimal("10000.00"))
        assert result["outcome"] == CreditPolicyOutcome.CREDIT_OK

    def test_exceeds_credit_limit(self):
        # ENTERPRISE_ID credit_limit=500000; order $600,000
        result = check_credit_policy(ENTERPRISE_ID, Decimal("600000.00"))
        assert result["outcome"] == CreditPolicyOutcome.CREDIT_LIMIT_EXCEEDED

    def test_account_restricted_credit_hold(self):
        result = check_credit_policy(CREDIT_HOLD_ID, Decimal("100.00"))
        assert result["outcome"] == CreditPolicyOutcome.ACCOUNT_RESTRICTED

    def test_account_restricted_suspended(self):
        result = check_credit_policy(SUSPENDED_ID, Decimal("100.00"))
        assert result["outcome"] == CreditPolicyOutcome.ACCOUNT_RESTRICTED

    def test_credit_limit_from_json_not_hardcoded(self):
        """Verify the credit_limit in the result matches customers.json exactly."""
        result = check_credit_policy(ENTERPRISE_ID, Decimal("1.00"))
        assert result["credit_limit"] == ENTERPRISE_CREDIT

    def test_warning_threshold_from_json(self):
        policy = get_credit_policy()
        expected_warn = Decimal(str(policy["credit_utilisation_warning_pct"]))
        result = check_credit_policy(ENTERPRISE_ID, Decimal("1.00"))
        assert result["warning_threshold"] == expected_warn

    def test_block_threshold_from_json(self):
        policy = get_credit_policy()
        expected_block = Decimal(str(policy["credit_utilisation_block_pct"]))
        result = check_credit_policy(ENTERPRISE_ID, Decimal("1.00"))
        assert result["block_threshold"] == expected_block

    def test_utilisation_warning_true_when_near_limit(self):
        # $450,000 of $500,000 = 90% utilisation, warning threshold = 80%
        result = check_credit_policy(ENTERPRISE_ID, Decimal("450000.00"))
        assert result["utilisation_warning"] is True

    def test_utilisation_warning_false_when_far_below(self):
        # $1 of $500,000 = negligible utilisation
        result = check_credit_policy(ENTERPRISE_ID, Decimal("1.00"))
        assert result["utilisation_warning"] is False

    def test_utilisation_pct_correct(self):
        # $250,000 of $500,000 = 50.00%
        result = check_credit_policy(ENTERPRISE_ID, Decimal("250000.00"))
        assert result["utilisation_pct"] == Decimal("50.00")

    def test_returns_required_keys(self):
        result = check_credit_policy(ENTERPRISE_ID, Decimal("100.00"))
        required = {
            "customer_id", "order_value", "credit_limit", "account_status",
            "payment_history", "outcome", "utilisation_pct",
            "warning_threshold", "block_threshold", "utilisation_warning",
        }
        assert required.issubset(result.keys())

    def test_customer_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            check_credit_policy("CUST-999", Decimal("100.00"))

    def test_negative_order_value_raises(self):
        with pytest.raises(ValueError):
            check_credit_policy(ENTERPRISE_ID, Decimal("-1.00"))


class TestCrossToolConsistency:
    """Verify that policies are consistent with product and customer data."""

    def test_discount_policy_consistent_with_get_customer_credit_info(self):
        """check_discount_policy and get_customer_credit_info should agree on discount_limit."""
        from app.tools.customers import get_customer_credit_info
        info = get_customer_credit_info(ENTERPRISE_ID)
        disc_result = check_discount_policy(ENTERPRISE_ID, info["discount_limit"])
        # Discount limit from customers.json should always be WITHIN the tier cap
        assert disc_result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT

    def test_discount_policy_consistent_for_all_customers(self):
        """Every customer's own discount_limit must be within their tier cap."""
        from app.tools.data_loader import get_all_customers
        for c in get_all_customers():
            result = check_discount_policy(c["customer_id"], c["discount_limit"])
            assert result["outcome"] == DiscountPolicyOutcome.WITHIN_LIMIT, (
                f"Customer {c['customer_id']} discount_limit {c['discount_limit']} "
                f"exceeds their tier cap"
            )

    def test_credit_policy_blocks_credit_hold_customer(self):
        """credit_hold customer must always return ACCOUNT_RESTRICTED."""
        result = check_credit_policy(CREDIT_HOLD_ID, Decimal("1.00"))
        assert result["outcome"] == CreditPolicyOutcome.ACCOUNT_RESTRICTED
