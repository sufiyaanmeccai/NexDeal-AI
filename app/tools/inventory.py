"""
app/tools/inventory.py — NexDeal AI  |  Phase 2

Read-only inventory availability tools.

All data originates exclusively from data/products.json via data_loader.
Inventory is NEVER mutated — this is a read-only check tool.
No LLMs, no Azure calls.
"""

from __future__ import annotations

from enum import Enum

from app.tools.data_loader import get_product_by_id
from app.tools.products import ProductNotFoundError


class InventoryStatus(str, Enum):
    """Controlled vocabulary for inventory availability outcomes."""
    AVAILABLE = "AVAILABLE"       # Requested quantity fully in stock
    PARTIAL = "PARTIAL"           # Some stock exists but less than requested
    UNAVAILABLE = "UNAVAILABLE"   # Zero units in stock


def check_inventory(product_id: str, quantity: int) -> dict:
    """
    Compare the requested *quantity* against authoritative stock levels.

    This is a read-only check. It does NOT reserve, decrement, or alter
    the inventory in any way.

    Parameters
    ----------
    product_id : str
        Unique product identifier (e.g. "PRD-001").
    quantity : int
        Number of units requested. Must be >= 1.

    Returns
    -------
    dict with keys:
        product_id          str             — echoed for traceability
        requested_quantity  int             — the quantity that was checked
        stock_on_hand       int             — current inventory from JSON
        status              InventoryStatus — AVAILABLE | PARTIAL | UNAVAILABLE
        available_quantity  int             — min(requested_quantity, stock_on_hand)
        shortfall           int             — units short (0 if AVAILABLE)

    Raises
    ------
    ValueError
        If *quantity* <= 0.
    ProductNotFoundError
        If the product does not exist in the catalogue.
    TypeError
        If *quantity* is not an integer.
    """
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise TypeError(f"quantity must be an int, got {type(quantity).__name__!r}")
    if quantity <= 0:
        raise ValueError(
            f"quantity must be >= 1 (received {quantity}). "
            "Specify the number of units the customer wants to order."
        )
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string.")

    record = get_product_by_id(product_id.strip())
    if record is None:
        raise ProductNotFoundError(
            f"Product '{product_id}' not found; cannot check inventory."
        )

    stock = record["inventory"]

    if stock >= quantity:
        status = InventoryStatus.AVAILABLE
        available_qty = quantity
        shortfall = 0
    elif stock > 0:
        status = InventoryStatus.PARTIAL
        available_qty = stock
        shortfall = quantity - stock
    else:
        status = InventoryStatus.UNAVAILABLE
        available_qty = 0
        shortfall = quantity

    return {
        "product_id": record["product_id"],
        "requested_quantity": quantity,
        "stock_on_hand": stock,
        "status": status,
        "available_quantity": available_qty,
        "shortfall": shortfall,
    }
