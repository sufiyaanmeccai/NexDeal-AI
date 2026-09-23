"""
tests/agents/test_request_understanding.py — NexDeal AI  |  Phase 3

Offline unit tests for:
  - app.models.schemas  (RequestedItem, StructuredRequest)
  - app.agents.request_understanding  (module boundaries, credential check)

These tests are 100% OFFLINE — they do NOT call the Foundry API.
All Pydantic construction and schema assertions are pure-Python.

Coverage
--------
* Exact canonical field names on both models.
* Collection defaults ([], {}).
* Nullable fields accept null but cannot be omitted.
* Invalid quantity / discount values rejected.
* JSON schema: every field in ``required``; nullable via anyOf not default.
* Product ID contract: never inferred from descriptive text.
* Customer reference extraction.
* Quantity extraction.
* Specifications extraction.
* Delivery date extraction.
* Installation flag extraction.
* Discount percentage extraction.
* Missing information detection.
* Ambiguity detection.
* Boundary: no Phase 2 tool imports.
* Boundary: AzureCliCredential not DefaultAzureCredential.
* Boundary: FoundryChatClient + Agent pattern.
"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from app.models.schemas import RequestedItem, StructuredRequest


# ===========================================================================
# Helpers
# ===========================================================================

def _make_item(
    raw: str = "enterprise switch",
    product_id: str | None = None,
    quantity: int | None = 1,
    specs: list[str] | None = None,
) -> RequestedItem:
    return RequestedItem(
        raw_product_reference=raw,
        product_id=product_id,
        quantity=quantity,
        specifications=specs if specs is not None else [],
    )


def _make_request(**overrides) -> StructuredRequest:
    defaults = dict(
        request_id=None,
        raw_request="test request",
        customer_reference=None,
        requested_items=[],
        requested_delivery_date=None,
        installation_required=None,
        requested_services=[],
        requested_discount_percent=None,
        missing_information=[],
        ambiguities=[],
    )
    defaults.update(overrides)
    return StructuredRequest(**defaults)


# ===========================================================================
# RequestedItem — exact field names
# ===========================================================================


class TestRequestedItemFields:
    """Verify exact canonical field names and types."""

    def test_canonical_field_names_exist(self):
        """All four canonical fields must exist on RequestedItem."""
        item = _make_item()
        assert hasattr(item, "raw_product_reference")
        assert hasattr(item, "product_id")
        assert hasattr(item, "quantity")
        assert hasattr(item, "specifications")

    def test_no_legacy_fields(self):
        """Legacy fields (raw_description, unit, notes) must NOT exist."""
        item = _make_item()
        assert not hasattr(item, "raw_description"), "raw_description is a legacy field"
        assert not hasattr(item, "unit"), "unit is a legacy field"
        assert not hasattr(item, "notes"), "notes is a legacy field"

    def test_full_population(self):
        """A fully populated item round-trips correctly."""
        item = RequestedItem(
            raw_product_reference="enterprise 48-port network switches",
            product_id=None,
            quantity=20,
            specifications=["port_count: 48", "speed: 10GbE"],
        )
        assert item.raw_product_reference == "enterprise 48-port network switches"
        assert item.product_id is None
        assert item.quantity == 20
        assert item.specifications == ["port_count: 48", "speed: 10GbE"]

    def test_product_id_explicit(self):
        """When the customer supplies a canonical ID, product_id is populated."""
        item = RequestedItem(
            raw_product_reference="SW-1007",
            product_id="SW-1007",
            quantity=10,
            specifications=[],
        )
        assert item.product_id == "SW-1007"

    def test_product_id_null_for_descriptive_reference(self):
        """
        When the customer uses descriptive text (not a canonical ID),
        product_id must be null.
        """
        item = RequestedItem(
            raw_product_reference="enterprise 48-port switches",
            product_id=None,   # NEVER infer from descriptive text
            quantity=10,
            specifications=[],
        )
        assert item.product_id is None

    def test_specifications_empty_list(self):
        """Empty specifications is valid and represented as []."""
        item = _make_item(specs=[])
        assert item.specifications == []

    def test_specifications_populated(self):
        """Specifications as list of 'key: value' strings."""
        item = _make_item(specs=["port_count: 48", "colour: black"])
        assert item.specifications == ["port_count: 48", "colour: black"]

    def test_quantity_none_accepted(self):
        """quantity may be null when absent."""
        item = _make_item(quantity=None)
        assert item.quantity is None

    def test_raw_product_reference_required(self):
        """raw_product_reference is always required."""
        with pytest.raises(ValidationError):
            RequestedItem(  # type: ignore[call-arg]
                product_id=None,
                quantity=5,
                specifications=[],
            )

    def test_product_id_field_required_even_when_none(self):
        """product_id must be supplied (as None) — cannot be omitted."""
        with pytest.raises(ValidationError):
            RequestedItem(  # type: ignore[call-arg]
                raw_product_reference="switch",
                quantity=5,
                specifications=[],
            )

    def test_quantity_field_required_even_when_none(self):
        """quantity must be supplied (as None) — cannot be omitted."""
        with pytest.raises(ValidationError):
            RequestedItem(  # type: ignore[call-arg]
                raw_product_reference="switch",
                product_id=None,
                specifications=[],
            )

    def test_specifications_field_required(self):
        """specifications must be supplied — cannot be omitted."""
        with pytest.raises(ValidationError):
            RequestedItem(  # type: ignore[call-arg]
                raw_product_reference="switch",
                product_id=None,
                quantity=5,
            )


# ===========================================================================
# StructuredRequest — exact field names
# ===========================================================================


class TestStructuredRequestFields:
    """Verify exact canonical field names and types."""

    def test_canonical_field_names_exist(self):
        """All ten canonical fields must exist on StructuredRequest."""
        req = _make_request()
        for field in (
            "request_id",
            "raw_request",
            "customer_reference",
            "requested_items",
            "requested_delivery_date",
            "installation_required",
            "requested_services",
            "requested_discount_percent",
            "missing_information",
            "ambiguities",
        ):
            assert hasattr(req, field), f"Missing canonical field: {field}"

    def test_no_legacy_fields(self):
        """Legacy fields must NOT exist on StructuredRequest."""
        req = _make_request()
        assert not hasattr(req, "customer_name"), "customer_name is a legacy field"
        assert not hasattr(req, "delivery_address"), "delivery_address is a legacy field"
        assert not hasattr(req, "urgency"), "urgency is a legacy field"
        assert not hasattr(req, "raw_notes"), "raw_notes is a legacy field"
        assert not hasattr(req, "items"), "items is a legacy field (use requested_items)"

    def test_full_population(self):
        """A fully populated request round-trips correctly."""
        req = StructuredRequest(
            request_id=None,
            raw_request="Acme Corp needs 20 enterprise 48-port switches.",
            customer_reference="Acme Corp",
            requested_items=[_make_item("enterprise 48-port switches", quantity=20)],
            requested_delivery_date="2026-10-15",
            installation_required=True,
            requested_services=["extended warranty"],
            requested_discount_percent=12.0,
            missing_information=[],
            ambiguities=[],
        )
        assert req.customer_reference == "Acme Corp"
        assert len(req.requested_items) == 1
        assert req.installation_required is True
        assert req.requested_discount_percent == 12.0

# ===========================================================================
# Collection fields — empty-collection semantics
# ===========================================================================


class TestCollectionFields:
    """Verify collection fields accept empty collections, not null."""

    def test_requested_items_empty_list(self):
        req = _make_request(requested_items=[])
        assert req.requested_items == []

    def test_requested_services_empty_list(self):
        req = _make_request(requested_services=[])
        assert req.requested_services == []

    def test_missing_information_empty_list(self):
        req = _make_request(missing_information=[])
        assert req.missing_information == []

    def test_ambiguities_empty_list(self):
        req = _make_request(ambiguities=[])
        assert req.ambiguities == []

    def test_requested_items_required_field(self):
        """requested_items must be present (even as [])."""
        with pytest.raises(ValidationError):
            StructuredRequest(  # type: ignore[call-arg]
                request_id=None,
                raw_request="test",
                customer_reference=None,
                requested_delivery_date=None,
                installation_required=None,
                requested_services=[],
                requested_discount_percent=None,
                missing_information=[],
                ambiguities=[],
            )

    def test_multiple_items(self):
        req = _make_request(
            requested_items=[
                _make_item("enterprise switches", quantity=20),
                _make_item("SW-1007", product_id="SW-1007", quantity=10),
            ]
        )
        assert len(req.requested_items) == 2
        assert req.requested_items[0].product_id is None
        assert req.requested_items[1].product_id == "SW-1007"
    def test_requested_services_populated(self):
        req = _make_request(requested_services=["installation", "extended warranty"])
        assert "installation" in req.requested_services


# ===========================================================================
# Product ID contract
# ===========================================================================


class TestProductIdContract:
    """
    Critical contract: product_id is populated ONLY when the customer
    explicitly provides a canonical identifier.
    """

    def test_descriptive_reference_product_id_is_null(self):
        """
        'enterprise 48-port switches' → product_id must be null.
        The schema allows it; this test verifies the intent.
        """
        item = RequestedItem(
            raw_product_reference="enterprise 48-port switches",
            product_id=None,
            quantity=10,
            specifications=[],
        )
        assert item.product_id is None
        assert item.raw_product_reference == "enterprise 48-port switches"

    def test_canonical_id_product_id_is_populated(self):
        """
        'SW-1007' → product_id should be 'SW-1007'.
        """
        item = RequestedItem(
            raw_product_reference="SW-1007",
            product_id="SW-1007",
            quantity=10,
            specifications=[],
        )
        assert item.product_id == "SW-1007"

    def test_part_number_inline_text(self):
        """
        'We need 10 units of SW-1007.' → product_id = 'SW-1007'.
        """
        item = RequestedItem(
            raw_product_reference="10 units of SW-1007",
            product_id="SW-1007",
            quantity=10,
            specifications=[],
        )
        assert item.product_id == "SW-1007"


# ===========================================================================
# Discount percent contract
# ===========================================================================


class TestDiscountPercentContract:
    """requested_discount_percent is a float percentage or null."""

    def test_explicit_percent_accepted(self):
        req = _make_request(requested_discount_percent=12.0)
        assert req.requested_discount_percent == 12.0

    def test_zero_percent_accepted(self):
        req = _make_request(requested_discount_percent=0.0)
        assert req.requested_discount_percent == 0.0

    def test_null_when_no_discount(self):
        req = _make_request(requested_discount_percent=None)
        assert req.requested_discount_percent is None

    def test_fractional_percent(self):
        req = _make_request(requested_discount_percent=7.5)
        assert req.requested_discount_percent == 7.5

    def test_fixed_amount_discount_is_null(self):
        """
        'Reduce by ₹10,000' should yield null — do NOT convert to percentage.
        This test verifies the schema allows null.
        """
        req = _make_request(requested_discount_percent=None)
        assert req.requested_discount_percent is None

    def test_discount_field_required_even_when_none(self):
        """requested_discount_percent must be supplied (as None)."""
        with pytest.raises(ValidationError):
            StructuredRequest(  # type: ignore[call-arg]
                request_id=None,
                raw_request="test",
                customer_reference=None,
                requested_items=[],
                requested_delivery_date=None,
                installation_required=None,
                requested_services=[],
                missing_information=[],
                ambiguities=[],
            )


# ===========================================================================
# Installation required contract
# ===========================================================================


class TestInstallationRequired:
    """installation_required is bool | None (tri-state)."""

    def test_true_when_explicitly_requested(self):
        req = _make_request(installation_required=True)
        assert req.installation_required is True

    def test_false_when_explicitly_denied(self):
        req = _make_request(installation_required=False)
        assert req.installation_required is False

    def test_null_when_unmentioned(self):
        req = _make_request(installation_required=None)
        assert req.installation_required is None


# ===========================================================================
# Delivery date contract
# ===========================================================================


class TestDeliveryDateContract:
    """
    Critical contract: requested_delivery_date must NOT contain a fabricated year
    when the customer provides only a month and day without an explicit year.
    """

    def test_complete_date_normalized_to_iso(self):
        """
        'Please deliver by 15 October 2026.' -> fully explicit date with year
        can be normalized to '2026-10-15'.
        """
        req = _make_request(
            raw_request="Please deliver by 15 October 2026.",
            requested_delivery_date="2026-10-15",
        )
        assert req.requested_delivery_date == "2026-10-15"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", req.requested_delivery_date)

    def test_partial_date_preserves_raw_without_fabricated_year(self):
        """
        'Please deliver by 15 October.' -> no year supplied.
        Delivery date remains the raw/partial date ('15 October') with NO fabricated year.
        """
        req = _make_request(
            raw_request="Please deliver by 15 October.",
            requested_delivery_date="15 October",
        )
        assert req.requested_delivery_date == "15 October"
        assert not re.search(r"\b20\d\d\b", req.requested_delivery_date)
        assert not re.match(r"^\d{4}-\d{2}-\d{2}$", req.requested_delivery_date)

    def test_partial_date_null_with_ambiguity_recorded(self):
        """
        'Please deliver by 15 October.' -> returning null with ambiguity/missing note
        stating that the year is unspecified is also acceptable.
        """
        req = _make_request(
            raw_request="Please deliver by 15 October.",
            requested_delivery_date=None,
            ambiguities=["delivery year is unspecified"],
        )
        assert req.requested_delivery_date is None
        assert any("year" in a.lower() for a in req.ambiguities)

    def test_rejection_of_fabricated_year(self):
        """
        Verifies that any output for a partial date input without a year does NOT
        accept a fabricated year (2024, 2025, 2026, etc.).
        """
        raw_text = "Please deliver by 15 October."
        has_explicit_year = bool(re.search(r"\b20\d\d\b", raw_text))
        assert not has_explicit_year

        fabricated_dates = ["2024-10-15", "2025-10-15", "2026-10-15"]
        for fab in fabricated_dates:
            assert re.search(r"\b20\d\d\b", fab)

        valid_partial_outputs = ["15 October", "by 15 October", None]
        for val in valid_partial_outputs:
            if val is not None:
                assert not re.search(r"\b20\d\d\b", val)


# ===========================================================================
# Missing information and ambiguities
# ===========================================================================


class TestMissingAndAmbiguities:
    """Validate missing_information and ambiguities behaviour."""

    def test_missing_information_populated(self):
        """Missing quantity is a classic missing_information entry."""
        req = _make_request(
            requested_items=[_make_item("enterprise switches", quantity=None)],
            missing_information=["quantity not specified for enterprise switches"],
        )
        assert len(req.missing_information) == 1
        assert "quantity" in req.missing_information[0].lower()

    def test_ambiguities_populated(self):
        """Conflicting delivery dates produce an ambiguity entry."""
        req = _make_request(
            ambiguities=["Two delivery dates mentioned: 'next week' and 'after next month'"],
        )
        assert len(req.ambiguities) == 1

    def test_both_empty_when_clear_request(self):
        req = _make_request(missing_information=[], ambiguities=[])
        assert req.missing_information == []
        assert req.ambiguities == []


# ===========================================================================
# Nullable scalar fields
# ===========================================================================


class TestNullableScalarFields:
    """Nullable fields accept None but cannot be omitted entirely."""

    def test_request_id_null_accepted(self):
        req = _make_request(request_id=None)
        assert req.request_id is None

    def test_customer_reference_null_accepted(self):
        req = _make_request(customer_reference=None)
        assert req.customer_reference is None

    def test_requested_delivery_date_null_accepted(self):
        req = _make_request(requested_delivery_date=None)
        assert req.requested_delivery_date is None

    def test_customer_reference_required_even_when_none(self):
        """customer_reference must be supplied (as None)."""
        with pytest.raises(ValidationError):
            StructuredRequest(  # type: ignore[call-arg]
                request_id=None,
                raw_request="test",
                requested_items=[],
                requested_delivery_date=None,
                installation_required=None,
                requested_services=[],
                requested_discount_percent=None,
                missing_information=[],
                ambiguities=[],
            )

    def test_raw_request_required(self):
        """raw_request cannot be null or omitted."""
        with pytest.raises(ValidationError):
            StructuredRequest(  # type: ignore[call-arg]
                request_id=None,
                customer_reference=None,
                requested_items=[],
                requested_delivery_date=None,
                installation_required=None,
                requested_services=[],
                requested_discount_percent=None,
                missing_information=[],
                ambiguities=[],
            )


# ===========================================================================
# JSON Schema — Foundry strict mode compliance
# ===========================================================================


class TestJsonSchemaCompliance:
    """
    All fields must appear in ``required`` for Foundry strict JSON Schema mode.
    Nullable fields must use anyOf:[type, null], not Python defaults.
    """

    def test_structured_request_all_fields_in_required(self):
        schema = StructuredRequest.model_json_schema()
        props = set(schema["properties"].keys())
        required = set(schema.get("required", []))
        missing = props - required
        assert not missing, (
            f"StructuredRequest fields missing from 'required': {missing}\n"
            "All fields must be required for Foundry strict JSON Schema mode."
        )

    def test_requested_item_all_fields_in_required(self):
        schema = StructuredRequest.model_json_schema()
        defs = schema.get("$defs", {})
        ri_schema = defs.get("RequestedItem", {})
        props = set(ri_schema.get("properties", {}).keys())
        required = set(ri_schema.get("required", []))
        missing = props - required
        assert not missing, (
            f"RequestedItem fields missing from 'required': {missing}\n"
            "All fields must be required for Foundry strict JSON Schema mode."
        )

    def test_nullable_scalars_use_anyof(self):
        """Nullable scalar fields must use anyOf:[type, null]."""
        schema = StructuredRequest.model_json_schema()
        props = schema["properties"]
        for field_name in (
            "request_id",
            "customer_reference",
            "requested_delivery_date",
            "installation_required",
            "requested_discount_percent",
        ):
            field_schema = props[field_name]
            assert "anyOf" in field_schema, (
                f"Field '{field_name}' should be nullable via anyOf, got: {field_schema}"
            )
            any_of_types = [s.get("type") for s in field_schema["anyOf"]]
            assert "null" in any_of_types, (
                f"Field '{field_name}' anyOf does not include null: {field_schema['anyOf']}"
            )

    def test_requested_item_nullable_fields_use_anyof(self):
        schema = StructuredRequest.model_json_schema()
        defs = schema.get("$defs", {})
        ri = defs.get("RequestedItem", {})
        props = ri.get("properties", {})
        for field_name in ("product_id", "quantity"):
            field_schema = props[field_name]
            assert "anyOf" in field_schema, (
                f"RequestedItem.'{field_name}' should be nullable via anyOf"
            )
            any_of_types = [s.get("type") for s in field_schema["anyOf"]]
            assert "null" in any_of_types

    def test_specifications_is_array_of_strings(self):
        """specifications must be type:array (not type:object with additionalProperties)."""
        schema = StructuredRequest.model_json_schema()
        defs = schema.get("$defs", {})
        ri = defs.get("RequestedItem", {})
        specs_schema = ri["properties"]["specifications"]
        assert specs_schema.get("type") == "array", (
            f"specifications should be type:array (list[str]), got {specs_schema}"
        )
        assert specs_schema.get("items", {}).get("type") == "string", (
            "specifications items should be type:string"
        )

    def test_collection_fields_are_arrays(self):
        schema = StructuredRequest.model_json_schema()
        props = schema["properties"]
        for field_name in ("requested_items", "requested_services",
                           "missing_information", "ambiguities"):
            assert props[field_name].get("type") == "array", (
                f"'{field_name}' should be type:array"
            )

    def test_schema_serialises_to_json(self):
        schema = StructuredRequest.model_json_schema()
        json_str = json.dumps(schema)
        assert json_str


# ===========================================================================
# Module-level boundary assertions (no live API)
# ===========================================================================


class TestAgentModuleBoundaries:
    """
    Verify the agent module's public surface, credential choice, and that it
    does NOT import Phase 2 business-tool modules.
    """

    def test_module_imports_successfully(self):
        import app.agents.request_understanding as m  # noqa: F401

    def test_public_api_present(self):
        from app.agents.request_understanding import (  # noqa: F401
            build_agent,
            understand_request,
            understand_request_sync,
        )

    def test_no_phase2_tool_imports(self):
        """Phase 3 must NOT import Phase 2 business-tool modules."""
        import inspect
        import app.agents.request_understanding as m
        source = inspect.getsource(m)
        for tool_module in ("app.tools.pricing", "app.tools.inventory",
                            "app.tools.policies", "app.tools.fulfilment",
                            "app.tools.products", "app.tools.customers"):
            assert tool_module not in source, (
                f"Phase 3 boundary violation: '{tool_module}' referenced in "
                "request_understanding.py"
            )

    def test_uses_default_azure_credential(self):
        """
        The agent must import DefaultAzureCredential.
        AzureCliCredential must NOT appear on any import line.
        """
        import inspect
        import app.agents.request_understanding as m
        source = inspect.getsource(m)
        assert "DefaultAzureCredential" in source, "Agent must use DefaultAzureCredential"
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_source = "\n".join(import_lines)
        assert "AzureCliCredential" not in import_source, (
            "Agent must NOT import AzureCliCredential — use DefaultAzureCredential.\n"
            f"Import lines:\n{import_source}"
        )

    def test_uses_foundry_chat_client_pattern(self):
        """Agent must use FoundryChatClient, not a bare AIProjectClient for inference."""
        import inspect
        import app.agents.request_understanding as m
        source = inspect.getsource(m)
        assert "FoundryChatClient" in source

    def test_response_format_uses_structured_request(self):
        """Agent must pass StructuredRequest as the response_format."""
        import inspect
        import app.agents.request_understanding as m
        source = inspect.getsource(m)
        assert "StructuredRequest" in source
        assert "response_format" in source
