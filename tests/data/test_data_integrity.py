"""
tests/data/test_data_integrity.py — NexDeal AI  |  Phase 1 data integrity tests

Validates that every JSON file in data/ is well-formed, internally consistent,
and satisfies the field contracts defined in the Phase 1 specification.

All tests load the ACTUAL data files from data/*.json — no mock / fake data is
created inside this test module.

Run with:
    pytest tests/data/test_data_integrity.py -v
"""

import json
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Paths — resolve relative to this file so tests work regardless of CWD.
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA_DIR = _REPO_ROOT / "data"
PRODUCTS_PATH = DATA_DIR / "products.json"
CUSTOMERS_PATH = DATA_DIR / "customers.json"
BUSINESS_RULES_PATH = DATA_DIR / "business_rules.json"


# ---------------------------------------------------------------------------
# Fixtures — load each file once per test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def products() -> list[dict]:
    """Load and return the products list."""
    raw = PRODUCTS_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, list), "products.json must be a JSON array at the top level"
    return data


@pytest.fixture(scope="session")
def customers() -> list[dict]:
    """Load and return the customers list."""
    raw = CUSTOMERS_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, list), "customers.json must be a JSON array at the top level"
    return data


@pytest.fixture(scope="session")
def business_rules() -> dict:
    """Load and return the business rules object."""
    raw = BUSINESS_RULES_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, dict), "business_rules.json must be a JSON object at the top level"
    return data


# ---------------------------------------------------------------------------
# Constants — controlled vocabulary drawn from the spec / business_rules.json
# ---------------------------------------------------------------------------

VALID_TIERS = {"standard", "premium", "enterprise"}
VALID_PAYMENT_HISTORIES = {"good", "risk"}
VALID_ACCOUNT_STATUSES = {"active", "credit_hold", "suspended", "closed"}
VALID_PRODUCT_STATUSES = {"active", "discontinued", "out_of_stock"}

REQUIRED_PRODUCT_FIELDS = {
    "product_id",
    "product_name",
    "category",
    "description",
    "specifications",
    "unit_price",
    "currency",
    "inventory",
    "lead_time_days",
    "installation_available",
    "installation_price",
    "status",
}

REQUIRED_CUSTOMER_FIELDS = {
    "customer_id",
    "company_name",
    "customer_tier",
    "payment_history",
    "discount_limit",
    "credit_limit",
    "account_status",
    "industry",
    "region",
}

REQUIRED_BUSINESS_RULE_SECTIONS = {
    "discount_policy",
    "margin_policy",
    "approval_policy",
    "delivery_policy",
    "installation_policy",
    "customer_tier_policy",
    "credit_policy",
}


# ===========================================================================
# FILE-LEVEL TESTS — parsing and existence
# ===========================================================================

class TestFilesExistAndParse:
    """All three data files must exist and parse as valid JSON."""

    def test_products_file_exists(self):
        assert PRODUCTS_PATH.exists(), f"products.json not found at {PRODUCTS_PATH}"

    def test_customers_file_exists(self):
        assert CUSTOMERS_PATH.exists(), f"customers.json not found at {CUSTOMERS_PATH}"

    def test_business_rules_file_exists(self):
        assert BUSINESS_RULES_PATH.exists(), f"business_rules.json not found at {BUSINESS_RULES_PATH}"

    def test_products_parses_as_valid_json(self):
        """products.json must parse without error."""
        raw = PRODUCTS_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, list)

    def test_customers_parses_as_valid_json(self):
        """customers.json must parse without error."""
        raw = CUSTOMERS_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, list)

    def test_business_rules_parses_as_valid_json(self):
        """business_rules.json must parse without error."""
        raw = BUSINESS_RULES_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# ===========================================================================
# PRODUCTS TESTS
# ===========================================================================

class TestProductsDataIntegrity:
    """Structural and constraint validation for products.json."""

    def test_products_count_in_range(self, products):
        """Must have between 10 and 15 products (spec: 10-15)."""
        assert 10 <= len(products) <= 15, (
            f"Expected 10–15 products, found {len(products)}"
        )

    def test_product_ids_are_unique(self, products):
        """product_id must be unique across all records."""
        ids = [p["product_id"] for p in products]
        assert len(ids) == len(set(ids)), (
            f"Duplicate product_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_product_names_are_unique(self, products):
        """product_name must be unique (no accidental duplicates)."""
        names = [p["product_name"] for p in products]
        assert len(names) == len(set(names)), (
            f"Duplicate product names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_all_required_fields_present(self, products):
        """Every product record must contain all required fields."""
        for product in products:
            missing = REQUIRED_PRODUCT_FIELDS - product.keys()
            assert not missing, (
                f"Product {product.get('product_id', '?')} is missing fields: {missing}"
            )

    def test_unit_price_positive(self, products):
        """unit_price must be > 0 for every product."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["unit_price"], (int, float)), (
                f"Product {pid}: unit_price must be numeric"
            )
            assert product["unit_price"] > 0, (
                f"Product {pid}: unit_price must be > 0, got {product['unit_price']}"
            )

    def test_inventory_non_negative(self, products):
        """inventory must be >= 0."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["inventory"], int), (
                f"Product {pid}: inventory must be an integer"
            )
            assert product["inventory"] >= 0, (
                f"Product {pid}: inventory must be >= 0, got {product['inventory']}"
            )

    def test_lead_time_days_non_negative(self, products):
        """lead_time_days must be >= 0."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["lead_time_days"], int), (
                f"Product {pid}: lead_time_days must be an integer"
            )
            assert product["lead_time_days"] >= 0, (
                f"Product {pid}: lead_time_days must be >= 0, got {product['lead_time_days']}"
            )

    def test_installation_price_non_negative(self, products):
        """installation_price must be >= 0."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["installation_price"], (int, float)), (
                f"Product {pid}: installation_price must be numeric"
            )
            assert product["installation_price"] >= 0, (
                f"Product {pid}: installation_price >= 0, got {product['installation_price']}"
            )

    def test_installation_available_is_boolean(self, products):
        """installation_available must be a boolean value."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["installation_available"], bool), (
                f"Product {pid}: installation_available must be bool"
            )

    def test_currency_is_consistent(self, products):
        """All products must share the same currency code."""
        currencies = {p["currency"] for p in products}
        assert len(currencies) == 1, (
            f"Inconsistent currency values found across products: {currencies}"
        )

    def test_specifications_is_object(self, products):
        """specifications must be a dict (nested object)."""
        for product in products:
            pid = product.get("product_id", "?")
            assert isinstance(product["specifications"], dict), (
                f"Product {pid}: specifications must be a JSON object (dict)"
            )

    def test_product_status_valid_value(self, products):
        """status must be one of the allowed vocabulary values."""
        for product in products:
            pid = product.get("product_id", "?")
            assert product["status"] in VALID_PRODUCT_STATUSES, (
                f"Product {pid}: invalid status '{product['status']}'. "
                f"Must be one of {VALID_PRODUCT_STATUSES}"
            )

    def test_installation_not_available_means_zero_price(self, products):
        """If installation_available is False, installation_price must be 0."""
        for product in products:
            pid = product.get("product_id", "?")
            if not product["installation_available"]:
                assert product["installation_price"] == 0, (
                    f"Product {pid}: installation_available=False but "
                    f"installation_price={product['installation_price']} (expected 0)"
                )


# ===========================================================================
# CUSTOMERS TESTS
# ===========================================================================

class TestCustomersDataIntegrity:
    """Structural and constraint validation for customers.json."""

    def test_customers_count_in_range(self, customers):
        """Must have between 5 and 8 customers (spec: 5-8)."""
        assert 5 <= len(customers) <= 8, (
            f"Expected 5–8 customers, found {len(customers)}"
        )

    def test_customer_ids_are_unique(self, customers):
        """customer_id must be unique across all records."""
        ids = [c["customer_id"] for c in customers]
        assert len(ids) == len(set(ids)), (
            f"Duplicate customer_ids: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_company_names_are_unique(self, customers):
        """company_name must be unique."""
        names = [c["company_name"] for c in customers]
        assert len(names) == len(set(names)), (
            f"Duplicate company names: {[n for n in names if names.count(n) > 1]}"
        )

    def test_all_required_fields_present(self, customers):
        """Every customer record must contain all required fields."""
        for customer in customers:
            missing = REQUIRED_CUSTOMER_FIELDS - customer.keys()
            assert not missing, (
                f"Customer {customer.get('customer_id', '?')} is missing fields: {missing}"
            )

    def test_customer_tier_valid_value(self, customers):
        """customer_tier must be one of standard | premium | enterprise."""
        for customer in customers:
            cid = customer.get("customer_id", "?")
            assert customer["customer_tier"] in VALID_TIERS, (
                f"Customer {cid}: invalid tier '{customer['customer_tier']}'. "
                f"Must be one of {VALID_TIERS}"
            )

    def test_payment_history_valid_value(self, customers):
        """payment_history must be one of good | risk."""
        for customer in customers:
            cid = customer.get("customer_id", "?")
            assert customer["payment_history"] in VALID_PAYMENT_HISTORIES, (
                f"Customer {cid}: invalid payment_history '{customer['payment_history']}'. "
                f"Must be one of {VALID_PAYMENT_HISTORIES}"
            )

    def test_account_status_valid_value(self, customers):
        """account_status must be one of the controlled vocabulary values."""
        for customer in customers:
            cid = customer.get("customer_id", "?")
            assert customer["account_status"] in VALID_ACCOUNT_STATUSES, (
                f"Customer {cid}: invalid account_status '{customer['account_status']}'. "
                f"Must be one of {VALID_ACCOUNT_STATUSES}"
            )

    def test_discount_limit_non_negative(self, customers):
        """discount_limit must be >= 0 and <= 100."""
        for customer in customers:
            cid = customer.get("customer_id", "?")
            val = customer["discount_limit"]
            assert isinstance(val, (int, float)), f"Customer {cid}: discount_limit must be numeric"
            assert 0 <= val <= 100, (
                f"Customer {cid}: discount_limit must be 0–100, got {val}"
            )

    def test_credit_limit_positive(self, customers):
        """credit_limit must be > 0."""
        for customer in customers:
            cid = customer.get("customer_id", "?")
            val = customer["credit_limit"]
            assert isinstance(val, (int, float)), f"Customer {cid}: credit_limit must be numeric"
            assert val > 0, f"Customer {cid}: credit_limit must be > 0, got {val}"

    def test_enterprise_tier_has_highest_discount_limits(self, customers):
        """Enterprise customers must have discount_limit >= premium >= standard (within dataset)."""
        tier_max_discounts = {tier: 0 for tier in VALID_TIERS}
        for customer in customers:
            tier = customer["customer_tier"]
            tier_max_discounts[tier] = max(tier_max_discounts[tier], customer["discount_limit"])
        # Only assert if all tiers are represented
        if all(tier_max_discounts[t] > 0 for t in VALID_TIERS):
            assert tier_max_discounts["enterprise"] >= tier_max_discounts["premium"], (
                "Max enterprise discount_limit should be >= max premium discount_limit"
            )
            assert tier_max_discounts["premium"] >= tier_max_discounts["standard"], (
                "Max premium discount_limit should be >= max standard discount_limit"
            )

    def test_dataset_has_at_least_one_active_customer(self, customers):
        """Must have at least one customer with account_status == 'active' for happy-path tests."""
        active = [c for c in customers if c["account_status"] == "active"]
        assert len(active) >= 1, "Dataset must contain at least one active customer"

    def test_dataset_has_at_least_one_blocked_customer(self, customers):
        """Must have at least one non-active customer to support edge-case tests."""
        blocked = [c for c in customers if c["account_status"] != "active"]
        assert len(blocked) >= 1, "Dataset must contain at least one non-active customer for edge-case tests"


# ===========================================================================
# BUSINESS RULES TESTS
# ===========================================================================

class TestBusinessRulesIntegrity:
    """Structural and threshold validation for business_rules.json."""

    def test_all_required_sections_present(self, business_rules):
        """All seven policy sections must be present."""
        missing = REQUIRED_BUSINESS_RULE_SECTIONS - business_rules.keys()
        assert not missing, f"Missing business rule sections: {missing}"

    # --- discount_policy ---

    def test_discount_policy_has_tier_max(self, business_rules):
        """discount_policy must define max_discount_by_tier for all tiers."""
        section = business_rules["discount_policy"]
        assert "max_discount_by_tier" in section
        tier_map = section["max_discount_by_tier"]
        for tier in VALID_TIERS:
            assert tier in tier_map, f"discount_policy missing tier: {tier}"
            assert tier_map[tier] >= 0, f"Discount for {tier} must be >= 0"

    def test_discount_policy_tier_ordering(self, business_rules):
        """Enterprise discount ceiling must be >= premium >= standard."""
        tiers = business_rules["discount_policy"]["max_discount_by_tier"]
        assert tiers["enterprise"] >= tiers["premium"] >= tiers["standard"], (
            "Discount caps must respect tier ordering: enterprise >= premium >= standard"
        )

    def test_discount_policy_volume_brackets_are_contiguous(self, business_rules):
        """Volume discount brackets must be contiguous and non-overlapping."""
        brackets = business_rules["discount_policy"]["volume_discount_brackets"]
        assert len(brackets) >= 1, "At least one volume bracket required"
        prev_max = -1
        for bracket in brackets:
            assert bracket["min_order_value_usd"] == prev_max + 1 or prev_max == -1 or bracket["min_order_value_usd"] == 0
            if bracket["max_order_value_usd"] is not None:
                prev_max = bracket["max_order_value_usd"]
            else:
                prev_max = bracket["min_order_value_usd"]  # last open bracket

    # --- margin_policy ---

    def test_margin_policy_has_absolute_minimum(self, business_rules):
        """absolute_minimum_margin_pct must be present and > 0."""
        section = business_rules["margin_policy"]
        assert "absolute_minimum_margin_pct" in section
        assert section["absolute_minimum_margin_pct"] > 0

    def test_margin_policy_category_minimums_above_absolute(self, business_rules):
        """Category-level minimums must be >= absolute minimum."""
        section = business_rules["margin_policy"]
        abs_min = section["absolute_minimum_margin_pct"]
        for category, pct in section["minimum_margin_pct_by_category"].items():
            assert pct >= abs_min, (
                f"Category '{category}' minimum margin {pct}% is below absolute minimum {abs_min}%"
            )

    # --- approval_policy ---

    def test_approval_policy_thresholds_are_ascending(self, business_rules):
        """Approval thresholds must be in ascending order: auto < manager < director < board."""
        section = business_rules["approval_policy"]
        auto = section["auto_approve_threshold_usd"]
        mgr = section["manager_approval_threshold_usd"]
        dir_ = section["director_approval_threshold_usd"]
        board = section["board_approval_threshold_usd"]
        assert auto < mgr < dir_ < board, (
            f"Approval thresholds must be ascending: {auto} < {mgr} < {dir_} < {board}"
        )

    def test_approval_policy_has_triggers_list(self, business_rules):
        """approval_triggers must be a non-empty list."""
        triggers = business_rules["approval_policy"]["approval_triggers"]
        assert isinstance(triggers, list) and len(triggers) >= 1

    # --- delivery_policy ---

    def test_delivery_policy_has_regions(self, business_rules):
        """delivery_policy must define at least one region."""
        regions = business_rules["delivery_policy"]["regions"]
        assert isinstance(regions, dict) and len(regions) >= 1

    def test_delivery_policy_express_faster_than_standard(self, business_rules):
        """For every region, express_transit_days must be < standard_transit_days."""
        for region, config in business_rules["delivery_policy"]["regions"].items():
            assert config["express_transit_days"] < config["standard_transit_days"], (
                f"Region '{region}': express must be faster than standard transit"
            )

    def test_delivery_policy_free_shipping_threshold_positive(self, business_rules):
        """free_shipping_threshold_usd must be > 0."""
        threshold = business_rules["delivery_policy"]["free_shipping_threshold_usd"]
        assert threshold > 0

    # --- installation_policy ---

    def test_installation_policy_has_required_categories_list(self, business_rules):
        """installation_required_categories must be a list."""
        section = business_rules["installation_policy"]
        assert isinstance(section["installation_required_categories"], list)

    def test_installation_bundle_discount_non_negative(self, business_rules):
        """installation_bundle_discount_pct must be >= 0."""
        val = business_rules["installation_policy"]["installation_bundle_discount_pct"]
        assert isinstance(val, (int, float)) and val >= 0

    # --- customer_tier_policy ---

    def test_customer_tier_policy_defines_all_tiers(self, business_rules):
        """customer_tier_policy must define benefit entries for all valid tiers."""
        benefits = business_rules["customer_tier_policy"]["tier_benefits"]
        for tier in VALID_TIERS:
            assert tier in benefits, f"customer_tier_policy missing benefit definition for tier: {tier}"

    def test_customer_tier_policy_upgrade_thresholds_ascending(self, business_rules):
        """standard->premium threshold must be < premium->enterprise threshold."""
        thresholds = business_rules["customer_tier_policy"]["upgrade_thresholds"]
        std_to_prem = thresholds["standard_to_premium_annual_spend_usd"]
        prem_to_ent = thresholds["premium_to_enterprise_annual_spend_usd"]
        assert std_to_prem < prem_to_ent, (
            f"Upgrade thresholds must be ascending: {std_to_prem} < {prem_to_ent}"
        )

    # --- credit_policy ---

    def test_credit_policy_valid_order_statuses_are_subset_of_all_statuses(self, business_rules):
        """valid_account_statuses_for_order must be a subset of VALID_ACCOUNT_STATUSES."""
        valid_for_order = set(business_rules["credit_policy"]["valid_account_statuses_for_order"])
        assert valid_for_order.issubset(VALID_ACCOUNT_STATUSES), (
            f"Unknown statuses in valid_account_statuses_for_order: "
            f"{valid_for_order - VALID_ACCOUNT_STATUSES}"
        )

    def test_credit_policy_utilisation_warning_below_block(self, business_rules):
        """credit_utilisation_warning_pct must be < credit_utilisation_block_pct."""
        section = business_rules["credit_policy"]
        warn = section["credit_utilisation_warning_pct"]
        block = section["credit_utilisation_block_pct"]
        assert warn < block, (
            f"Credit warning threshold {warn}% must be < block threshold {block}%"
        )

    def test_credit_policy_payment_history_values_match_spec(self, business_rules):
        """payment_history_values in rules must match VALID_PAYMENT_HISTORIES constant."""
        rule_values = set(business_rules["credit_policy"]["payment_history_values"])
        assert rule_values == VALID_PAYMENT_HISTORIES, (
            f"credit_policy.payment_history_values {rule_values} does not match "
            f"spec constant {VALID_PAYMENT_HISTORIES}"
        )


# ===========================================================================
# CROSS-REFERENCE TESTS — data consistency between files
# ===========================================================================

class TestCrossFileConsistency:
    """Validate that customers.json and business_rules.json are mutually consistent."""

    def test_customer_tiers_match_rules(self, customers, business_rules):
        """Every tier value in customers.json must be defined in business_rules.json."""
        rules_tiers = set(business_rules["discount_policy"]["max_discount_by_tier"].keys())
        for customer in customers:
            tier = customer["customer_tier"]
            assert tier in rules_tiers, (
                f"Customer {customer['customer_id']}: tier '{tier}' is not defined "
                f"in business_rules discount_policy (known tiers: {rules_tiers})"
            )

    def test_customer_discount_limits_within_tier_cap(self, customers, business_rules):
        """Each customer's discount_limit must not exceed the tier's rule-defined cap."""
        tier_caps = business_rules["discount_policy"]["max_discount_by_tier"]
        for customer in customers:
            cid = customer["customer_id"]
            tier = customer["customer_tier"]
            cap = tier_caps.get(tier)
            if cap is not None:
                assert customer["discount_limit"] <= cap, (
                    f"Customer {cid}: discount_limit {customer['discount_limit']} "
                    f"exceeds tier '{tier}' cap of {cap}"
                )

    def test_blocked_customer_statuses_match_credit_policy(self, customers, business_rules):
        """Customers with blocked statuses must use values listed in credit_policy."""
        blocked_statuses = set(business_rules["credit_policy"]["blocked_account_statuses"])
        for customer in customers:
            status = customer["account_status"]
            if status != "active":
                assert status in blocked_statuses, (
                    f"Customer {customer['customer_id']}: account_status '{status}' is "
                    f"neither 'active' nor in credit_policy.blocked_account_statuses {blocked_statuses}"
                )
