"""
tests/tools/test_fulfilment.py — NexDeal AI  |  Phase 2

Tests for app/tools/fulfilment.py.
All tests use an explicit reference_date for full determinism.
Uses REAL Phase 1 data from data/products.json and business_rules.json.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.tools.fulfilment import (
    DeliveryFeasibility,
    check_delivery_feasibility,
    check_installation_availability,
    get_installation_price,
)
from app.tools.products import ProductNotFoundError
from app.tools.data_loader import get_delivery_policy


# ---------------------------------------------------------------------------
# Known data from products.json
# ---------------------------------------------------------------------------
# PRD-001: lead_time_days=5, installation_available=True, installation_price=450.00
INSTALL_PRODUCT = "PRD-001"
INSTALL_PRODUCT_LEAD = 5
INSTALL_PRODUCT_PRICE = Decimal("450.00")

# PRD-008: lead_time_days=0, installation_available=False, installation_price=0.00
NO_INSTALL_PRODUCT = "PRD-008"
NO_INSTALL_LEAD = 0

# PRD-004: lead_time_days=30 (CoreRouter 100G — longest lead time)
LONG_LEAD_PRODUCT = "PRD-004"
LONG_LEAD_DAYS = 30

REFERENCE_DATE = date(2026, 1, 15)


class TestCheckDeliveryFeasibility:
    def test_feasible_when_ample_time(self):
        policy = get_delivery_policy()
        buffer = policy["standard_lead_time_buffer_days"]
        # Request date well beyond lead + buffer
        requested = REFERENCE_DATE + timedelta(days=INSTALL_PRODUCT_LEAD + buffer + 30)
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, requested, REFERENCE_DATE)
        assert result["feasibility"] == DeliveryFeasibility.FEASIBLE

    def test_not_feasible_when_too_soon(self):
        # Request only 1 day after order — impossible
        requested = REFERENCE_DATE + timedelta(days=1)
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, requested, REFERENCE_DATE)
        assert result["feasibility"] == DeliveryFeasibility.NOT_FEASIBLE

    def test_exact_boundary_is_feasible(self):
        """Requesting exactly on earliest_dispatch_ready should be FEASIBLE."""
        policy = get_delivery_policy()
        buffer = policy["standard_lead_time_buffer_days"]
        exact_date = REFERENCE_DATE + timedelta(days=INSTALL_PRODUCT_LEAD + buffer)
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, exact_date, REFERENCE_DATE)
        assert result["feasibility"] == DeliveryFeasibility.FEASIBLE

    def test_one_day_before_boundary_is_not_feasible(self):
        policy = get_delivery_policy()
        buffer = policy["standard_lead_time_buffer_days"]
        one_before = REFERENCE_DATE + timedelta(days=INSTALL_PRODUCT_LEAD + buffer - 1)
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, one_before, REFERENCE_DATE)
        assert result["feasibility"] == DeliveryFeasibility.NOT_FEASIBLE

    def test_no_date_requested_returns_no_date_status(self):
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        assert result["feasibility"] == DeliveryFeasibility.NO_DATE_REQUESTED
        assert result["requested_delivery_date"] is None
        assert result["days_to_deadline"] is None

    def test_earliest_dispatch_ready_uses_json_buffer(self):
        """Buffer days must come from delivery_policy JSON, not a hardcoded constant."""
        policy = get_delivery_policy()
        buffer = policy["standard_lead_time_buffer_days"]
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        expected_ready = REFERENCE_DATE + timedelta(days=INSTALL_PRODUCT_LEAD + buffer)
        assert result["earliest_dispatch_ready"] == expected_ready.isoformat()

    def test_result_contains_required_keys(self):
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        required = {
            "product_id", "reference_date", "product_lead_time_days",
            "buffer_days", "earliest_dispatch_ready", "requested_delivery_date",
            "feasibility", "days_to_deadline", "days_ahead_or_behind",
        }
        assert required.issubset(result.keys())

    def test_product_id_echoed(self):
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        assert result["product_id"] == INSTALL_PRODUCT

    def test_reference_date_in_iso_format(self):
        result = check_delivery_feasibility(INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        assert result["reference_date"] == REFERENCE_DATE.isoformat()

    def test_zero_lead_time_product_ready_on_buffer_date(self):
        """PRD-008 has lead_time_days=0; only buffer adds to reference date."""
        policy = get_delivery_policy()
        buffer = policy["standard_lead_time_buffer_days"]
        result = check_delivery_feasibility(NO_INSTALL_PRODUCT, 1, None, REFERENCE_DATE)
        expected = REFERENCE_DATE + timedelta(days=buffer)
        assert result["earliest_dispatch_ready"] == expected.isoformat()

    def test_deterministic_with_same_inputs(self):
        """Same inputs must always produce identical outputs."""
        requested = REFERENCE_DATE + timedelta(days=20)
        r1 = check_delivery_feasibility(INSTALL_PRODUCT, 5, requested, REFERENCE_DATE)
        r2 = check_delivery_feasibility(INSTALL_PRODUCT, 5, requested, REFERENCE_DATE)
        assert r1 == r2

    def test_unknown_product_raises(self):
        with pytest.raises(ProductNotFoundError):
            check_delivery_feasibility("PRD-999", 1, None, REFERENCE_DATE)

    def test_zero_quantity_raises_value_error(self):
        with pytest.raises(ValueError):
            check_delivery_feasibility(INSTALL_PRODUCT, 0, None, REFERENCE_DATE)

    def test_negative_quantity_raises_value_error(self):
        with pytest.raises(ValueError):
            check_delivery_feasibility(INSTALL_PRODUCT, -3, None, REFERENCE_DATE)

    def test_non_date_reference_raises_type_error(self):
        with pytest.raises(TypeError):
            check_delivery_feasibility(INSTALL_PRODUCT, 1, None, "2026-01-15")  # type: ignore


class TestCheckInstallationAvailability:
    def test_install_available_true(self):
        result = check_installation_availability(INSTALL_PRODUCT)
        assert result["installation_available"] is True

    def test_install_available_false(self):
        result = check_installation_availability(NO_INSTALL_PRODUCT)
        assert result["installation_available"] is False

    def test_install_price_is_decimal(self):
        result = check_installation_availability(INSTALL_PRODUCT)
        assert isinstance(result["installation_price"], Decimal)

    def test_install_price_matches_json(self):
        result = check_installation_availability(INSTALL_PRODUCT)
        assert result["installation_price"] == INSTALL_PRODUCT_PRICE

    def test_no_install_price_is_zero(self):
        result = check_installation_availability(NO_INSTALL_PRODUCT)
        assert result["installation_price"] == Decimal("0.00")

    def test_product_id_echoed(self):
        result = check_installation_availability(INSTALL_PRODUCT)
        assert result["product_id"] == INSTALL_PRODUCT

    def test_unknown_product_raises(self):
        with pytest.raises(ProductNotFoundError):
            check_installation_availability("PRD-999")


class TestGetInstallationPrice:
    def test_returns_decimal(self):
        price = get_installation_price(INSTALL_PRODUCT)
        assert isinstance(price, Decimal)

    def test_price_matches_json(self):
        price = get_installation_price(INSTALL_PRODUCT)
        assert price == INSTALL_PRODUCT_PRICE

    def test_no_install_returns_zero(self):
        price = get_installation_price(NO_INSTALL_PRODUCT)
        assert price == Decimal("0.00")

    def test_unknown_product_raises(self):
        with pytest.raises(ProductNotFoundError):
            get_installation_price("PRD-999")
