"""
scripts/smoke_test_product_availability.py — NexDeal AI  |  Phase 4

Live smoke test for the Product & Availability Agent.

This script:
  1. Builds a StructuredRequest manually (simulating Phase 3 output).
  2. Calls check_availability_sync() with an explicit reference_date.
  3. Asserts the FulfilmentResult structure and overall_status.
  4. Prints a detailed, human-readable report.

Requirements
-----------
  - Azure CLI authentication must be valid (az login completed).
  - FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_NAME in .env must be set.
  - All Phase 2 data files must be present (data/products.json, etc.).

Usage
-----
    .venv\\Scripts\\python scripts\\smoke_test_product_availability.py
"""

from __future__ import annotations

import sys
from datetime import date

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run directly
# ---------------------------------------------------------------------------
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from app.agents.product_availability import check_availability_sync
from app.models.schemas import (
    FulfilmentItemResult,
    FulfilmentResult,
    RequestedItem,
    StructuredRequest,
)

# ---------------------------------------------------------------------------
# Test inputs
# ---------------------------------------------------------------------------

# Scenario: Acme Corp requests:
#   1. 20 enterprise 48-port network switches (descriptive — no product_id)
#   2. 3 units of PRD-001 (explicit product_id)
# Delivery: 2027-03-01 (explicit, full ISO date)
# Installation: requested
# Discount: 12%

_TEST_REQUEST = StructuredRequest(
    request_id=None,
    raw_request=(
        "Acme Manufacturing needs 20 enterprise 48-port network switches "
        "and 3 units of PRD-001. Installation included. "
        "Please deliver by 1 March 2027. We would also like a 12% discount."
    ),
    customer_reference="Acme Manufacturing",
    requested_items=[
        RequestedItem(
            raw_product_reference="enterprise 48-port network switches",
            product_id=None,
            quantity=20,
            specifications=["port_count: 48"],
        ),
        RequestedItem(
            raw_product_reference="PRD-001",
            product_id="PRD-001",
            quantity=3,
            specifications=[],
        ),
    ],
    requested_delivery_date="2027-03-01",
    installation_required=True,
    requested_services=[],
    requested_discount_percent=12.0,
    missing_information=[],
    ambiguities=[],
)

# Explicit reference date — must NOT use date.today() in the test itself,
# but can be provided as a known value for reproducibility.
_REFERENCE_DATE = date(2026, 9, 22)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


def _colour(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def _check(label: str, condition: bool, detail: str = "") -> bool:
    status = _colour("PASS", GREEN) if condition else _colour("FAIL", RED)
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


def _print_item(item: FulfilmentItemResult, idx: int) -> None:
    print(f"\n  {_colour(f'Item {idx + 1}', BOLD)}: {item.raw_product_reference!r}")
    print(f"    resolved_product_id    : {item.resolved_product_id}")
    print(f"    product_resolution     : {_colour(item.product_resolution_status, CYAN)}")
    print(f"    requested_quantity     : {item.requested_quantity}")
    print(f"    available_quantity     : {item.available_quantity}")
    print(f"    inventory_status       : {_colour(item.inventory_status, CYAN)}")
    print(f"    requested_delivery_date: {item.requested_delivery_date}")
    print(f"    delivery_status        : {_colour(item.delivery_status, CYAN)}")
    print(f"    installation_required  : {item.installation_required}")
    print(f"    installation_status    : {_colour(item.installation_status, CYAN)}")
    print(f"    installation_price     : {item.installation_price}")
    if item.issues:
        for issue in item.issues:
            print(f"    {_colour('ISSUE', YELLOW)}: {issue}")


# ---------------------------------------------------------------------------
# Main smoke test
# ---------------------------------------------------------------------------


def main() -> None:
    print(_colour("=" * 70, BOLD))
    print(_colour("  NexDeal AI — Phase 4 Product & Availability Agent Smoke Test", BOLD))
    print(_colour("=" * 70, BOLD))
    print(f"\nReference date  : {_REFERENCE_DATE.isoformat()}")
    print(f"Customer        : {_TEST_REQUEST.customer_reference}")
    print(f"Items requested : {len(_TEST_REQUEST.requested_items)}")
    print(f"Delivery date   : {_TEST_REQUEST.requested_delivery_date}")
    print(f"Installation    : {_TEST_REQUEST.installation_required}")
    print(f"Discount        : {_TEST_REQUEST.requested_discount_percent}%")

    print("\n" + _colour("Calling Product & Availability Agent (live Foundry)...", BOLD))
    result = check_availability_sync(_TEST_REQUEST, reference_date=_REFERENCE_DATE)

    print(f"\n{_colour('FulfilmentResult:', BOLD)}")
    print(f"  request_id           : {result.request_id}")
    print(f"  customer_reference   : {result.customer_reference}")
    print(f"  overall_status       : {_colour(result.overall_status, CYAN)}")
    print(f"  clarification_req    : {result.clarification_required}")
    if result.issues:
        print(f"  top-level issues     :")
        for issue in result.issues:
            print(f"    - {issue}")

    print(f"\n{_colour('Per-item results:', BOLD)}")
    for i, item in enumerate(result.items):
        _print_item(item, i)

    # -----------------------------------------------------------------------
    # Assertions
    # -----------------------------------------------------------------------
    print(f"\n{_colour('Assertions:', BOLD)}")
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if not _check(label, condition, detail):
            failures.append(label)

    # Structure
    check("result is FulfilmentResult", isinstance(result, FulfilmentResult))
    check("items list is non-empty", len(result.items) == 2,
          f"got {len(result.items)} items")

    # Echo fields
    check("customer_reference echoed",
          result.customer_reference == "Acme Manufacturing")
    check("request_id is None (not assigned by agent)", result.request_id is None)

    # Overall status must be application-derived, not free-text
    valid_statuses = {
        "READY", "PARTIAL", "UNAVAILABLE",
        "CLARIFICATION_REQUIRED", "DELIVERY_CONFLICT", "INSTALLATION_UNAVAILABLE",
    }
    check("overall_status is a valid Literal value",
          result.overall_status in valid_statuses,
          result.overall_status)

    # clarification_required must match overall_status
    expected_clarification = (result.overall_status == "CLARIFICATION_REQUIRED")
    check("clarification_required matches overall_status",
          result.clarification_required == expected_clarification,
          f"overall={result.overall_status}, flag={result.clarification_required}")

    # Item-level assertions
    for i, item in enumerate(result.items):
        prefix = f"Item {i + 1}"

        check(f"{prefix}: raw_product_reference preserved",
              bool(item.raw_product_reference))

        check(f"{prefix}: product_resolution_status is valid",
              item.product_resolution_status in ("RESOLVED", "AMBIGUOUS", "NOT_FOUND"),
              item.product_resolution_status)

        check(f"{prefix}: inventory_status is valid",
              item.inventory_status in ("AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_EVALUATED"),
              item.inventory_status)

        check(f"{prefix}: delivery_status is valid",
              item.delivery_status in (
                  "FEASIBLE", "INFEASIBLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"
              ),
              item.delivery_status)

        check(f"{prefix}: installation_status is valid",
              item.installation_status in (
                  "AVAILABLE", "UNAVAILABLE", "NOT_REQUESTED", "NEEDS_CLARIFICATION", "NOT_EVALUATED"
              ),
              item.installation_status)

        # If resolved, must have a product ID
        if item.product_resolution_status == "RESOLVED":
            check(f"{prefix}: resolved_product_id set when RESOLVED",
                  item.resolved_product_id is not None)
        else:
            check(f"{prefix}: resolved_product_id null when unresolved",
                  item.resolved_product_id is None)

        # If installation_required=True and RESOLVED, installation_status should not be NOT_EVALUATED
        if item.installation_required is True and item.product_resolution_status == "RESOLVED":
            check(f"{prefix}: installation evaluated when required and resolved",
                  item.installation_status != "NOT_EVALUATED",
                  item.installation_status)

    # Item 2 has explicit PRD-001 — it should be RESOLVED
    item2 = result.items[1]
    check("Item 2 (PRD-001 explicit): RESOLVED",
          item2.product_resolution_status == "RESOLVED",
          item2.product_resolution_status)

    # Installation is globally True — all resolved items must have installation checked
    for i, item in enumerate(result.items):
        if item.product_resolution_status == "RESOLVED":
            check(f"Item {i+1}: installation not NOT_EVALUATED (installation_required=True)",
                  item.installation_status != "NOT_EVALUATED",
                  item.installation_status)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{_colour('=' * 70, BOLD)}")
    if failures:
        print(_colour(f"  SMOKE TEST FAILED — {len(failures)} assertion(s) failed:", RED))
        for f in failures:
            print(_colour(f"    ✗ {f}", RED))
        sys.exit(1)
    else:
        print(_colour(
            f"  SMOKE TEST PASSED — all assertions passed "
            f"(overall_status={result.overall_status})",
            GREEN,
        ))
    print(_colour("=" * 70, BOLD))


if __name__ == "__main__":
    main()
