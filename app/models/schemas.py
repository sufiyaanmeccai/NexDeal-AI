"""
app/models/schemas.py — NexDeal AI  |  Phase 3 Pydantic schemas

Defines the CANONICAL structured output types produced by the Request
Understanding Agent.

Design constraints
------------------
* Microsoft Foundry strict JSON Schema requires ALL fields to be listed in
  ``required``.  In Pydantic v2 a field is only emitted to ``required`` when
  it has **no default value**.  Therefore every field here is declared with
  ``Field(...)`` (required sentinel) so the generated JSON schema includes
  every field in ``required`` while still allowing the model to return JSON
  null (or an empty collection) when the information is absent.

* Collections that may be empty (``requested_items``, ``requested_services``,
  ``missing_information``, ``ambiguities``, ``specifications``) are typed as
  plain list/dict — never Optional — so the model returns ``[]`` / ``{}``
  rather than null when nothing is present.

* No business-rule concerns here — no prices, no inventory, no canonical IDs.
  The agent only *understands* the request; later pipeline stages do the rest.
"""

from __future__ import annotations

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
