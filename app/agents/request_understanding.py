"""
app/agents/request_understanding.py — NexDeal AI  |  Phase 3

Request Understanding Agent
============================
Transforms a free-text B2B customer request into a validated ``StructuredRequest``
using the Microsoft Agent Framework's ``FoundryChatClient`` and Foundry structured
outputs (strict JSON Schema mode).

Architectural boundaries (Phase 3)
------------------------------------
* This agent ONLY extracts what the customer wrote — it does NOT check inventory,
  calculate prices, check delivery feasibility, apply business rules, or resolve
  product descriptions to canonical product IDs.  Those concerns belong to later
  pipeline stages.
* Authentication: ``DefaultAzureCredential`` (supports both local development and Foundry Hosted Agent runtime).
* Client pattern: ``Agent(client=FoundryChatClient(...))`` — the code-first,
  direct-inference pattern.  Phase 0's ``AIProjectClient`` approach is left
  untouched.
* All Foundry connectivity settings are read from the shared ``app.config.settings``
  singleton that Phase 0 already validates.

Usage example::

    import asyncio
    from app.agents.request_understanding import understand_request

    result = asyncio.run(understand_request(
        "Acme Corp needs 20 enterprise switches. Deliver by 15 Oct. 12% discount."
    ))
    print(result.customer_reference)           # "Acme Corp"
    print(result.requested_items[0].product_id)  # None — descriptive, not canonical
    print(result.requested_discount_percent)    # 12.0
"""

from __future__ import annotations

import asyncio

from azure.identity import DefaultAzureCredential

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from app.config import settings
from app.models.schemas import StructuredRequest


# ---------------------------------------------------------------------------
# System instructions for the Request Understanding Agent
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTIONS = """\
You are the Request Understanding Agent for NexDeal AI, a B2B order-processing system.

Your ONLY job is to read a raw customer request and extract structured information
from it.  You MUST NOT:
  - Resolve product descriptions to catalogue IDs or SKUs.
  - Check inventory, prices, margins, delivery feasibility, or credit limits.
  - Apply any business rules or policies.
  - Calculate discounts, taxes, or totals.
  - Create or modify quotes or orders.
  - Call any Phase 2 business tools.
  - Invent or hallucinate information the customer did not supply.

CRITICAL RULES for product_id:
  - Set product_id ONLY when the customer explicitly supplies a canonical-looking identifier
    (e.g. a part number like "SW-1007", "PROD-42", "PRD-999", "SRV-1001"). You MUST extract that exact identifier into the product_id field.
  - This rule applies EVEN IF the identifier may not exist in the product catalogue. You must NOT test, validate, reject, or null the identifier based on catalogue existence.
  - NEVER infer product_id from purely descriptive product text such as "enterprise 48-port switches"
    or "HP LaserJet toner". In that case, product_id MUST be null.

CRITICAL RULES for requested_items (Extraction Robustness):
  - Do NOT extract the customer name or company name as a requested item. If a phrase consists merely of a proper noun (e.g. "Meridian DataVault.", "Ironclad Defence."), it is the customer_reference, NOT a product.
  - Never invent phantom items from unrecognized proper nouns unless explicit purchase language (e.g., "buy", "purchase", "order") is attached to them.

CRITICAL RULES for quantity:
  - Extract a quantity ONLY if the customer explicitly provides a number.
  - If the customer does NOT explicitly provide a quantity (e.g., "a purchase", "the product"), quantity MUST be null.
  - NEVER assume or infer a default quantity of 1.

CRITICAL RULES for requested_discount_percent:
  - Set this ONLY when the customer explicitly requests a percentage discount
    (e.g. "12% discount", "15 percent off").
  - NEVER convert fixed-amount discounts (e.g. "₹10,000 off", "$500 reduction")
    to a percentage. Return null for fixed amounts.
  - Return null when no discount is mentioned.

CRITICAL RULES for installation_required:
  - true  — customer explicitly requests installation.
  - false — customer explicitly states installation is NOT required.
  - null  — installation is not mentioned.

CRITICAL RULES for specifications:
  - Represent each product specification as a plain string in "key: value" format.
  - Example: ["port_count: 48", "colour: black", "speed: 10GbE"]
  - Use an empty list [] when no specifications are mentioned.
  - Do NOT use a dictionary/object — use a list of strings.

CRITICAL RULES for requested_delivery_date:
  - Normalise to ISO 8601 (YYYY-MM-DD) ONLY when the date is fully explicit and unambiguous,
    INCLUDING an explicitly stated year (e.g. "15 October 2026" -> "2026-10-15").
  - NEVER infer, assume, fabricate, or guess a year when the customer did not explicitly provide one.
  - If the customer specifies only a day and month without a year (e.g. "15 October", "by Oct 15"):
    You MUST NOT output "2024-10-15", "2025-10-15", "2026-10-15" or any other guessed ISO date with an invented year.
    Instead: preserve the exact raw phrasing (e.g. "15 October") or return null for requested_delivery_date,
    AND record an entry in ambiguities or missing_information stating that the delivery year is unspecified.
  - Preserve relative or vague timeframes (e.g. "end of next week", "ASAP") as stated.
  - Return null when delivery date is not mentioned.

For all other nullable fields: return null when the customer did not provide
that information.  For other collection fields (requested_items, requested_services,
missing_information, ambiguities): return [] when nothing is present.

ALWAYS preserve the customer's original wording in raw_product_reference and
raw_request — do not paraphrase or normalise.

Populate missing_information with any field or detail that would typically be
needed to fulfil the request but is absent (e.g. "quantity not specified for item 2",
"delivery address not provided").

Populate ambiguities with any conflicting or unclear statements
(e.g. "two different delivery dates mentioned", "product specification is vague").

Respond ONLY with the JSON object conforming to the StructuredRequest schema.
No preamble, no explanation, no markdown code fences.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_agent() -> Agent:
    """
    Construct and return a configured Request Understanding Agent.

    The agent is stateless and can be reused across multiple ``await agent.run()``
    calls, but must not be shared across OS threads or event loops
    (``FoundryChatClient`` constraint).

    Returns
    -------
    Agent
        A configured Agent instance wrapping a ``FoundryChatClient``.
    """
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_name,
        credential=DefaultAzureCredential(),
    )
    return Agent(
        client=client,
        name="RequestUnderstandingAgent",
        instructions=_SYSTEM_INSTRUCTIONS,
    )


async def understand_request(raw_text: str) -> StructuredRequest:
    """
    Parse a raw customer request string into a validated ``StructuredRequest``.

    Parameters
    ----------
    raw_text:
        The unstructured B2B customer request (email, chat message, form input, etc.).

    Returns
    -------
    StructuredRequest
        Validated, structured representation of the request.

    Raises
    ------
    ValueError
        If the agent returns a response that cannot be parsed into a
        ``StructuredRequest``.
    RuntimeError
        If the Foundry API call fails (network error, auth error, etc.).
    """
    agent = build_agent()

    response = await agent.run(
        raw_text,
        options={"response_format": StructuredRequest},
    )

    result = response.value
    if result is None:
        raise ValueError(
            "Request Understanding Agent returned no structured value. "
            f"Raw text response: {response.text!r}"
        )

    return result


def understand_request_sync(raw_text: str) -> StructuredRequest:
    """
    Synchronous wrapper around :func:`understand_request`.

    Useful in non-async contexts (scripts, tests).  Uses ``asyncio.run()``
    so it must not be called from inside a running event loop.
    """
    return asyncio.run(understand_request(raw_text))
