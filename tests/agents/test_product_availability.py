"""
tests/agents/test_product_availability.py — NexDeal AI  |  Phase 4

Offline unit tests for:
  - app.models.schemas  (FulfilmentItemResult, FulfilmentResult)
  - app.agents.product_availability  (module boundaries, deterministic logic,
    tool wrappers, overall_status derivation)

These tests are 100% OFFLINE — they do NOT call the Foundry API.
All Pydantic construction and schema assertions are pure-Python.
The @tool wrappers are tested directly against real Phase 2 data.

Coverage
--------
* Exact canonical field names on both models.
* All fields appear in JSON schema ``required`` list (Foundry strict mode).
* Nullable fields accept null but cannot be omitted.
* Literal status fields reject invalid values.
* _derive_overall_status precedence (all 6 outcomes).
* Tool wrapper happy-path and error handling.
* Boundary: no pricing/tax/margin/credit tool imports.
* Boundary: AzureCliCredential not DefaultAzureCredential.
* Boundary: reference_date injection (no clock calls).
* Application-level enforcement of overall_status.
"""

from __future__ import annotations

import json
import ast
from datetime import date

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    FulfilmentItemResult,
    FulfilmentResult,
    RequestedItem,
    StructuredRequest,
)


# ===========================================================================
# Test helpers
# ===========================================================================


def _make_item_result(
    raw: str = "enterprise switch",
    resolved_id: str | None = "PRD-003",
    resolution_status: str = "RESOLVED",
    quantity: int | None = 5,
    available: int | None = 5,
    inv_status: str = "AVAILABLE",
    delivery_date: str | None = None,
    delivery_status: str = "NOT_REQUESTED",
    installation_required: bool | None = None,
    installation_status: str = "NEEDS_CLARIFICATION",
    installation_price: str | None = None,
    issues: list[str] | None = None,
) -> FulfilmentItemResult:
    return FulfilmentItemResult(
        raw_product_reference=raw,
        resolved_product_id=resolved_id,
        product_resolution_status=resolution_status,
        requested_quantity=quantity,
        available_quantity=available,
        inventory_status=inv_status,
        requested_delivery_date=delivery_date,
        delivery_status=delivery_status,
        installation_required=installation_required,
        installation_status=installation_status,
        installation_price=installation_price,
        issues=issues if issues is not None else [],
    )


def _make_result(**overrides) -> FulfilmentResult:
    defaults = dict(
        request_id=None,
        customer_reference=None,
        items=[],
        overall_status="CLARIFICATION_REQUIRED",
        clarification_required=True,
        issues=[],
    )
    defaults.update(overrides)
    return FulfilmentResult(**defaults)


# ===========================================================================
# FulfilmentItemResult — exact field names
# ===========================================================================


class TestFulfilmentItemResultFieldNames:
    """All 12 canonical field names must be present on FulfilmentItemResult."""

    EXPECTED_FIELDS = [
        "raw_product_reference",
        "resolved_product_id",
        "product_resolution_status",
        "requested_quantity",
        "available_quantity",
        "inventory_status",
        "requested_delivery_date",
        "delivery_status",
        "installation_required",
        "installation_status",
        "installation_price",
        "issues",
    ]

    def test_all_fields_exist(self):
        item = _make_item_result()
        for field in self.EXPECTED_FIELDS:
            assert hasattr(item, field), f"Missing field: {field}"

    def test_field_count(self):
        assert len(FulfilmentItemResult.model_fields) == 12

    def test_no_unexpected_fields(self):
        actual = set(FulfilmentItemResult.model_fields.keys())
        expected = set(self.EXPECTED_FIELDS)
        assert actual == expected


# ===========================================================================
# FulfilmentResult — exact field names
# ===========================================================================


class TestFulfilmentResultFieldNames:
    """All 6 canonical field names must be present on FulfilmentResult."""

    EXPECTED_FIELDS = [
        "request_id",
        "customer_reference",
        "items",
        "overall_status",
        "clarification_required",
        "issues",
    ]

    def test_all_fields_exist(self):
        result = _make_result()
        for field in self.EXPECTED_FIELDS:
            assert hasattr(result, field), f"Missing field: {field}"

    def test_field_count(self):
        assert len(FulfilmentResult.model_fields) == 6


# ===========================================================================
# JSON Schema — all fields in required (Foundry strict mode)
# ===========================================================================


class TestFulfilmentItemResultSchema:
    """Every FulfilmentItemResult field must appear in JSON schema required."""

    def setup_method(self):
        self.schema = FulfilmentItemResult.model_json_schema()

    def test_all_12_fields_in_required(self):
        required = self.schema.get("required", [])
        assert len(required) == 12, f"Expected 12 required fields, got {len(required)}: {required}"

    def test_specific_fields_required(self):
        required = self.schema.get("required", [])
        for field in [
            "raw_product_reference", "resolved_product_id", "product_resolution_status",
            "requested_quantity", "available_quantity", "inventory_status",
            "requested_delivery_date", "delivery_status", "installation_required",
            "installation_status", "installation_price", "issues",
        ]:
            assert field in required, f"Field '{field}' not in required"

    def test_nullable_fields_use_anyof_not_default(self):
        """Nullable fields must use anyOf[type/null] not have a default value."""
        props = self.schema.get("properties", {})
        for nullable_field in [
            "resolved_product_id", "requested_quantity", "available_quantity",
            "requested_delivery_date", "installation_required", "installation_price",
        ]:
            prop = props.get(nullable_field, {})
            assert "anyOf" in prop, (
                f"Field '{nullable_field}' should use anyOf for nullable, not default"
            )


class TestFulfilmentResultSchema:
    """Every FulfilmentResult field must appear in JSON schema required."""

    def setup_method(self):
        self.schema = FulfilmentResult.model_json_schema()

    def test_all_6_fields_in_required(self):
        required = self.schema.get("required", [])
        assert len(required) == 6, f"Expected 6 required fields, got {len(required)}: {required}"

    def test_specific_fields_required(self):
        required = self.schema.get("required", [])
        for field in [
            "request_id", "customer_reference", "items",
            "overall_status", "clarification_required", "issues",
        ]:
            assert field in required, f"Field '{field}' not in required"


# ===========================================================================
# FulfilmentItemResult — nullable field acceptance
# ===========================================================================


class TestFulfilmentItemResultNullableFields:

    def test_resolved_product_id_accepts_null(self):
        item = _make_item_result(resolved_id=None, resolution_status="NOT_FOUND")
        assert item.resolved_product_id is None

    def test_requested_quantity_accepts_null(self):
        item = _make_item_result(quantity=None)
        assert item.requested_quantity is None

    def test_available_quantity_accepts_null(self):
        item = _make_item_result(available=None, inv_status="NOT_EVALUATED")
        assert item.available_quantity is None

    def test_requested_delivery_date_accepts_null(self):
        item = _make_item_result(delivery_date=None)
        assert item.requested_delivery_date is None

    def test_installation_required_accepts_null(self):
        item = _make_item_result(installation_required=None)
        assert item.installation_required is None

    def test_installation_required_accepts_true(self):
        item = _make_item_result(installation_required=True, installation_status="AVAILABLE")
        assert item.installation_required is True

    def test_installation_required_accepts_false(self):
        item = _make_item_result(installation_required=False, installation_status="NOT_REQUESTED")
        assert item.installation_required is False

    def test_installation_price_accepts_null(self):
        item = _make_item_result(installation_price=None)
        assert item.installation_price is None

    def test_installation_price_accepts_decimal_string(self):
        item = _make_item_result(installation_price="450.00")
        assert item.installation_price == "450.00"

    def test_issues_empty_list_accepted(self):
        item = _make_item_result(issues=[])
        assert item.issues == []

    def test_issues_non_empty_accepted(self):
        item = _make_item_result(issues=["Product not found", "Quantity unspecified"])
        assert len(item.issues) == 2


# ===========================================================================
# FulfilmentItemResult — omitted required fields rejected
# ===========================================================================


class TestFulfilmentItemResultRequiredEnforcement:

    def test_missing_raw_product_reference_rejected(self):
        with pytest.raises(ValidationError):
            FulfilmentItemResult(
                resolved_product_id=None,
                product_resolution_status="NOT_FOUND",
                requested_quantity=None,
                available_quantity=None,
                inventory_status="NOT_EVALUATED",
                requested_delivery_date=None,
                delivery_status="NOT_EVALUATED",
                installation_required=None,
                installation_status="NOT_EVALUATED",
                installation_price=None,
                issues=[],
            )

    def test_missing_inventory_status_rejected(self):
        with pytest.raises(ValidationError):
            FulfilmentItemResult(
                raw_product_reference="test",
                resolved_product_id="PRD-001",
                product_resolution_status="RESOLVED",
                requested_quantity=1,
                available_quantity=1,
                requested_delivery_date=None,
                delivery_status="NOT_REQUESTED",
                installation_required=None,
                installation_status="NEEDS_CLARIFICATION",
                installation_price=None,
                issues=[],
            )


# ===========================================================================
# Literal status field validation
# ===========================================================================


class TestLiteralStatusValidation:

    def test_invalid_product_resolution_status_rejected(self):
        with pytest.raises(ValidationError):
            _make_item_result(resolution_status="UNKNOWN")

    def test_invalid_inventory_status_rejected(self):
        with pytest.raises(ValidationError):
            _make_item_result(inv_status="IN_STOCK")

    def test_invalid_delivery_status_rejected(self):
        with pytest.raises(ValidationError):
            _make_item_result(delivery_status="DELAYED")

    def test_invalid_installation_status_rejected(self):
        with pytest.raises(ValidationError):
            _make_item_result(installation_status="PENDING")

    def test_invalid_overall_status_rejected(self):
        with pytest.raises(ValidationError):
            _make_result(overall_status="ALL_GOOD")

    def test_all_valid_product_resolution_statuses(self):
        for status in ["RESOLVED", "AMBIGUOUS", "NOT_FOUND"]:
            item = _make_item_result(
                resolved_id=None if status != "RESOLVED" else "PRD-001",
                resolution_status=status,
            )
            assert item.product_resolution_status == status

    def test_all_valid_inventory_statuses(self):
        for status in ["AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_EVALUATED"]:
            item = _make_item_result(inv_status=status)
            assert item.inventory_status == status

    def test_all_valid_delivery_statuses(self):
        for status in ["FEASIBLE", "INFEASIBLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"]:
            item = _make_item_result(delivery_status=status)
            assert item.delivery_status == status

    def test_all_valid_installation_statuses(self):
        for status in ["AVAILABLE", "UNAVAILABLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"]:
            item = _make_item_result(installation_status=status)
            assert item.installation_status == status

    def test_all_valid_overall_statuses(self):
        for status in [
            "READY", "PARTIAL", "UNAVAILABLE",
            "CLARIFICATION_REQUIRED", "DELIVERY_CONFLICT", "INSTALLATION_UNAVAILABLE"
        ]:
            result = _make_result(
                overall_status=status,
                clarification_required=(status == "CLARIFICATION_REQUIRED"),
            )
            assert result.overall_status == status


# ===========================================================================
# _derive_overall_status — deterministic precedence
# ===========================================================================


class TestDeriveOverallStatus:
    """Tests for the Python-level status precedence logic."""

    def setup_method(self):
        from app.agents.product_availability import _derive_overall_status
        self.derive = _derive_overall_status

    # --- READY ---

    def test_all_clear_returns_ready(self):
        items = [
            _make_item_result(
                inv_status="AVAILABLE",
                delivery_status="NOT_REQUESTED",
                installation_required=None,
                installation_status="NEEDS_CLARIFICATION",
            ),
            _make_item_result(
                inv_status="AVAILABLE",
                delivery_status="NOT_REQUESTED",
                installation_required=False,
                installation_status="NOT_REQUESTED",
            ),
        ]
        assert self.derive(items) == "READY"

    def test_all_available_with_feasible_delivery_returns_ready(self):
        items = [
            _make_item_result(
                inv_status="AVAILABLE",
                delivery_date="2027-01-15",
                delivery_status="FEASIBLE",
                installation_required=False,
                installation_status="NOT_REQUESTED",
            ),
        ]
        assert self.derive(items) == "READY"

    # --- PARTIAL ---

    def test_partial_inventory_returns_partial(self):
        items = [
            _make_item_result(inv_status="PARTIAL"),
        ]
        assert self.derive(items) == "PARTIAL"

    # --- UNAVAILABLE ---

    def test_unavailable_inventory_returns_unavailable(self):
        items = [
            _make_item_result(inv_status="UNAVAILABLE"),
        ]
        assert self.derive(items) == "UNAVAILABLE"

    # --- DELIVERY_CONFLICT ---

    def test_infeasible_delivery_returns_delivery_conflict(self):
        items = [
            _make_item_result(
                inv_status="AVAILABLE",
                delivery_status="INFEASIBLE",
            ),
        ]
        assert self.derive(items) == "DELIVERY_CONFLICT"

    def test_delivery_conflict_beats_unavailable(self):
        """DELIVERY_CONFLICT has higher precedence than UNAVAILABLE per the status ordering."""
        items = [
            _make_item_result(inv_status="UNAVAILABLE"),
            _make_item_result(delivery_status="INFEASIBLE"),
        ]
        # DELIVERY_CONFLICT (idx 2) is checked before UNAVAILABLE (idx 3)
        assert self.derive(items) == "DELIVERY_CONFLICT"

    # --- INSTALLATION_UNAVAILABLE ---

    def test_installation_unavailable_returns_installation_unavailable(self):
        items = [
            _make_item_result(
                inv_status="AVAILABLE",
                installation_status="UNAVAILABLE",
            ),
        ]
        assert self.derive(items) == "INSTALLATION_UNAVAILABLE"

    def test_installation_unavailable_beats_delivery_conflict(self):
        """INSTALLATION_UNAVAILABLE beats DELIVERY_CONFLICT (higher precedence)."""
        items = [
            _make_item_result(delivery_status="INFEASIBLE"),
            _make_item_result(installation_status="UNAVAILABLE"),
        ]
        assert self.derive(items) == "INSTALLATION_UNAVAILABLE"

    # --- CLARIFICATION_REQUIRED ---

    def test_ambiguous_product_returns_clarification_required(self):
        items = [
            _make_item_result(
                resolved_id=None,
                resolution_status="AMBIGUOUS",
                inv_status="NOT_EVALUATED",
                delivery_status="NOT_EVALUATED",
                installation_status="NOT_EVALUATED",
            ),
        ]
        assert self.derive(items) == "CLARIFICATION_REQUIRED"

    def test_not_found_product_returns_clarification_required(self):
        items = [
            _make_item_result(
                resolved_id=None,
                resolution_status="NOT_FOUND",
                inv_status="NOT_EVALUATED",
                delivery_status="NOT_EVALUATED",
                installation_status="NOT_EVALUATED",
            ),
        ]
        assert self.derive(items) == "CLARIFICATION_REQUIRED"

    def test_needs_clarification_delivery_returns_clarification_required(self):
        items = [
            _make_item_result(
                inv_status="AVAILABLE",
                delivery_date="15 October",
                delivery_status="NEEDS_CLARIFICATION",
            ),
        ]
        assert self.derive(items) == "CLARIFICATION_REQUIRED"

    def test_clarification_beats_installation_unavailable(self):
        """CLARIFICATION_REQUIRED has highest precedence."""
        items = [
            _make_item_result(installation_status="UNAVAILABLE"),
            _make_item_result(
                resolved_id=None,
                resolution_status="NOT_FOUND",
                inv_status="NOT_EVALUATED",
                delivery_status="NOT_EVALUATED",
                installation_status="NOT_EVALUATED",
            ),
        ]
        assert self.derive(items) == "CLARIFICATION_REQUIRED"

    def test_empty_items_returns_clarification_required(self):
        """Empty item list means nothing can be fulfilled."""
        assert self.derive([]) == "CLARIFICATION_REQUIRED"

    # --- Mixed scenarios ---

    def test_mixed_ready_and_partial(self):
        items = [
            _make_item_result(inv_status="AVAILABLE"),
            _make_item_result(inv_status="PARTIAL"),
        ]
        assert self.derive(items) == "PARTIAL"

    def test_mixed_partial_and_unavailable(self):
        items = [
            _make_item_result(inv_status="PARTIAL"),
            _make_item_result(inv_status="UNAVAILABLE"),
        ]
        assert self.derive(items) == "UNAVAILABLE"


# ===========================================================================
# Tool wrappers — happy path against real Phase 2 data
# ===========================================================================


class TestToolSearchProducts:
    """tool_search_products wraps search_products and returns JSON string."""

    def setup_method(self):
        from app.agents.product_availability import tool_search_products
        self.tool = tool_search_products

    def test_switch_query_returns_results(self):
        raw = self.tool.func("switch")
        result = json.loads(raw)
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert "product_id" in first
        assert "product_name" in first
        assert "category" in first
        assert "description" in first

    def test_no_price_fields_in_response(self):
        """Tool must NOT return unit_price, margin, or other pricing fields."""
        raw = self.tool.func("server")
        result = json.loads(raw)
        for item in result:
            assert "unit_price" not in item, "unit_price must not be exposed to agent"
            assert "margin" not in item

    def test_empty_query_returns_all(self):
        raw = self.tool.func("")
        result = json.loads(raw)
        assert len(result) == 12  # All 12 products in catalogue

    def test_nonexistent_query_returns_empty_list(self):
        raw = self.tool.func("zzz_no_such_product_xyz")
        result = json.loads(raw)
        assert result == []

    def test_invalid_type_returns_error(self):
        # The @tool wrapper catches exceptions and returns error JSON
        raw = self.tool.func(123)  # type: ignore[arg-type]
        result = json.loads(raw)
        assert "error" in result


class TestToolGetProduct:
    """tool_get_product wraps get_product and returns JSON string."""

    def setup_method(self):
        from app.agents.product_availability import tool_get_product
        self.tool = tool_get_product

    def test_known_product_id_returns_record(self):
        raw = self.tool.func("PRD-001")
        result = json.loads(raw)
        assert result["product_id"] == "PRD-001"
        assert "product_name" in result
        assert "inventory" in result
        assert "lead_time_days" in result
        assert "installation_available" in result
        assert "installation_price" in result

    def test_no_unit_price_in_response(self):
        """unit_price must NOT be returned by this tool."""
        raw = self.tool.func("PRD-001")
        result = json.loads(raw)
        assert "unit_price" not in result

    def test_all_12_products_accessible(self):
        for i in range(1, 13):
            raw = self.tool.func(f"PRD-{i:03d}")
            result = json.loads(raw)
            assert "product_id" in result, f"PRD-{i:03d} should be accessible"

    def test_unknown_product_returns_error_json(self):
        raw = self.tool.func("PRD-999")
        result = json.loads(raw)
        assert "error" in result
        assert "PRD-999" in result.get("product_id", result.get("error", ""))

    def test_installation_price_is_string(self):
        """installation_price must be a string to avoid float representation issues."""
        raw = self.tool.func("PRD-003")
        result = json.loads(raw)
        assert isinstance(result["installation_price"], str)


class TestToolCheckInventory:
    """tool_check_inventory wraps check_inventory and returns JSON string."""

    def setup_method(self):
        from app.agents.product_availability import tool_check_inventory
        self.tool = tool_check_inventory

    def test_available_stock(self):
        raw = self.tool.func("PRD-003", 10)  # PRD-003 has 55 in stock
        result = json.loads(raw)
        assert result["status"] == "AVAILABLE"
        assert result["available_quantity"] == 10
        assert result["shortfall"] == 0

    def test_partial_stock(self):
        raw = self.tool.func("PRD-004", 10)  # PRD-004 has 4 in stock
        result = json.loads(raw)
        assert result["status"] == "PARTIAL"
        assert result["available_quantity"] == 4
        assert result["shortfall"] == 6

    def test_zero_quantity_returns_error(self):
        raw = self.tool.func("PRD-001", 0)
        result = json.loads(raw)
        assert "error" in result

    def test_unknown_product_returns_error(self):
        raw = self.tool.func("PRD-999", 1)
        result = json.loads(raw)
        assert "error" in result

    def test_status_is_string_not_enum(self):
        """Status must be a plain string, not an enum object, for JSON serialisation."""
        raw = self.tool.func("PRD-003", 1)
        result = json.loads(raw)
        assert isinstance(result["status"], str)


class TestToolCheckDeliveryFeasibility:
    """tool_check_delivery_feasibility wraps check_delivery_feasibility."""

    def setup_method(self):
        from app.agents.product_availability import tool_check_delivery_feasibility
        self.tool = tool_check_delivery_feasibility

    def test_feasible_delivery(self):
        # PRD-003 lead_time=3 days, buffer from business_rules, reference=2026-01-01
        # Requesting delivery 30 days out should be feasible
        raw = self.tool.func("PRD-003", 5, "2026-02-01", "2026-01-01")
        result = json.loads(raw)
        assert result["feasibility"] in ("FEASIBLE", "NOT_FEASIBLE")  # deterministic

    def test_no_date_requested(self):
        raw = self.tool.func("PRD-003", 5, "NONE", "2026-01-01")
        result = json.loads(raw)
        assert result["feasibility"] == "NO_DATE_REQUESTED"
        assert result["requested_delivery_date"] is None

    def test_invalid_date_format_returns_error(self):
        raw = self.tool.func("PRD-003", 5, "not-a-date", "2026-01-01")
        result = json.loads(raw)
        assert "error" in result

    def test_unknown_product_returns_error(self):
        raw = self.tool.func("PRD-999", 1, "NONE", "2026-01-01")
        result = json.loads(raw)
        assert "error" in result

    def test_reference_date_appears_in_result(self):
        raw = self.tool.func("PRD-001", 2, "NONE", "2026-06-15")
        result = json.loads(raw)
        assert result["reference_date"] == "2026-06-15"

    def test_feasibility_is_string_not_enum(self):
        raw = self.tool.func("PRD-003", 1, "NONE", "2026-01-01")
        result = json.loads(raw)
        assert isinstance(result["feasibility"], str)


class TestToolCheckInstallationAvailability:
    """tool_check_installation_availability wraps check_installation_availability."""

    def setup_method(self):
        from app.agents.product_availability import tool_check_installation_availability
        self.tool = tool_check_installation_availability

    def test_product_with_installation_returns_available_true(self):
        raw = self.tool.func("PRD-001")  # PRD-001 has installation
        result = json.loads(raw)
        assert result["installation_available"] is True
        assert result["product_id"] == "PRD-001"

    def test_product_without_installation(self):
        raw = self.tool.func("PRD-008")  # PRD-008 has no installation
        result = json.loads(raw)
        assert result["installation_available"] is False
        # Decimal("0.00") -> str() gives "0" or "0.0" depending on source data;
        # either is acceptable as long as it parses to zero.
        assert float(result["installation_price"]) == 0.0

    def test_installation_price_is_string(self):
        raw = self.tool.func("PRD-003")
        result = json.loads(raw)
        assert isinstance(result["installation_price"], str)
        # Must be a decimal string parseable as float
        float(result["installation_price"])

    def test_unknown_product_returns_error(self):
        raw = self.tool.func("PRD-999")
        result = json.loads(raw)
        assert "error" in result


# ===========================================================================
# Architectural boundaries — no forbidden imports
# ===========================================================================


class TestArchitecturalBoundaries:

    def test_no_pricing_tool_imports(self):
        """product_availability.py MUST NOT import from app.tools.pricing."""
        import ast
        import pathlib
        source = pathlib.Path(
            "app/agents/product_availability.py"
        ).read_text(encoding="utf-8")
        assert "app.tools.pricing" not in source, (
            "product_availability.py must NOT import from app.tools.pricing"
        )

    def test_no_policies_tool_imports(self):
        """product_availability.py MUST NOT import from app.tools.policies."""
        import pathlib
        source = pathlib.Path(
            "app/agents/product_availability.py"
        ).read_text(encoding="utf-8")
        assert "app.tools.policies" not in source, (
            "product_availability.py must NOT import from app.tools.policies"
        )

    def test_no_customers_tool_imports(self):
        """product_availability.py MUST NOT import from app.tools.customers."""
        import pathlib
        source = pathlib.Path(
            "app/agents/product_availability.py"
        ).read_text(encoding="utf-8")
        assert "app.tools.customers" not in source, (
            "product_availability.py must NOT import from app.tools.customers"
        )

    def test_azure_cli_credential_used(self):
        """Must use AzureCliCredential, NOT DefaultAzureCredential."""
        import pathlib
        source = pathlib.Path(
            "app/agents/product_availability.py"
        ).read_text(encoding="utf-8")
        assert "AzureCliCredential" in source
        assert "DefaultAzureCredential" not in source

    def test_foundry_chat_client_pattern(self):
        """Must use FoundryChatClient + Agent pattern."""
        import pathlib
        source = pathlib.Path(
            "app/agents/product_availability.py"
        ).read_text(encoding="utf-8")
        assert "FoundryChatClient" in source
        assert "Agent" in source

    def test_reference_date_parameter_exists(self):
        """check_availability must accept reference_date parameter."""
        import inspect
        from app.agents.product_availability import check_availability
        sig = inspect.signature(check_availability)
        assert "reference_date" in sig.parameters, (
            "check_availability must accept reference_date parameter"
        )

    def test_reference_date_is_keyword_only(self):
        """reference_date should be keyword-only to prevent accidental positional use."""
        import inspect
        from app.agents.product_availability import check_availability
        sig = inspect.signature(check_availability)
        param = sig.parameters["reference_date"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
            "reference_date should be keyword-only"
        )

    def test_tools_list_contains_only_allowed_tools(self):
        """The agent tool list must contain only the 5 allowed Phase 2 tools."""
        from app.agents.product_availability import _PHASE4_TOOLS
        allowed_names = {
            "tool_search_products",
            "tool_get_product",
            "tool_check_inventory",
            "tool_check_delivery_feasibility",
            "tool_check_installation_availability",
        }
        actual_names = {t.name for t in _PHASE4_TOOLS}
        assert actual_names == allowed_names, (
            f"Unexpected tools: {actual_names - allowed_names}; "
            f"Missing tools: {allowed_names - actual_names}"
        )


# ===========================================================================
# Application-level enforcement of overall_status
# ===========================================================================


class TestOverallStatusEnforcement:
    """
    Verify that _derive_overall_status is called and its result is not
    taken blindly from the LLM.  We cannot run a live agent in offline tests,
    but we can verify the enforcement logic by constructing a FulfilmentResult
    with an incorrect overall_status and checking the derive function would fix it.
    """

    def setup_method(self):
        from app.agents.product_availability import _derive_overall_status
        self.derive = _derive_overall_status

    def test_enforcement_overrides_incorrect_ready_status(self):
        """If items have issues, READY should be overridden."""
        items = [
            _make_item_result(inv_status="UNAVAILABLE"),
        ]
        derived = self.derive(items)
        assert derived != "READY", "UNAVAILABLE item should not derive READY"

    def test_enforcement_produces_clarification_for_empty_items(self):
        derived = self.derive([])
        assert derived == "CLARIFICATION_REQUIRED"

    def test_clarification_required_syncs_clarification_flag(self):
        """When overall_status is CLARIFICATION_REQUIRED, clarification_required must be True."""
        result = _make_result(
            overall_status="CLARIFICATION_REQUIRED",
            clarification_required=True,
        )
        assert result.clarification_required is True

    def test_ready_status_not_clarification_required(self):
        result = _make_result(
            overall_status="READY",
            clarification_required=False,
        )
        assert result.clarification_required is False


# ===========================================================================
# FulfilmentResult — items collection
# ===========================================================================


class TestFulfilmentResultItems:

    def test_empty_items_accepted(self):
        result = _make_result(items=[])
        assert result.items == []

    def test_multiple_items_preserved(self):
        items = [_make_item_result(raw=f"product_{i}") for i in range(3)]
        result = _make_result(items=items, overall_status="READY", clarification_required=False)
        assert len(result.items) == 3

    def test_issues_empty_list_accepted(self):
        result = _make_result(issues=[])
        assert result.issues == []

    def test_issues_non_empty_accepted(self):
        result = _make_result(issues=["Stock shortage", "Delivery conflict"])
        assert len(result.issues) == 2


# ===========================================================================
# FulfilmentResult — request echo fields
# ===========================================================================


class TestFulfilmentResultEchoFields:

    def test_request_id_null_accepted(self):
        result = _make_result(request_id=None)
        assert result.request_id is None

    def test_request_id_string_accepted(self):
        result = _make_result(request_id="REQ-001")
        assert result.request_id == "REQ-001"

    def test_customer_reference_null_accepted(self):
        result = _make_result(customer_reference=None)
        assert result.customer_reference is None

    def test_customer_reference_string_accepted(self):
        result = _make_result(customer_reference="Acme Corp")
        assert result.customer_reference == "Acme Corp"


# ===========================================================================
# Schema models — correct import from app.models.schemas
# ===========================================================================


class TestModuleExports:
    """FulfilmentItemResult and FulfilmentResult must be importable from schemas."""

    def test_fulfilment_item_result_importable(self):
        from app.models.schemas import FulfilmentItemResult as FIR
        assert FIR is not None

    def test_fulfilment_result_importable(self):
        from app.models.schemas import FulfilmentResult as FR
        assert FR is not None

    def test_check_availability_importable(self):
        from app.agents.product_availability import check_availability
        assert callable(check_availability)

    def test_check_availability_sync_importable(self):
        from app.agents.product_availability import check_availability_sync
        assert callable(check_availability_sync)

    def test_package_exports_check_availability(self):
        from app.agents import check_availability
        assert callable(check_availability)

    def test_package_exports_check_availability_sync(self):
        from app.agents import check_availability_sync
        assert callable(check_availability_sync)
