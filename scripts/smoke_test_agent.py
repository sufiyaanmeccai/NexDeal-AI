"""
scripts/smoke_test_agent.py — NexDeal AI  |  Phase 3

Live integration smoke test for the Request Understanding Agent.

Usage
-----
    python scripts/smoke_test_agent.py

Prerequisites
-------------
  1. .env must be populated with FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_NAME.
  2. Azure CLI must be authenticated (az login).
  3. agent-framework-foundry must be installed (pip install -r requirements.txt).

What this script does
---------------------
  1. Validates configuration and imports.
  2. Sends a single representative B2B request to the Request Understanding Agent.
  3. Verifies the returned StructuredRequest uses the canonical NexDeal schema.
  4. Runs specific field-level assertions (customer reference, item count, quantity,
     product_id null, installation flag, delivery date, discount percent).
  5. Prints a detailed PASS / FAIL report.

This script intentionally does NOT exercise Phase 2 business tools —
it tests Phase 3 in isolation.  Only ONE live model call is made.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys

# Ensure the project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Representative B2B request — deliberately tests all key contract points
# ---------------------------------------------------------------------------
#
# This request is designed to exercise:
#   - customer_reference extraction     ("Acme Manufacturing")
#   - requested_items (one item)
#   - quantity extraction               (20)
#   - product_id must be NULL           ("enterprise 48-port network switches"
#                                        is descriptive, not a canonical ID)
#   - installation_required = True      ("Installation included")
#   - requested_delivery_date           ("15 October")
#   - requested_discount_percent = 12   ("12% discount")
#   - requested_services                ("installation" or similar)

SAMPLE_REQUEST = (
    "Acme Manufacturing needs 20 enterprise 48-port network switches. "
    "Installation included. Please deliver by 15 October. "
    "We would also like a 12% discount."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main smoke test coroutine
# ---------------------------------------------------------------------------


async def run_smoke_test() -> bool:
    _section("NexDeal AI — Phase 3 Request Understanding Smoke Test")

    # ------------------------------------------------------------------
    # Step 1 — configuration
    # ------------------------------------------------------------------
    try:
        from app.config import settings
    except Exception as exc:
        _fail(f"Configuration error: {exc}")
        return False

    _ok(f"FOUNDRY_PROJECT_ENDPOINT : {settings.foundry_project_endpoint}")
    _ok(f"FOUNDRY_MODEL_NAME       : {settings.foundry_model_name}")

    # ------------------------------------------------------------------
    # Step 2 — imports
    # ------------------------------------------------------------------
    try:
        from app.agents.request_understanding import understand_request
        from app.models.schemas import StructuredRequest, RequestedItem
    except ImportError as exc:
        _fail(f"Import error: {exc}\n       Run: pip install -r requirements.txt")
        return False

    _ok("Imports succeeded (agent_framework, pydantic, app modules)")

    # ------------------------------------------------------------------
    # Step 3 — print the request
    # ------------------------------------------------------------------
    print(f"\n--- Request sent to agent ---")
    print(SAMPLE_REQUEST)
    print("-----------------------------")

    # ------------------------------------------------------------------
    # Step 4 — ONE live call to the agent
    # ------------------------------------------------------------------
    print("\n[..] Calling Request Understanding Agent (one live API call) ...")
    try:
        result: StructuredRequest = await understand_request(SAMPLE_REQUEST)
    except Exception as exc:
        _fail(
            f"Agent call failed: {type(exc).__name__}: {exc}\n"
            "       Ensure 'az login' is active and the endpoint is reachable."
        )
        return False

    # ------------------------------------------------------------------
    # Step 5 — verify response.value is a StructuredRequest
    # ------------------------------------------------------------------
    if not isinstance(result, StructuredRequest):
        _fail(
            f"response.value is not a StructuredRequest — got {type(result).__name__}"
        )
        return False
    _ok(f"response.value is a StructuredRequest instance")

    # ------------------------------------------------------------------
    # Step 6 — print the full structured result
    # ------------------------------------------------------------------
    print("\n--- StructuredRequest (canonical NexDeal schema) ---")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    print("-----------------------------------------------------")

    # ------------------------------------------------------------------
    # Step 7 — field-level assertions against the canonical schema
    # ------------------------------------------------------------------
    passed = True

    # 7a — no legacy fields on the result object
    for legacy_field in ("customer_name", "delivery_address", "urgency",
                         "raw_notes", "items"):
        if hasattr(result, legacy_field):
            _fail(f"Legacy field '{legacy_field}' found on StructuredRequest")
            passed = False

    if passed:
        _ok("No legacy fields on StructuredRequest (customer_name, delivery_address, etc.)")

    # 7b — customer_reference populated
    if result.customer_reference and "acme" in result.customer_reference.lower():
        _ok(f"customer_reference: {result.customer_reference!r}")
    else:
        _fail(
            f"customer_reference check failed — expected 'Acme Manufacturing', "
            f"got: {result.customer_reference!r}"
        )
        passed = False

    # 7c — requested_items has exactly one entry
    if len(result.requested_items) == 1:
        _ok(f"requested_items count: {len(result.requested_items)}")
    else:
        _fail(f"requested_items count: expected 1, got {len(result.requested_items)}")
        passed = False

    if result.requested_items:
        item = result.requested_items[0]

        # 7d — raw_product_reference preserved (descriptive text)
        if item.raw_product_reference:
            _ok(f"raw_product_reference: {item.raw_product_reference!r}")
        else:
            _fail("raw_product_reference is empty/null")
            passed = False

        # 7e — product_id must be NULL (descriptive reference, not canonical ID)
        if item.product_id is None:
            _ok("product_id is null (correct — descriptive reference, not a canonical ID)")
        else:
            _fail(
                f"product_id should be null for a descriptive reference, "
                f"got: {item.product_id!r}"
            )
            passed = False

        # 7f — quantity = 20
        if item.quantity == 20:
            _ok(f"quantity: {item.quantity}")
        else:
            _fail(f"quantity: expected 20, got {item.quantity!r}")
            passed = False

    # 7g — installation_required = True
    if result.installation_required is True:
        _ok(f"installation_required: {result.installation_required}")
    else:
        _fail(
            f"installation_required: expected True (customer said 'Installation included'), "
            f"got {result.installation_required!r}"
        )
        passed = False

    # 7h — requested_delivery_date: customer specified '15 October' (no year)
    # The agent MUST NOT invent a year (e.g. '2024-10-15', '2025-10-15', '2026-10-15').
    # Acceptable: raw/partial date phrasing (e.g. '15 October') OR null with ambiguity/missing note.
    date_val = result.requested_delivery_date
    if date_val is not None:
        if re.search(r"\b20\d\d\b", date_val):
            _fail(
                f"requested_delivery_date contains a fabricated year: {date_val!r}. "
                f"Customer said '15 October' with no year specified — the agent must NOT guess a year."
            )
            passed = False
        else:
            _ok(f"requested_delivery_date: {date_val!r} (correct — no fabricated year)")
    else:
        # If null, check that missing year was recorded in missing_information or ambiguities
        all_notes = " ".join(result.missing_information + result.ambiguities).lower()
        if any(w in all_notes for w in ("year", "date", "delivery")):
            _ok("requested_delivery_date: null with explanatory note in missing_information/ambiguities (correct)")
        else:
            _fail(
                "requested_delivery_date is null but no explanation found in missing_information or ambiguities"
            )
            passed = False

    # 7i — requested_discount_percent = 12
    if result.requested_discount_percent == 12.0 or result.requested_discount_percent == 12:
        _ok(f"requested_discount_percent: {result.requested_discount_percent}")
    else:
        _fail(
            f"requested_discount_percent: expected 12, "
            f"got {result.requested_discount_percent!r}"
        )
        passed = False

    # 7j — no pricing/business fields exist on the result
    for business_field in ("price", "total", "tax", "margin", "inventory",
                           "approved_discount", "net_total"):
        if hasattr(result, business_field):
            _fail(f"Business field '{business_field}' found on StructuredRequest — boundary violation")
            passed = False

    if passed:
        _ok("No pricing/inventory/business fields on StructuredRequest")

    # ------------------------------------------------------------------
    # Step 8 — verdict
    # ------------------------------------------------------------------
    if passed:
        _section("RESULT: PASS — Phase 3 Request Understanding Agent verified.")
        _ok("StructuredRequest uses the exact canonical NexDeal schema.")
    else:
        _section("RESULT: FAIL — see [FAIL] messages above.")

    return passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    success = asyncio.run(run_smoke_test())
    sys.exit(0 if success else 1)
