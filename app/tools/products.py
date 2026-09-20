"""
app/tools/products.py — NexDeal AI  |  Phase 2

Read-only product lookup and search tools.

All data originates exclusively from data/products.json via data_loader.
No LLMs, no Azure calls, no mutations.
"""

from __future__ import annotations

from app.tools.data_loader import get_all_products, get_product_by_id


class ProductNotFoundError(ValueError):
    """Raised when a product_id does not exist in the catalogue."""


def get_product(product_id: str) -> dict:
    """
    Return the product record for *product_id*.

    Parameters
    ----------
    product_id : str
        The unique product identifier (e.g. "PRD-001").

    Returns
    -------
    dict
        A copy of the product record from products.json.

    Raises
    ------
    ProductNotFoundError
        If no product with the given ID exists.
    """
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string.")

    record = get_product_by_id(product_id.strip())
    if record is None:
        raise ProductNotFoundError(
            f"Product '{product_id}' not found in the catalogue. "
            "Use search_products() to discover available products."
        )
    return record


def search_products(query: str) -> list[dict]:
    """
    Case-insensitive deterministic search across product fields.

    Searches the following fields:
      - product_id
      - product_name
      - category
      - description

    Results are returned in stable order (ascending product_id). An empty
    *query* string returns all products.

    Parameters
    ----------
    query : str
        Search term. Matched as a substring in each searched field.

    Returns
    -------
    list[dict]
        Matching product records, sorted by product_id ascending.

    Raises
    ------
    TypeError
        If *query* is not a string.
    """
    if not isinstance(query, str):
        raise TypeError(f"query must be a str, got {type(query).__name__!r}")

    term = query.strip().lower()
    all_products = get_all_products()

    if not term:
        # Return all products in stable order.
        return sorted(all_products, key=lambda p: p["product_id"])

    results = []
    for product in all_products:
        searchable = " ".join([
            product.get("product_id", ""),
            product.get("product_name", ""),
            product.get("category", ""),
            product.get("description", ""),
        ]).lower()
        if term in searchable:
            results.append(product)

    return sorted(results, key=lambda p: p["product_id"])
