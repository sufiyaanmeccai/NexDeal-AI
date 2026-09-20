"""
tests/tools/test_products.py — NexDeal AI  |  Phase 2

Tests for app/tools/products.py (get_product, search_products).

Uses REAL Phase 1 data from data/products.json via data_loader.
No mocking of the datasets.
"""

import pytest

from app.tools.products import ProductNotFoundError, get_product, search_products
from app.tools.data_loader import get_all_products


# ---------------------------------------------------------------------------
# Known-good data constants derived from products.json (verified by Phase 1)
# ---------------------------------------------------------------------------
KNOWN_PRODUCT_ID = "PRD-001"
KNOWN_PRODUCT_NAME = "RackServer Pro 2U"
KNOWN_PRODUCT_PRICE = 8750.00
KNOWN_PRODUCT_CATEGORY = "Servers"

# PRD-008 has installation_available = False
NO_INSTALL_PRODUCT_ID = "PRD-008"

# All product IDs in the dataset
ALL_PRODUCT_IDS = [f"PRD-{i:03d}" for i in range(1, 13)]  # PRD-001 .. PRD-012


class TestGetProduct:
    """Tests for get_product()."""

    def test_returns_correct_product(self):
        product = get_product(KNOWN_PRODUCT_ID)
        assert product["product_id"] == KNOWN_PRODUCT_ID
        assert product["product_name"] == KNOWN_PRODUCT_NAME

    def test_returns_dict(self):
        product = get_product(KNOWN_PRODUCT_ID)
        assert isinstance(product, dict)

    def test_all_required_fields_present(self):
        product = get_product(KNOWN_PRODUCT_ID)
        required = {
            "product_id", "product_name", "category", "description",
            "specifications", "unit_price", "currency", "inventory",
            "lead_time_days", "installation_available", "installation_price", "status",
        }
        assert required.issubset(product.keys())

    def test_unit_price_matches_json(self):
        """Ensure price is read directly from JSON without mutation."""
        product = get_product(KNOWN_PRODUCT_ID)
        assert product["unit_price"] == KNOWN_PRODUCT_PRICE

    def test_returns_copy_not_reference(self):
        """Mutating the returned dict must not affect subsequent lookups."""
        p1 = get_product(KNOWN_PRODUCT_ID)
        p1["unit_price"] = 999999.99  # mutate the copy
        p2 = get_product(KNOWN_PRODUCT_ID)
        assert p2["unit_price"] == KNOWN_PRODUCT_PRICE

    def test_not_found_raises_product_not_found_error(self):
        with pytest.raises(ProductNotFoundError):
            get_product("PRD-999")

    def test_not_found_error_message_contains_id(self):
        with pytest.raises(ProductNotFoundError, match="PRD-999"):
            get_product("PRD-999")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            get_product("")

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError):
            get_product("   ")

    def test_non_string_raises_value_error(self):
        with pytest.raises((ValueError, TypeError, AttributeError)):
            get_product(None)  # type: ignore[arg-type]

    def test_all_products_retrievable_by_id(self):
        """Every product in the dataset must be individually retrievable."""
        all_products = get_all_products()
        for p in all_products:
            fetched = get_product(p["product_id"])
            assert fetched["product_id"] == p["product_id"]

    def test_no_install_product_has_zero_price(self):
        """PRD-008 has installation_available=False and installation_price=0."""
        product = get_product(NO_INSTALL_PRODUCT_ID)
        assert product["installation_available"] is False
        assert product["installation_price"] == 0.0


class TestSearchProducts:
    """Tests for search_products()."""

    def test_returns_list(self):
        results = search_products("server")
        assert isinstance(results, list)

    def test_empty_query_returns_all(self):
        results = search_products("")
        all_products = get_all_products()
        assert len(results) == len(all_products)

    def test_empty_query_sorted_by_product_id(self):
        results = search_products("")
        ids = [r["product_id"] for r in results]
        assert ids == sorted(ids)

    def test_category_search_servers(self):
        results = search_products("Servers")
        assert len(results) >= 1
        for r in results:
            assert r["category"] == "Servers"

    def test_search_is_case_insensitive(self):
        results_lower = search_products("networking")
        results_upper = search_products("NETWORKING")
        results_mixed = search_products("Networking")
        assert {r["product_id"] for r in results_lower} == {r["product_id"] for r in results_upper}
        assert {r["product_id"] for r in results_lower} == {r["product_id"] for r in results_mixed}

    def test_search_by_product_id(self):
        results = search_products("PRD-001")
        assert any(r["product_id"] == "PRD-001" for r in results)

    def test_search_by_partial_name(self):
        """'RackServer' should match at least two products."""
        results = search_products("RackServer")
        assert len(results) >= 2

    def test_search_no_match_returns_empty_list(self):
        results = search_products("xyzzy_no_such_product_q7z9")
        assert results == []

    def test_search_results_sorted_by_product_id(self):
        results = search_products("industrial")
        ids = [r["product_id"] for r in results]
        assert ids == sorted(ids)

    def test_search_by_description_keyword(self):
        """'NVMe' appears only in description of PRD-005."""
        results = search_products("NVMe")
        ids = {r["product_id"] for r in results}
        assert "PRD-005" in ids

    def test_non_string_query_raises_type_error(self):
        with pytest.raises(TypeError):
            search_products(42)  # type: ignore[arg-type]

    def test_whitespace_query_returns_all(self):
        """Whitespace-only query is stripped to '' and returns all."""
        results = search_products("   ")
        all_products = get_all_products()
        assert len(results) == len(all_products)
