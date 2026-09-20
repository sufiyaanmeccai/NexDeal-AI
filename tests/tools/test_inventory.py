"""
tests/tools/test_inventory.py — NexDeal AI  |  Phase 2

Tests for app/tools/inventory.py (check_inventory).
Uses REAL Phase 1 data from data/products.json.
"""

import pytest

from app.tools.inventory import InventoryStatus, check_inventory
from app.tools.products import ProductNotFoundError


# ---------------------------------------------------------------------------
# Known data from products.json
# ---------------------------------------------------------------------------
# PRD-003 inventory = 55 (EdgeSwitch 48P PoE+)
ABUNDANT_PRODUCT = "PRD-003"
ABUNDANT_STOCK = 55

# PRD-002 inventory = 6 (RackServer Ultra 4U GPU)
SCARCE_PRODUCT = "PRD-002"
SCARCE_STOCK = 6

# PRD-008 inventory = 999 (Endpoint Security Suite — software licence)
SOFTWARE_PRODUCT = "PRD-008"
SOFTWARE_STOCK = 999


class TestCheckInventoryAvailable:
    def test_exact_stock_available(self):
        result = check_inventory(ABUNDANT_PRODUCT, ABUNDANT_STOCK)
        assert result["status"] == InventoryStatus.AVAILABLE

    def test_less_than_stock_available(self):
        result = check_inventory(ABUNDANT_PRODUCT, 1)
        assert result["status"] == InventoryStatus.AVAILABLE

    def test_available_quantity_equals_requested(self):
        result = check_inventory(ABUNDANT_PRODUCT, 10)
        assert result["available_quantity"] == 10
        assert result["shortfall"] == 0


class TestCheckInventoryPartial:
    def test_partial_when_requesting_more_than_stock(self):
        result = check_inventory(SCARCE_PRODUCT, SCARCE_STOCK + 5)
        assert result["status"] == InventoryStatus.PARTIAL

    def test_partial_available_quantity_equals_stock(self):
        result = check_inventory(SCARCE_PRODUCT, SCARCE_STOCK + 5)
        assert result["available_quantity"] == SCARCE_STOCK

    def test_partial_shortfall_is_correct(self):
        overage = 4
        result = check_inventory(SCARCE_PRODUCT, SCARCE_STOCK + overage)
        assert result["shortfall"] == overage


class TestCheckInventoryUnavailable:
    def test_requesting_more_than_software_stock(self):
        """Software licence PRD-008 has 999 units; request 1000 → PARTIAL."""
        result = check_inventory(SOFTWARE_PRODUCT, SOFTWARE_STOCK + 1)
        assert result["status"] == InventoryStatus.PARTIAL

    def test_unavailable_when_stock_is_zero(self, monkeypatch):
        """Simulate a zero-stock scenario by patching the reference used inside inventory.py."""
        import app.tools.inventory as inv_module
        import app.tools.data_loader as dl
        original = dl.get_product_by_id

        def fake_get(pid):
            rec = original(pid)
            if rec and pid == SCARCE_PRODUCT:
                rec = dict(rec)
                rec["inventory"] = 0
            return rec

        # Patch the name as imported inside app.tools.inventory
        monkeypatch.setattr(inv_module, "get_product_by_id", fake_get)
        result = check_inventory(SCARCE_PRODUCT, 1)
        assert result["status"] == InventoryStatus.UNAVAILABLE
        assert result["available_quantity"] == 0
        assert result["shortfall"] == 1


class TestCheckInventoryReturnStructure:
    def test_required_keys_present(self):
        result = check_inventory(ABUNDANT_PRODUCT, 5)
        required = {
            "product_id", "requested_quantity", "stock_on_hand",
            "status", "available_quantity", "shortfall",
        }
        assert required.issubset(result.keys())

    def test_product_id_echoed(self):
        result = check_inventory(ABUNDANT_PRODUCT, 5)
        assert result["product_id"] == ABUNDANT_PRODUCT

    def test_requested_quantity_echoed(self):
        result = check_inventory(ABUNDANT_PRODUCT, 7)
        assert result["requested_quantity"] == 7

    def test_stock_on_hand_matches_json(self):
        result = check_inventory(ABUNDANT_PRODUCT, 1)
        assert result["stock_on_hand"] == ABUNDANT_STOCK


class TestCheckInventoryInputValidation:
    def test_zero_quantity_raises_value_error(self):
        with pytest.raises(ValueError):
            check_inventory(ABUNDANT_PRODUCT, 0)

    def test_negative_quantity_raises_value_error(self):
        with pytest.raises(ValueError):
            check_inventory(ABUNDANT_PRODUCT, -1)

    def test_float_quantity_raises_type_error(self):
        with pytest.raises(TypeError):
            check_inventory(ABUNDANT_PRODUCT, 2.5)  # type: ignore[arg-type]

    def test_bool_quantity_raises_type_error(self):
        """Booleans are a subclass of int but must be rejected."""
        with pytest.raises(TypeError):
            check_inventory(ABUNDANT_PRODUCT, True)  # type: ignore[arg-type]

    def test_unknown_product_raises_product_not_found(self):
        with pytest.raises(ProductNotFoundError):
            check_inventory("PRD-999", 1)

    def test_empty_product_id_raises_value_error(self):
        with pytest.raises(ValueError):
            check_inventory("", 1)

    def test_inventory_not_mutated(self):
        """Calling check_inventory twice must return same stock_on_hand."""
        r1 = check_inventory(ABUNDANT_PRODUCT, 10)
        r2 = check_inventory(ABUNDANT_PRODUCT, 10)
        assert r1["stock_on_hand"] == r2["stock_on_hand"]
