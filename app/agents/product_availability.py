"""
app/agents/product_availability.py — NexDeal AI  |  Phase 4

Product & Availability Agent
=============================
Receives a validated ``StructuredRequest`` from Phase 3, resolves each
requested product against the authoritative catalogue, checks inventory and
fulfilment feasibility using Phase 2 deterministic tools, and returns a
``FulfilmentResult``.

Architectural boundaries (Phase 4)
------------------------------------
* ALLOWED tools (Phase 2, product/fulfilment domain only):
    - search_products          — find matching catalogue entries by keyword
    - get_product              — retrieve authoritative product record by ID
    - check_inventory          — authoritative stock availability
    - check_delivery_feasibility  — delivery date feasibility
    - check_installation_availability  — whether installation is offered
    - get_installation_price   — authoritative installation price

* FORBIDDEN — this agent MUST NOT call:
    - calculate_customer_price, calculate_tax, check_discount_policy,
      get_customer, or any Phase 2 pricing/credit/policy tools.

* ``overall_status`` and ``clarification_required`` on ``FulfilmentResult``
  are ALWAYS computed deterministically by Python after the agent responds.
  The LLM's proposed values are overwritten.

* Date safety: ``reference_date`` is injected explicitly at call time; the
  agent never reads the system clock.

* Authentication: ``AzureCliCredential`` (same as Phase 3).

Usage example::

    import asyncio
    from datetime import date
    from app.agents.product_availability import check_availability
    from app.models.schemas import StructuredRequest

    structured = StructuredRequest(...)
    result = asyncio.run(check_availability(structured, reference_date=date.today()))
    print(result.overall_status)
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import Literal

from azure.identity import AzureCliCredential

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient

from app.config import settings
from app.models.schemas import FulfilmentItemResult, FulfilmentResult, StructuredRequest

# Phase 2 tools — product/fulfilment domain only
from app.tools.fulfilment import (
    check_delivery_feasibility,
    check_installation_availability,
    get_installation_price,
)
from app.tools.inventory import check_inventory
from app.tools.products import ProductNotFoundError, get_product, search_products


# ---------------------------------------------------------------------------
# Status precedence ordering  (descending priority)
# ---------------------------------------------------------------------------

_STATUS_PRECEDENCE: list[Literal[
    "READY",
    "PARTIAL",
    "UNAVAILABLE",
    "CLARIFICATION_REQUIRED",
    "DELIVERY_CONFLICT",
    "INSTALLATION_UNAVAILABLE",
]] = [
    "CLARIFICATION_REQUIRED",
    "INSTALLATION_UNAVAILABLE",
    "DELIVERY_CONFLICT",
    "UNAVAILABLE",
    "PARTIAL",
    "READY",
]


def _derive_overall_status(
    items: list[FulfilmentItemResult],
) -> Literal[
    "READY",
    "PARTIAL",
    "UNAVAILABLE",
    "CLARIFICATION_REQUIRED",
    "DELIVERY_CONFLICT",
    "INSTALLATION_UNAVAILABLE",
]:
    """
    Deterministically derive ``FulfilmentResult.overall_status`` from item results.

    Precedence (highest → lowest):
    1. CLARIFICATION_REQUIRED — any unresolved product (AMBIGUOUS/NOT_FOUND)
       OR any delivery date that NEEDS_CLARIFICATION.
    2. INSTALLATION_UNAVAILABLE — any item where installation was required
       but is UNAVAILABLE.
    3. DELIVERY_CONFLICT — any item with INFEASIBLE delivery.
    4. UNAVAILABLE — any item with UNAVAILABLE inventory.
    5. PARTIAL — any item with PARTIAL inventory.
    6. READY — everything checks out.
    """
    if not items:
        return "CLARIFICATION_REQUIRED"

    candidate_statuses: set[str] = set()

    for item in items:
        if item.product_resolution_status in ("AMBIGUOUS", "NOT_FOUND"):
            candidate_statuses.add("CLARIFICATION_REQUIRED")
        if item.delivery_status == "NEEDS_CLARIFICATION":
            candidate_statuses.add("CLARIFICATION_REQUIRED")
        if item.installation_status == "UNAVAILABLE":
            candidate_statuses.add("INSTALLATION_UNAVAILABLE")
        if item.delivery_status == "INFEASIBLE":
            candidate_statuses.add("DELIVERY_CONFLICT")
        if item.inventory_status == "UNAVAILABLE":
            candidate_statuses.add("UNAVAILABLE")
        if item.inventory_status == "PARTIAL":
            candidate_statuses.add("PARTIAL")

    if not candidate_statuses:
        return "READY"

    for status in _STATUS_PRECEDENCE:
        if status in candidate_statuses:
            return status  # type: ignore[return-value]

    return "READY"


# ---------------------------------------------------------------------------
# Agent-exposed tools (wrappers around Phase 2 tools)
# ---------------------------------------------------------------------------
# Each wrapper is a plain function decorated with @tool so the Agent Framework
# converts it to a FunctionTool.  The wrappers normalise return types to
# JSON-serialisable dicts and handle exceptions gracefully, returning an error
# dict rather than crashing the agent loop.


@tool
def tool_search_products(query: str) -> str:
    """
    Search the product catalogue by keyword.

    Returns a JSON-encoded list of matching product summaries (id, name,
    category, description).  Use this when the customer provided a descriptive
    product reference without an explicit product ID.

    Args:
        query: Free-text search term (e.g. "enterprise 48-port network switch").
    """
    try:
        results = search_products(query)
        # Return only the fields needed for resolution — not prices/margins
        summary = [
            {
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "category": p["category"],
                "description": p["description"],
            }
            for p in results
        ]
        return json.dumps(summary)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_get_product(product_id: str) -> str:
    """
    Retrieve the authoritative product record for a known product ID.

    Returns a JSON-encoded product record including inventory, lead_time_days,
    installation_available, and installation_price.  Call this to confirm a
    product_id that was identified via search_products or supplied directly
    by the customer.

    Args:
        product_id: The exact product identifier (e.g. "PRD-003").
    """
    try:
        record = get_product(product_id)
        # Return only the fields relevant to fulfilment (no pricing columns)
        return json.dumps({
            "product_id": record["product_id"],
            "product_name": record["product_name"],
            "category": record["category"],
            "description": record["description"],
            "inventory": record["inventory"],
            "lead_time_days": record["lead_time_days"],
            "installation_available": record["installation_available"],
            "installation_price": str(record["installation_price"]),
            "status": record["status"],
        })
    except ProductNotFoundError as exc:
        return json.dumps({"error": str(exc), "product_id": product_id})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_check_inventory(product_id: str, quantity: int) -> str:
    """
    Check stock availability for a product against the requested quantity.

    Returns a JSON-encoded dict with keys: status (AVAILABLE/PARTIAL/UNAVAILABLE),
    available_quantity, shortfall, stock_on_hand.

    Args:
        product_id: Confirmed product identifier (e.g. "PRD-003").
        quantity: Number of units requested (must be >= 1).
    """
    try:
        result = check_inventory(product_id, quantity)
        return json.dumps({
            "product_id": result["product_id"],
            "requested_quantity": result["requested_quantity"],
            "stock_on_hand": result["stock_on_hand"],
            "status": result["status"].value if hasattr(result["status"], "value") else str(result["status"]),
            "available_quantity": result["available_quantity"],
            "shortfall": result["shortfall"],
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_check_delivery_feasibility(
    product_id: str,
    quantity: int,
    requested_delivery_date_iso: str,
    reference_date_iso: str,
) -> str:
    """
    Determine whether a product can be delivered by the customer's requested date.

    IMPORTANT: Only call this when requested_delivery_date_iso is a complete,
    fully-specified ISO date (YYYY-MM-DD).  If the date is incomplete (e.g. the
    customer said "15 October" without a year), do NOT call this tool — report
    delivery_status as NEEDS_CLARIFICATION instead.

    Args:
        product_id: Confirmed product identifier (e.g. "PRD-003").
        quantity: Requested quantity (>= 1).
        requested_delivery_date_iso: Requested delivery date as "YYYY-MM-DD",
            or the string "NONE" if no date was specified.
        reference_date_iso: Today's date as "YYYY-MM-DD" (injected by the system).
    """
    try:
        ref = date.fromisoformat(reference_date_iso)
        req_date = (
            None if requested_delivery_date_iso.upper() == "NONE"
            else date.fromisoformat(requested_delivery_date_iso)
        )
        result = check_delivery_feasibility(product_id, quantity, req_date, ref)
        return json.dumps({
            "product_id": result["product_id"],
            "reference_date": result["reference_date"],
            "earliest_dispatch_ready": result["earliest_dispatch_ready"],
            "requested_delivery_date": result["requested_delivery_date"],
            "feasibility": (
                result["feasibility"].value
                if hasattr(result["feasibility"], "value")
                else str(result["feasibility"])
            ),
            "days_to_deadline": result["days_to_deadline"],
            "days_ahead_or_behind": result["days_ahead_or_behind"],
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_check_installation_availability(product_id: str) -> str:
    """
    Check whether installation is available for a product and retrieve the price.

    Returns a JSON-encoded dict with keys: installation_available (bool),
    installation_price (string decimal, e.g. "450.00").

    Args:
        product_id: Confirmed product identifier (e.g. "PRD-003").
    """
    try:
        result = check_installation_availability(product_id)
        return json.dumps({
            "product_id": result["product_id"],
            "installation_available": result["installation_available"],
            "installation_price": str(result["installation_price"]),
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# System instructions
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTIONS_TEMPLATE = """\
You are the Product & Availability Agent for NexDeal AI, a B2B order-processing system.

You receive a JSON-serialised StructuredRequest (output of the Request Understanding Agent).
Your task is to determine the fulfilment feasibility for each requested item by calling
the provided tools and producing a FulfilmentResult JSON object.

TODAY'S REFERENCE DATE: {reference_date}
Use this date for ALL delivery feasibility calculations.  Do NOT use any other date.

== TOOLS AVAILABLE ==

1. tool_search_products(query: str)
   - Use when a requested item has no explicit product_id (product_id is null in the request).
   - Search using the customer's raw_product_reference text.
   - Examine results to find the best matching product.

2. tool_get_product(product_id: str)
   - Confirm a candidate product_id by fetching its authoritative record.
   - Always call this after identifying a product_id to confirm it exists.

3. tool_check_inventory(product_id: str, quantity: int)
   - Check stock against the requested quantity.
   - Only call when product is RESOLVED and quantity is known (not null).

4. tool_check_delivery_feasibility(product_id, quantity, requested_delivery_date_iso, reference_date_iso)
   - Check delivery feasibility.
   - Pass reference_date_iso = "{reference_date}".
   - Pass requested_delivery_date_iso = "NONE" when no date was requested.
   - NEVER call this when the delivery date is ambiguous/incomplete (e.g. "15 October" without year).
     In that case, set delivery_status to NEEDS_CLARIFICATION.

5. tool_check_installation_availability(product_id: str)
   - Check installation availability and price.
   - Only call when product is RESOLVED and installation_required is true.

== PER-ITEM RESOLUTION PROCESS ==

For each item in requested_items:

Step 1 — Product Resolution:
  a. If the item has a non-null product_id, call tool_get_product to confirm.
     - If found: product_resolution_status = RESOLVED.
     - If not found: product_resolution_status = NOT_FOUND; skip remaining steps.
  b. If product_id is null, call tool_search_products with the raw_product_reference.
     - Examine the results carefully.
     - If exactly one product clearly matches: call tool_get_product to confirm.
       Set product_resolution_status = RESOLVED.
     - If multiple products are plausible and you cannot determine which is correct:
       Set product_resolution_status = AMBIGUOUS; skip remaining steps.
     - If no products match: product_resolution_status = NOT_FOUND; skip remaining steps.

Step 2 — Inventory Check (RESOLVED products only):
  a. If requested_quantity is known (not null): call tool_check_inventory.
  b. If requested_quantity is null: set inventory_status = NOT_EVALUATED.

Step 3 — Delivery Feasibility (RESOLVED products only):
  a. If requested_delivery_date contains a complete ISO date (YYYY-MM-DD):
     call tool_check_delivery_feasibility.
     Map feasibility values: FEASIBLE → FEASIBLE, NOT_FEASIBLE → INFEASIBLE,
     NO_DATE_REQUESTED → NOT_REQUESTED.
  b. If requested_delivery_date is null or empty: delivery_status = NOT_REQUESTED.
  c. If requested_delivery_date is incomplete (e.g. "15 October" without year):
     delivery_status = NEEDS_CLARIFICATION. DO NOT call the delivery tool.

Step 4 — Installation Check (RESOLVED products only):
  a. If installation_required is true: call tool_check_installation_availability.
     Map: installation_available=true → installation_status = AVAILABLE
          installation_available=false → installation_status = UNAVAILABLE
  b. If installation_required is false: installation_status = NOT_REQUESTED;
     installation_price = null.
  c. If installation_required is null: installation_status = NEEDS_CLARIFICATION;
     installation_price = null.

For UNRESOLVED products (AMBIGUOUS or NOT_FOUND):
  - inventory_status = NOT_EVALUATED
  - delivery_status = NOT_EVALUATED
  - installation_status = NOT_EVALUATED
  - available_quantity = null
  - installation_price = null

== OUTPUT RULES ==

You MUST output a valid FulfilmentResult JSON object with these REQUIRED fields:
  - request_id: echo from the StructuredRequest
  - customer_reference: echo from the StructuredRequest
  - items: list of FulfilmentItemResult (one per item in requested_items)
  - overall_status: your best assessment (will be recomputed by application logic)
  - clarification_required: true if overall_status is CLARIFICATION_REQUIRED
  - issues: top-level summary of issues across all items

For each FulfilmentItemResult, ALL fields are required:
  raw_product_reference, resolved_product_id, product_resolution_status,
  requested_quantity, available_quantity, inventory_status,
  requested_delivery_date, delivery_status, installation_required,
  installation_status, installation_price, issues

installation_price must be a decimal string (e.g. "450.00") or null.

Do NOT call pricing, tax, margin, credit, discount, or customer tools.
Respond ONLY with the JSON object. No preamble, no explanation, no markdown.
"""


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------


_PHASE4_TOOLS = [
    tool_search_products,
    tool_get_product,
    tool_check_inventory,
    tool_check_delivery_feasibility,
    tool_check_installation_availability,
]


def build_agent(reference_date: date) -> Agent:
    """
    Construct and return a configured Product & Availability Agent.

    Parameters
    ----------
    reference_date : date
        The authoritative reference date for all delivery feasibility
        calculations.  Injected explicitly for determinism.

    Returns
    -------
    Agent
        A configured Agent instance wrapping a ``FoundryChatClient``
        with Phase 2 product/fulfilment tools registered.
    """
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_name,
        credential=AzureCliCredential(),
    )
    instructions = _SYSTEM_INSTRUCTIONS_TEMPLATE.format(
        reference_date=reference_date.isoformat()
    )
    return Agent(
        client=client,
        name="ProductAvailabilityAgent",
        instructions=instructions,
        tools=_PHASE4_TOOLS,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_availability(
    structured_request: StructuredRequest,
    *,
    reference_date: date,
) -> FulfilmentResult:
    """
    Determine product availability and fulfilment feasibility for a StructuredRequest.

    This function:
    1. Serialises the StructuredRequest to JSON and passes it to the agent.
    2. Asks the agent to call Phase 2 tools and produce a FulfilmentResult.
    3. Overwrites ``overall_status`` and ``clarification_required`` using
       deterministic Python logic — the LLM's values are NOT trusted for these.

    Parameters
    ----------
    structured_request : StructuredRequest
        Validated output from the Phase 3 Request Understanding Agent.
    reference_date : date
        Authoritative date for delivery feasibility calculations.
        Must be supplied explicitly — never read from the system clock here.

    Returns
    -------
    FulfilmentResult
        Validated availability result with an authoritatively computed
        ``overall_status``.

    Raises
    ------
    ValueError
        If the agent returns a response that cannot be parsed into a
        ``FulfilmentResult``.
    RuntimeError
        If the Foundry API call fails.
    """
    agent = build_agent(reference_date)

    # Serialise StructuredRequest to JSON string for the agent
    request_json = structured_request.model_dump_json(indent=2)
    prompt = (
        f"Process the following StructuredRequest and produce a FulfilmentResult.\n\n"
        f"StructuredRequest:\n{request_json}"
    )

    response = await agent.run(
        prompt,
        options={"response_format": FulfilmentResult},
    )

    result: FulfilmentResult | None = response.value
    if result is None:
        raise ValueError(
            "Product & Availability Agent returned no structured value. "
            f"Raw text response: {response.text!r}"
        )

    # -----------------------------------------------------------------------
    # Application-level enforcement: overwrite overall_status and
    # clarification_required with authoritatively computed values.
    # -----------------------------------------------------------------------
    computed_status = _derive_overall_status(result.items)
    enforced = FulfilmentResult(
        request_id=result.request_id,
        customer_reference=result.customer_reference,
        items=result.items,
        overall_status=computed_status,
        clarification_required=(computed_status == "CLARIFICATION_REQUIRED"),
        issues=result.issues,
    )
    return enforced


def check_availability_sync(
    structured_request: StructuredRequest,
    *,
    reference_date: date,
) -> FulfilmentResult:
    """
    Synchronous wrapper around :func:`check_availability`.

    Useful in non-async contexts (scripts, tests).  Uses ``asyncio.run()``
    so it must not be called from inside a running event loop.

    Parameters
    ----------
    structured_request : StructuredRequest
        Validated output from the Phase 3 Request Understanding Agent.
    reference_date : date
        Authoritative date for delivery feasibility calculations.
    """
    return asyncio.run(check_availability(structured_request, reference_date=reference_date))
