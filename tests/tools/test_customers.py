"""
tests/tools/test_customers.py — NexDeal AI  |  Phase 2

Tests for app/tools/customers.py.
Uses REAL Phase 1 data from data/customers.json.
"""

import pytest

from app.tools.customers import (
    CustomerNotFoundError,
    check_customer_account_status,
    get_customer,
    get_customer_credit_info,
    get_customer_pricing_tier,
)
from app.tools.data_loader import get_all_customers


# ---------------------------------------------------------------------------
# Known data — values lifted directly from customers.json
# ---------------------------------------------------------------------------
# Active enterprise customer with good history
ENTERPRISE_ACTIVE_ID = "CUST-001"
ENTERPRISE_ACTIVE_TIER = "enterprise"
ENTERPRISE_ACTIVE_CREDIT = 500000.00
ENTERPRISE_ACTIVE_DISCOUNT = 20

# Premium active customer
PREMIUM_ACTIVE_ID = "CUST-002"
PREMIUM_ACTIVE_TIER = "premium"

# Standard customer on credit hold (CUST-003)
CREDIT_HOLD_ID = "CUST-003"
CREDIT_HOLD_STATUS = "credit_hold"

# Suspended customer (CUST-008)
SUSPENDED_ID = "CUST-008"
SUSPENDED_STATUS = "suspended"


class TestGetCustomer:
    def test_returns_correct_customer(self):
        c = get_customer(ENTERPRISE_ACTIVE_ID)
        assert c["customer_id"] == ENTERPRISE_ACTIVE_ID

    def test_returns_dict(self):
        assert isinstance(get_customer(ENTERPRISE_ACTIVE_ID), dict)

    def test_all_required_fields_present(self):
        c = get_customer(ENTERPRISE_ACTIVE_ID)
        required = {
            "customer_id", "company_name", "customer_tier", "payment_history",
            "discount_limit", "credit_limit", "account_status", "industry", "region",
        }
        assert required.issubset(c.keys())

    def test_returns_copy_not_reference(self):
        c1 = get_customer(ENTERPRISE_ACTIVE_ID)
        original_credit = c1["credit_limit"]
        c1["credit_limit"] = 0  # mutate copy
        c2 = get_customer(ENTERPRISE_ACTIVE_ID)
        assert c2["credit_limit"] == original_credit

    def test_not_found_raises_error(self):
        with pytest.raises(CustomerNotFoundError):
            get_customer("CUST-999")

    def test_not_found_error_contains_id(self):
        with pytest.raises(CustomerNotFoundError, match="CUST-999"):
            get_customer("CUST-999")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            get_customer("")

    def test_all_customers_retrievable(self):
        all_customers = get_all_customers()
        for c in all_customers:
            fetched = get_customer(c["customer_id"])
            assert fetched["customer_id"] == c["customer_id"]


class TestGetCustomerPricingTier:
    def test_enterprise_tier_correct(self):
        assert get_customer_pricing_tier(ENTERPRISE_ACTIVE_ID) == ENTERPRISE_ACTIVE_TIER

    def test_premium_tier_correct(self):
        assert get_customer_pricing_tier(PREMIUM_ACTIVE_ID) == PREMIUM_ACTIVE_TIER

    def test_returns_string(self):
        assert isinstance(get_customer_pricing_tier(ENTERPRISE_ACTIVE_ID), str)

    def test_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            get_customer_pricing_tier("CUST-999")

    def test_all_tiers_are_valid_vocabulary(self):
        valid_tiers = {"standard", "premium", "enterprise"}
        for c in get_all_customers():
            tier = get_customer_pricing_tier(c["customer_id"])
            assert tier in valid_tiers


class TestCheckCustomerAccountStatus:
    def test_active_customer_is_orderable(self):
        result = check_customer_account_status(ENTERPRISE_ACTIVE_ID)
        assert result["account_status"] == "active"
        assert result["is_orderable"] is True

    def test_credit_hold_not_orderable(self):
        result = check_customer_account_status(CREDIT_HOLD_ID)
        assert result["account_status"] == CREDIT_HOLD_STATUS
        assert result["is_orderable"] is False

    def test_suspended_not_orderable(self):
        result = check_customer_account_status(SUSPENDED_ID)
        assert result["account_status"] == SUSPENDED_STATUS
        assert result["is_orderable"] is False

    def test_result_contains_required_keys(self):
        result = check_customer_account_status(ENTERPRISE_ACTIVE_ID)
        assert {"customer_id", "account_status", "payment_history", "is_orderable"}.issubset(
            result.keys()
        )

    def test_customer_id_echoed(self):
        result = check_customer_account_status(ENTERPRISE_ACTIVE_ID)
        assert result["customer_id"] == ENTERPRISE_ACTIVE_ID

    def test_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            check_customer_account_status("CUST-999")


class TestGetCustomerCreditInfo:
    def test_credit_limit_matches_json(self):
        info = get_customer_credit_info(ENTERPRISE_ACTIVE_ID)
        assert info["credit_limit"] == ENTERPRISE_ACTIVE_CREDIT

    def test_discount_limit_matches_json(self):
        info = get_customer_credit_info(ENTERPRISE_ACTIVE_ID)
        assert info["discount_limit"] == ENTERPRISE_ACTIVE_DISCOUNT

    def test_contains_required_keys(self):
        info = get_customer_credit_info(ENTERPRISE_ACTIVE_ID)
        required = {
            "customer_id", "credit_limit", "discount_limit",
            "customer_tier", "payment_history", "account_status",
        }
        assert required.issubset(info.keys())

    def test_risk_payment_history_present(self):
        """CUST-003 has risk payment history — must be returned faithfully."""
        info = get_customer_credit_info(CREDIT_HOLD_ID)
        assert info["payment_history"] == "risk"

    def test_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            get_customer_credit_info("CUST-999")

    def test_credit_limit_positive_for_all(self):
        for c in get_all_customers():
            info = get_customer_credit_info(c["customer_id"])
            assert info["credit_limit"] > 0
