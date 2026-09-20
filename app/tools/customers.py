"""
app/tools/customers.py — NexDeal AI  |  Phase 2

Read-only customer lookup tools.

All data originates exclusively from data/customers.json via data_loader.
No LLMs, no Azure calls, no mutations.
"""

from __future__ import annotations

from app.tools.data_loader import get_customer_by_id


class CustomerNotFoundError(ValueError):
    """Raised when a customer_id does not exist in the customer database."""


def _fetch(customer_id: str) -> dict:
    """Internal helper — validates input and returns the customer record."""
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("customer_id must be a non-empty string.")
    record = get_customer_by_id(customer_id.strip())
    if record is None:
        raise CustomerNotFoundError(
            f"Customer '{customer_id}' not found in the customer database."
        )
    return record


def get_customer(customer_id: str) -> dict:
    """
    Return the full customer record for *customer_id*.

    Parameters
    ----------
    customer_id : str
        Unique customer identifier (e.g. "CUST-001").

    Returns
    -------
    dict
        Copy of the customer record from customers.json.

    Raises
    ------
    CustomerNotFoundError
        If no customer with that ID exists.
    """
    return _fetch(customer_id)


def get_customer_pricing_tier(customer_id: str) -> str:
    """
    Return the authoritative pricing tier for *customer_id*.

    Returns
    -------
    str
        One of "standard", "premium", "enterprise".

    Raises
    ------
    CustomerNotFoundError
        If the customer does not exist.
    """
    return _fetch(customer_id)["customer_tier"]


def check_customer_account_status(customer_id: str) -> dict:
    """
    Return the current account status and payment history for *customer_id*.

    Returns
    -------
    dict with keys:
        customer_id       str  — echoed back for traceability
        account_status    str  — e.g. "active", "credit_hold", "suspended"
        payment_history   str  — e.g. "good", "risk"
        is_orderable      bool — True only when account_status == "active"

    Raises
    ------
    CustomerNotFoundError
    """
    record = _fetch(customer_id)
    return {
        "customer_id": record["customer_id"],
        "account_status": record["account_status"],
        "payment_history": record["payment_history"],
        "is_orderable": record["account_status"] == "active",
    }


def get_customer_credit_info(customer_id: str) -> dict:
    """
    Return authoritative credit information for *customer_id*.

    Returns
    -------
    dict with keys:
        customer_id       str   — echoed for traceability
        credit_limit      float — authoritative limit from customers.json
        discount_limit    int   — maximum discount percentage allowed
        customer_tier     str   — tier (determines policy cap)
        payment_history   str   — "good" or "risk"
        account_status    str   — current account status

    Raises
    ------
    CustomerNotFoundError
    """
    record = _fetch(customer_id)
    return {
        "customer_id": record["customer_id"],
        "credit_limit": record["credit_limit"],
        "discount_limit": record["discount_limit"],
        "customer_tier": record["customer_tier"],
        "payment_history": record["payment_history"],
        "account_status": record["account_status"],
    }
