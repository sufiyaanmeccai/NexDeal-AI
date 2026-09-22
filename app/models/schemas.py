"""
app/models/schemas.py — NexDeal AI  |  Phases 3 & 4 Pydantic schemas

Defines the CANONICAL structured output types produced by the Request
Understanding Agent (Phase 3) and the Product & Availability Agent (Phase 4).

Design constraints
------------------
* Microsoft Foundry strict JSON Schema requires ALL fields to be listed in
  ``required``.  In Pydantic v2 a field is only emitted to ``required`` when
  it has **no default value**.  Therefore every field here is declared with
  ``Field(...)`` (required sentinel) so the generated JSON schema includes
  every field in ``required`` while still allowing the model to return JSON
  null (or an empty collection) when the information is absent.

* Collections that may be empty are typed as plain list — never Optional —
  so the model returns ``[]`` rather than null when nothing is present.

* Status fields use ``Literal[...]`` to prevent the LLM from inventing
  arbitrary status names.  This is enforced by Pydantic validation on
  construction, not just by documentation.

* ``FulfilmentResult`` and ``FulfilmentItemResult`` are produced by Phase 4.
  Phase 3's ``StructuredRequest`` is NOT modified.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequestedItem(BaseModel):
    """
    A single product line-item extracted from an unstructured customer request.

    All fields appear in the JSON schema ``required`` list (Foundry strict mode).

    ``product_id`` is ONLY populated when the customer explicitly provides a
    canonical identifier (e.g. a part number like "SW-1007").  It is NEVER
    inferred from descriptive text such as "enterprise 48-port switches".

    ``specifications`` is a list of strings in "key: value" format because
    Foundry strict JSON Schema mode rejects ``additionalProperties`` schemas
    (which ``dict[str, str]`` would generate).  An empty list means no
    specifications were stated.
    """

    raw_product_reference: str = Field(
        ...,
        description=(
            "The customer's exact words describing this product — preserved "
            "verbatim, no normalisation or paraphrasing."
        ),
    )
    product_id: str | None = Field(
        ...,
        description=(
            "Canonical product identifier ONLY when the customer explicitly "
            "supplies one (e.g. 'SW-1007', 'PROD-42'). "
            "NEVER infer a product_id from descriptive text. "
            "Return null when the customer does not provide a canonical ID."
        ),
    )
    quantity: int | None = Field(
        ...,
        description=(
            "Numeric quantity requested, or null when absent or ambiguous."
        ),
    )
    specifications: list[str] = Field(
        ...,
        description=(
            "Explicitly stated product specifications as 'key: value' strings "
            "(e.g. ['port_count: 48', 'colour: black', 'speed: 10GbE']). "
            "Use an empty list [] when no specifications are mentioned."
        ),
    )


class StructuredRequest(BaseModel):
    """
    Canonical structured representation of a complete B2B customer request.

    Produced by the Request Understanding Agent.  All fields appear in the
    JSON schema ``required`` list (Foundry strict mode).

    This model captures ONLY what the customer stated — it contains no
    business-rule evaluations, no pricing, no inventory data, and no
    canonical product resolution.
    """

    request_id: str | None = Field(
        ...,
        description=(
            "Application-assigned request identifier.  The model must not "
            "invent a meaningful ID — return null in model output."
        ),
    )
    raw_request: str = Field(
        ...,
        description=(
            "The complete original customer request text, preserved faithfully."
        ),
    )
    customer_reference: str | None = Field(
        ...,
        description=(
            "Customer name or company as stated in the request, "
            "or null if not identifiable."
        ),
    )
    requested_items: list[RequestedItem] = Field(
        ...,
        description=(
            "One RequestedItem per distinct product mentioned. "
            "Use an empty list [] when no products are mentioned."
        ),
    )
    requested_delivery_date: str | None = Field(
        ...,
        description=(
            "Requested delivery date as stated by the customer. "
            "Normalise to ISO 8601 (YYYY-MM-DD) ONLY when the date is fully "
            "explicit and unambiguous, INCLUDING the year (e.g. '15 October 2026' -> '2026-10-15'). "
            "If the customer specifies only a month and day without a year (e.g. '15 October'), "
            "do NOT infer or guess a year — preserve the raw phrasing (e.g. '15 October') "
            "or return null, and record that the delivery year is unspecified in ambiguities or missing_information. "
            "Preserve original phrasing when it is relative or vague (e.g. 'end of next week'). "
            "Return null when not mentioned."
        ),
    )
    installation_required: bool | None = Field(
        ...,
        description=(
            "True if the customer explicitly requests installation. "
            "False if the customer explicitly states installation is NOT needed. "
            "Null if installation is not mentioned."
        ),
    )
    requested_services: list[str] = Field(
        ...,
        description=(
            "List of additional services requested (e.g. 'extended warranty', "
            "'on-site training'). Use an empty list [] when none are requested."
        ),
    )
    requested_discount_percent: float | None = Field(
        ...,
        description=(
            "Percentage discount the customer explicitly requests "
            "(e.g. 12 for '12% discount'). "
            "Return null when no percentage discount is mentioned. "
            "Do NOT convert fixed-amount discounts (e.g. '₹10,000 off') "
            "into a percentage."
        ),
    )
    missing_information: list[str] = Field(
        ...,
        description=(
            "List of fields or details that would normally be needed to "
            "fulfil the order but are absent from this request "
            "(e.g. 'quantity not specified', 'delivery address missing'). "
            "Use an empty list [] when the request is complete."
        ),
    )
    ambiguities: list[str] = Field(
        ...,
        description=(
            "List of conflicting or unclear statements detected in the request "
            "(e.g. 'two different delivery dates mentioned'). "
            "Use an empty list [] when none are detected."
        ),
    )


# ===========================================================================
# Phase 4 — Product & Availability Agent output schemas
# ===========================================================================


class FulfilmentItemResult(BaseModel):
    """
    Availability result for a single product line-item from a StructuredRequest.

    Produced by the Product & Availability Agent.  All fields appear in the
    JSON schema ``required`` list (Foundry strict mode).

    Key contracts
    -------------
    * ``resolved_product_id`` — null when product could not be uniquely
      resolved; the authoritative value comes from Phase 2 ``get_product``.
    * ``available_quantity`` — null when inventory was not checked (e.g. product
      unresolved); otherwise the authoritative value from Phase 2
      ``check_inventory``.
    * ``installation_price`` — stored as a decimal string (e.g. ``"450.00"``)
      to avoid floating-point representation errors from the Phase 2 Decimal layer.
    * Status fields use ``Literal[...]`` — invalid strings are rejected by Pydantic.
    """

    raw_product_reference: str = Field(
        ...,
        description=(
            "The customer's original product description from the StructuredRequest, "
            "preserved verbatim."
        ),
    )
    resolved_product_id: str | None = Field(
        ...,
        description=(
            "Authoritative product ID after resolution. "
            "Null when unresolved (AMBIGUOUS or NOT_FOUND)."
        ),
    )
    product_resolution_status: Literal["RESOLVED", "AMBIGUOUS", "NOT_FOUND"] = Field(
        ...,
        description=(
            "RESOLVED — exactly one catalogue match found and confirmed via get_product. "
            "AMBIGUOUS — multiple plausible matches; clarification needed. "
            "NOT_FOUND — no catalogue match found."
        ),
    )
    requested_quantity: int | None = Field(
        ...,
        description="Quantity from the StructuredRequest, or null if not specified.",
    )
    available_quantity: int | None = Field(
        ...,
        description=(
            "Authoritative available quantity from check_inventory. "
            "Null when product is unresolved or inventory was not checked."
        ),
    )
    inventory_status: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_EVALUATED"] = Field(
        ...,
        description=(
            "AVAILABLE — full quantity in stock. "
            "PARTIAL — some stock but less than requested. "
            "UNAVAILABLE — zero stock. "
            "NOT_EVALUATED — product unresolved or quantity unknown."
        ),
    )
    requested_delivery_date: str | None = Field(
        ...,
        description=(
            "Delivery date from the StructuredRequest. "
            "Null when not specified. May be an incomplete date (e.g. '15 October') "
            "if the year was not specified — do NOT normalise here."
        ),
    )
    delivery_status: Literal[
        "FEASIBLE", "INFEASIBLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"
    ] = Field(
        ...,
        description=(
            "FEASIBLE — delivery can be achieved by the requested date. "
            "INFEASIBLE — earliest dispatch is after the requested date. "
            "NOT_REQUESTED — no delivery date was specified. "
            "NEEDS_CLARIFICATION — date is incomplete (e.g. missing year) so "
            "delivery cannot be evaluated. "
            "NOT_EVALUATED — product unresolved; delivery not checked."
        ),
    )
    installation_required: bool | None = Field(
        ...,
        description=(
            "True/False as stated in StructuredRequest, or null if unspecified."
        ),
    )
    installation_status: Literal[
        "AVAILABLE", "UNAVAILABLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"
    ] = Field(
        ...,
        description=(
            "AVAILABLE — installation offered and confirmed available for this product. "
            "UNAVAILABLE — installation not available for this product. "
            "NOT_REQUESTED — customer explicitly said installation is not needed, "
            "or installation_required is false. "
            "NEEDS_CLARIFICATION — installation_required is null; cannot determine. "
            "NOT_EVALUATED — product unresolved."
        ),
    )
    installation_price: str | None = Field(
        ...,
        description=(
            "Authoritative installation price as a decimal string (e.g. '450.00'), "
            "taken directly from the Phase 2 tool without floating-point conversion. "
            "Null when installation is not available, not requested, or product is unresolved."
        ),
    )
    issues: list[str] = Field(
        ...,
        description=(
            "Human-readable descriptions of any problems encountered for this item "
            "(e.g. 'Product not found', 'Delivery year unspecified', "
            "'Only 5 units available, 10 requested'). "
            "Use an empty list [] when there are no issues."
        ),
    )


class FulfilmentResult(BaseModel):
    """
    Complete availability determination for a StructuredRequest.

    Produced by the Product & Availability Agent.  All fields appear in the
    JSON schema ``required`` list (Foundry strict mode).

    ``overall_status`` is ALWAYS computed deterministically by the application
    layer from the per-item results.  The LLM output is overwritten by Python
    logic before returning this object.
    """

    request_id: str | None = Field(
        ...,
        description="Echoed from the StructuredRequest.request_id.",
    )
    customer_reference: str | None = Field(
        ...,
        description="Echoed from the StructuredRequest.customer_reference.",
    )
    items: list[FulfilmentItemResult] = Field(
        ...,
        description="Per-item availability results, one per RequestedItem in the StructuredRequest.",
    )
    overall_status: Literal[
        "READY",
        "PARTIAL",
        "UNAVAILABLE",
        "CLARIFICATION_REQUIRED",
        "DELIVERY_CONFLICT",
        "INSTALLATION_UNAVAILABLE",
    ] = Field(
        ...,
        description=(
            "Application-derived summary status (NOT trusted from LLM output). "
            "Precedence (highest first): "
            "1. CLARIFICATION_REQUIRED — any unresolved product or incomplete date. "
            "2. INSTALLATION_UNAVAILABLE — any installation-required item unavailable. "
            "3. DELIVERY_CONFLICT — any infeasible delivery. "
            "4. UNAVAILABLE — any item with zero stock. "
            "5. PARTIAL — any item with partial stock. "
            "6. READY — all required checks pass."
        ),
    )
    clarification_required: bool = Field(
        ...,
        description="True when overall_status is CLARIFICATION_REQUIRED.",
    )
    issues: list[str] = Field(
        ...,
        description=(
            "Aggregated top-level issues across all items. "
            "Use an empty list [] when there are no issues."
        ),
    )
