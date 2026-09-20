"""
tests/tools/test_pricing.py — NexDeal AI  |  Phase 2

Tests for app/tools/pricing.py.
Uses REAL Phase 1 data via data_loader.
"""

from decimal import Decimal

import pytest

from app.tools.pricing import (
    calculate_customer_price,
    calculate_discount,
    calculate_discounted_total,
    calculate_margin,
    calculate_subtotal,
    calculate_tax,
)
from app.tools.products import ProductNotFoundError
from app.tools.customers import CustomerNotFoundError


# ---------------------------------------------------------------------------
# Known data from products.json and customers.json
# ---------------------------------------------------------------------------
# PRD-001: unit_price = 8750.00
PRODUCT_A = "PRD-001"
PRICE_A = Decimal("8750.00")

# PRD-009: unit_price = 1250.00 (cheaper product for volume bracket tests)
PRODUCT_B = "PRD-009"
PRICE_B = Decimal("1250.00")

# CUST-001: enterprise tier, discount_limit=20, credit_limit=500000 (active)
ENTERPRISE_CUST = "CUST-001"

# CUST-002: premium tier, discount_limit=12
PREMIUM_CUST = "CUST-002"

# CUST-006: standard tier, discount_limit=5
STANDARD_CUST = "CUST-006"


class TestCalculateSubtotal:
    def test_correct_arithmetic(self):
        result = calculate_subtotal(PRODUCT_A, 2)
        assert result == PRICE_A * 2

    def test_returns_decimal(self):
        assert isinstance(calculate_subtotal(PRODUCT_A, 1), Decimal)

    def test_quantity_one(self):
        assert calculate_subtotal(PRODUCT_A, 1) == PRICE_A

    def test_large_quantity(self):
        result = calculate_subtotal(PRODUCT_A, 100)
        assert result == PRICE_A * 100

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError):
            calculate_subtotal(PRODUCT_A, 0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            calculate_subtotal(PRODUCT_A, -1)

    def test_float_quantity_raises_type_error(self):
        with pytest.raises(TypeError):
            calculate_subtotal(PRODUCT_A, 2.0)  # type: ignore[arg-type]

    def test_unknown_product_raises(self):
        with pytest.raises(ProductNotFoundError):
            calculate_subtotal("PRD-999", 1)

    def test_price_consistent_with_get_product(self):
        """Subtotal of quantity=1 must equal unit_price from get_product."""
        from app.tools.products import get_product
        product = get_product(PRODUCT_A)
        expected = Decimal(str(product["unit_price"]))
        assert calculate_subtotal(PRODUCT_A, 1) == expected


class TestCalculateDiscount:
    def test_zero_discount(self):
        assert calculate_discount(Decimal("1000.00"), 0) == Decimal("0.00")

    def test_ten_percent(self):
        assert calculate_discount(Decimal("1000.00"), 10) == Decimal("100.00")

    def test_hundred_percent(self):
        assert calculate_discount(Decimal("500.00"), 100) == Decimal("500.00")

    def test_returns_decimal(self):
        assert isinstance(calculate_discount(1000, 5), Decimal)

    def test_negative_discount_raises(self):
        with pytest.raises(ValueError):
            calculate_discount(Decimal("1000.00"), -1)

    def test_discount_over_100_raises(self):
        with pytest.raises(ValueError):
            calculate_discount(Decimal("1000.00"), 101)

    def test_negative_subtotal_raises(self):
        with pytest.raises(ValueError):
            calculate_discount(Decimal("-1.00"), 5)

    def test_rounding_half_up(self):
        """$100.005 at 15% => $15.0075 => rounds to $15.01"""
        result = calculate_discount(Decimal("100.05"), 15)
        # 100.05 * 0.15 = 15.0075 -> ROUND_HALF_UP -> 15.01
        assert result == Decimal("15.01")


class TestCalculateDiscountedTotal:
    def test_zero_discount_returns_subtotal(self):
        sub = Decimal("5000.00")
        assert calculate_discounted_total(sub, 0) == sub

    def test_twenty_percent_discount(self):
        sub = Decimal("10000.00")
        expected = Decimal("8000.00")
        assert calculate_discounted_total(sub, 20) == expected

    def test_returns_decimal(self):
        assert isinstance(calculate_discounted_total(1000, 10), Decimal)

    def test_total_equals_subtotal_minus_discount(self):
        sub = Decimal("7500.00")
        disc_pct = Decimal("12")
        disc_amount = calculate_discount(sub, disc_pct)
        total = calculate_discounted_total(sub, disc_pct)
        assert total == sub - disc_amount


class TestCalculateCustomerPrice:
    def test_returns_dict(self):
        result = calculate_customer_price(PRODUCT_A, 1, ENTERPRISE_CUST)
        assert isinstance(result, dict)

    def test_required_keys(self):
        result = calculate_customer_price(PRODUCT_A, 1, ENTERPRISE_CUST)
        required = {
            "product_id", "customer_id", "quantity", "unit_price", "subtotal",
            "customer_tier", "tier_discount_cap", "customer_discount",
            "volume_discount_additional", "effective_discount",
            "discount_amount", "net_total",
        }
        assert required.issubset(result.keys())

    def test_all_values_decimal(self):
        result = calculate_customer_price(PRODUCT_A, 1, ENTERPRISE_CUST)
        for key in ("unit_price", "subtotal", "tier_discount_cap",
                    "customer_discount", "volume_discount_additional",
                    "effective_discount", "discount_amount", "net_total"):
            assert isinstance(result[key], Decimal), f"{key} should be Decimal"

    def test_subtotal_equals_unit_price_times_qty(self):
        result = calculate_customer_price(PRODUCT_A, 3, ENTERPRISE_CUST)
        assert result["subtotal"] == PRICE_A * 3

    def test_net_total_less_than_subtotal_when_discounted(self):
        result = calculate_customer_price(PRODUCT_A, 1, ENTERPRISE_CUST)
        assert result["net_total"] < result["subtotal"]

    def test_enterprise_tier_cap_matches_json(self):
        """enterprise tier cap = 20% from business_rules.json."""
        from app.tools.data_loader import get_discount_policy
        policy = get_discount_policy()
        expected_cap = Decimal(str(policy["max_discount_by_tier"]["enterprise"]))
        result = calculate_customer_price(PRODUCT_A, 1, ENTERPRISE_CUST)
        assert result["tier_discount_cap"] == expected_cap

    def test_standard_tier_effective_discount_capped_at_tier_max(self):
        """CUST-006 standard tier, discount_limit=5, tier cap=5 from JSON."""
        from app.tools.data_loader import get_discount_policy
        policy = get_discount_policy()
        tier_cap = Decimal(str(policy["max_discount_by_tier"]["standard"]))
        result = calculate_customer_price(PRODUCT_B, 1, STANDARD_CUST)
        assert result["effective_discount"] <= tier_cap

    def test_volume_discount_applied_for_high_value(self):
        """Large order (100 units × $8750 = $875,000) should hit the top volume bracket."""
        from app.tools.data_loader import get_discount_policy
        policy = get_discount_policy()
        # Find bracket for $875,000 (max_order_value_usd=null means open bracket)
        expected_additional = None
        for bracket in policy["volume_discount_brackets"]:
            min_val = bracket["min_order_value_usd"]
            max_val = bracket["max_order_value_usd"]
            if 875000 >= min_val and (max_val is None or 875000 <= max_val):
                expected_additional = Decimal(str(bracket["additional_discount_pct"]))
                break
        result = calculate_customer_price(PRODUCT_A, 100, ENTERPRISE_CUST)
        assert result["volume_discount_additional"] == expected_additional

    def test_unknown_product_raises(self):
        with pytest.raises(ProductNotFoundError):
            calculate_customer_price("PRD-999", 1, ENTERPRISE_CUST)

    def test_unknown_customer_raises(self):
        with pytest.raises(CustomerNotFoundError):
            calculate_customer_price(PRODUCT_A, 1, "CUST-999")

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError):
            calculate_customer_price(PRODUCT_A, 0, ENTERPRISE_CUST)


class TestCalculateTax:
    def test_default_rule_standard(self):
        """Omitting rule uses default 'standard' rule (20% from business_rules.json)."""
        assert calculate_tax(Decimal("1000.00")) == Decimal("200.00")

    def test_standard_tax_rule(self):
        assert calculate_tax(Decimal("1000.00"), "standard") == Decimal("200.00")

    def test_reduced_tax_rule(self):
        """'reduced' rule is 5% in business_rules.json."""
        assert calculate_tax(Decimal("1000.00"), "reduced") == Decimal("50.00")

    def test_zero_tax_rule(self):
        assert calculate_tax(Decimal("1000.00"), "zero") == Decimal("0.00")

    def test_exempt_tax_rule(self):
        assert calculate_tax(Decimal("1000.00"), "exempt") == Decimal("0.00")

    def test_regional_rule_north_america(self):
        """'North America' regional rate is 8.5% in business_rules.json."""
        assert calculate_tax(Decimal("1000.00"), "North America") == Decimal("85.00")

    def test_regional_rule_europe(self):
        """'Europe' regional rate is 20% in business_rules.json."""
        assert calculate_tax(Decimal("1000.00"), "Europe") == Decimal("200.00")

    def test_returns_decimal(self):
        assert isinstance(calculate_tax(1000, "standard"), Decimal)

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            calculate_tax(Decimal("-1.00"), "standard")

    def test_unknown_tax_rule_raises(self):
        with pytest.raises(ValueError, match="Unknown tax rule"):
            calculate_tax(Decimal("1000.00"), "nonexistent_rule")

    def test_arbitrary_numeric_rate_disallowed(self):
        """Arbitrary numeric rates must be rejected with TypeError so business rules remain authoritative."""
        with pytest.raises(TypeError, match="must be a string rule name"):
            calculate_tax(Decimal("1000.00"), 20)  # type: ignore[arg-type]

    def test_zero_amount(self):
        assert calculate_tax(Decimal("0.00"), "standard") == Decimal("0.00")

    def test_rate_matches_authoritative_json(self):
        """Cross-check that calculate_tax result strictly matches get_tax_policy()."""
        from app.tools.data_loader import get_tax_policy
        policy = get_tax_policy()
        rule = "reduced"
        pct = Decimal(str(policy["tax_rules"][rule]))
        subtotal = Decimal("1500.00")
        expected = (subtotal * pct / Decimal("100")).quantize(Decimal("0.01"))
        assert calculate_tax(subtotal, rule) == expected



class TestCalculateMargin:
    def test_fifty_percent_margin(self):
        result = calculate_margin(Decimal("1000.00"), Decimal("500.00"))
        assert result["margin_pct"] == Decimal("50.00")

    def test_gross_profit_correct(self):
        result = calculate_margin(Decimal("1000.00"), Decimal("700.00"))
        assert result["gross_profit"] == Decimal("300.00")

    def test_returns_dict_with_required_keys(self):
        result = calculate_margin(1000, 800)
        assert {"revenue", "cost", "gross_profit", "margin_pct"}.issubset(result.keys())

    def test_all_values_decimal(self):
        result = calculate_margin(1000, 800)
        for k in ("revenue", "cost", "gross_profit", "margin_pct"):
            assert isinstance(result[k], Decimal)

    def test_zero_revenue_raises(self):
        with pytest.raises(ValueError):
            calculate_margin(Decimal("0.00"), Decimal("0.00"))

    def test_negative_revenue_raises(self):
        with pytest.raises(ValueError):
            calculate_margin(Decimal("-100.00"), Decimal("50.00"))

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError):
            calculate_margin(Decimal("1000.00"), Decimal("-1.00"))

    def test_cost_exceeds_revenue_raises(self):
        with pytest.raises(ValueError):
            calculate_margin(Decimal("500.00"), Decimal("600.00"))

    def test_exact_float_precision(self):
        """Verify Decimal avoids float rounding errors in margin calc."""
        result = calculate_margin(Decimal("1.10"), Decimal("0.90"))
        # (1.10 - 0.90) / 1.10 * 100 = 18.181818... -> rounds to 18.18
        assert result["margin_pct"] == Decimal("18.18")
