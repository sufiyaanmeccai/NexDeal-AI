"""
app/tools/fulfilment.py — NexDeal AI  |  Phase 2

Read-only fulfilment feasibility tools: delivery date checking and
installation availability/pricing.

Delivery date logic uses business_rules.json delivery_policy exclusively.
All calculations are deterministic; no random values or runtime timestamps.
No LLMs, no Azure calls, no mutations.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from app.tools.data_loader import get_delivery_policy, get_product_by_id
from app.tools.products import ProductNotFoundError


class DeliveryFeasibility(str, Enum):
    """Outcome of a delivery date feasibility check."""
    FEASIBLE = "FEASIBLE"             # Order can be delivered by the requested date
    NOT_FEASIBLE = "NOT_FEASIBLE"     # Earliest delivery is after the requested date
    NO_DATE_REQUESTED = "NO_DATE_REQUESTED"  # No deadline given; earliest date returned


def _resolve_product(product_id: str) -> dict:
    """Validate product_id and return the product record or raise."""
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string.")
    record = get_product_by_id(product_id.strip())
    if record is None:
        raise ProductNotFoundError(
            f"Product '{product_id}' not found; cannot determine fulfilment details."
        )
    return record


def check_delivery_feasibility(
    product_id: str,
    quantity: int,
    requested_delivery_date: date | None,
    reference_date: date,
) -> dict:
    """
    Determine whether a product can be delivered by the requested date.

    Delivery estimate formula (from delivery_policy):
        earliest_ready = reference_date
                         + product.lead_time_days
                         + delivery_policy.standard_lead_time_buffer_days

    The region transit time is NOT added here because the customer region
    is not known at this call site. The tool returns the earliest dispatch-
    ready date; the calling layer (or a future agent) can add transit time.

    Parameters
    ----------
    product_id : str
        Unique product identifier.
    quantity : int
        Requested quantity (>= 1; used only for validation here).
    requested_delivery_date : date or None
        The customer's desired delivery date. Pass None if no date specified.
    reference_date : date
        The order/calculation date. Must be explicit for determinism.

    Returns
    -------
    dict with keys:
        product_id                  str
        reference_date              str  — ISO 8601 (YYYY-MM-DD)
        product_lead_time_days      int
        buffer_days                 int  — from delivery_policy
        earliest_dispatch_ready     str  — ISO date when product is ready to ship
        requested_delivery_date     str | None
        feasibility                 DeliveryFeasibility
        days_to_deadline            int | None  — None when no date requested
        days_ahead_or_behind        int | None  — positive = ahead, negative = behind

    Raises
    ------
    ValueError
        If quantity <= 0 or product_id is blank.
    ProductNotFoundError
        If the product is not in the catalogue.
    TypeError
        If reference_date is not a date instance, or quantity is not int.
    """
    if not isinstance(reference_date, date):
        raise TypeError(
            f"reference_date must be a datetime.date instance, "
            f"got {type(reference_date).__name__!r}"
        )
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise TypeError(f"quantity must be an int, got {type(quantity).__name__!r}")
    if quantity <= 0:
        raise ValueError(f"quantity must be >= 1, got {quantity}")

    product = _resolve_product(product_id)
    policy = get_delivery_policy()
    buffer = policy["standard_lead_time_buffer_days"]
    lead = product["lead_time_days"]

    earliest_ready = reference_date + timedelta(days=lead + buffer)

    if requested_delivery_date is None:
        return {
            "product_id": product["product_id"],
            "reference_date": reference_date.isoformat(),
            "product_lead_time_days": lead,
            "buffer_days": buffer,
            "earliest_dispatch_ready": earliest_ready.isoformat(),
            "requested_delivery_date": None,
            "feasibility": DeliveryFeasibility.NO_DATE_REQUESTED,
            "days_to_deadline": None,
            "days_ahead_or_behind": None,
        }

    if not isinstance(requested_delivery_date, date):
        raise TypeError(
            f"requested_delivery_date must be a datetime.date or None, "
            f"got {type(requested_delivery_date).__name__!r}"
        )

    days_to_deadline = (requested_delivery_date - reference_date).days
    days_ahead_or_behind = (requested_delivery_date - earliest_ready).days
    feasibility = (
        DeliveryFeasibility.FEASIBLE
        if earliest_ready <= requested_delivery_date
        else DeliveryFeasibility.NOT_FEASIBLE
    )

    return {
        "product_id": product["product_id"],
        "reference_date": reference_date.isoformat(),
        "product_lead_time_days": lead,
        "buffer_days": buffer,
        "earliest_dispatch_ready": earliest_ready.isoformat(),
        "requested_delivery_date": requested_delivery_date.isoformat(),
        "feasibility": feasibility,
        "days_to_deadline": days_to_deadline,
        "days_ahead_or_behind": days_ahead_or_behind,
    }


def check_installation_availability(product_id: str) -> dict:
    """
    Return whether installation is available for *product_id*.

    Parameters
    ----------
    product_id : str
        Unique product identifier.

    Returns
    -------
    dict with keys:
        product_id              str
        installation_available  bool  — directly from products.json
        installation_price      Decimal — 0 if not available

    Raises
    ------
    ProductNotFoundError
    """
    product = _resolve_product(product_id)
    return {
        "product_id": product["product_id"],
        "installation_available": product["installation_available"],
        "installation_price": Decimal(str(product["installation_price"])),
    }


def get_installation_price(product_id: str) -> Decimal:
    """
    Return the authoritative installation price for *product_id*.

    Parameters
    ----------
    product_id : str
        Unique product identifier.

    Returns
    -------
    Decimal
        Installation price in the product's currency (USD).
        Returns Decimal("0") if installation is not available.

    Raises
    ------
    ProductNotFoundError
    """
    product = _resolve_product(product_id)
    return Decimal(str(product["installation_price"]))
