"""
app/tools/data_loader.py — NexDeal AI  |  Phase 2

Central, read-only data loader for the three Phase 1 JSON datasets.

Design principles:
  - Repository-relative paths: resolved from this file's location, so
    tests pass regardless of the working directory.
  - Fail fast: missing or malformed files raise DataLoadError immediately.
  - Immutable at runtime: all public accessors return new copies or
    read-only views; the internal cache is never exposed directly.
  - No mutations: this module never writes to the JSON files.
  - No LLMs, no Azure calls, no network activity.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution — anchored to the repo root (two parents up from this file)
# ---------------------------------------------------------------------------
_THIS_FILE = pathlib.Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent.parent   # app/tools/data_loader.py -> repo root
DATA_DIR = _REPO_ROOT / "data"


class DataLoadError(Exception):
    """Raised when a required data file cannot be found or parsed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: pathlib.Path) -> Any:
    """Read *path* and return the parsed JSON value, or raise DataLoadError."""
    if not path.exists():
        raise DataLoadError(
            f"Required data file not found: {path}\n"
            "Ensure the Phase 1 data files are present at data/*.json"
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataLoadError(
            f"Failed to parse JSON from {path}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Module-level cache — loaded once on first import, never mutated.
# ---------------------------------------------------------------------------
_products_raw: list[dict] | None = None
_customers_raw: list[dict] | None = None
_business_rules_raw: dict | None = None

# Index caches for O(1) lookups
_products_index: dict[str, dict] | None = None
_customers_index: dict[str, dict] | None = None


def _ensure_loaded() -> None:
    """Lazily load all three data files into module-level cache."""
    global _products_raw, _customers_raw, _business_rules_raw
    global _products_index, _customers_index

    if _products_raw is None:
        raw = _load_json(DATA_DIR / "products.json")
        if not isinstance(raw, list):
            raise DataLoadError("products.json must be a JSON array at the top level.")
        _products_raw = raw
        _products_index = {p["product_id"]: p for p in raw}

    if _customers_raw is None:
        raw = _load_json(DATA_DIR / "customers.json")
        if not isinstance(raw, list):
            raise DataLoadError("customers.json must be a JSON array at the top level.")
        _customers_raw = raw
        _customers_index = {c["customer_id"]: c for c in raw}

    if _business_rules_raw is None:
        raw = _load_json(DATA_DIR / "business_rules.json")
        if not isinstance(raw, dict):
            raise DataLoadError("business_rules.json must be a JSON object at the top level.")
        _business_rules_raw = raw


# ---------------------------------------------------------------------------
# Public accessors — return copies so callers cannot mutate the cache
# ---------------------------------------------------------------------------

def get_all_products() -> list[dict]:
    """Return a copy of the full products list."""
    _ensure_loaded()
    return list(_products_raw)  # type: ignore[arg-type]


def get_product_by_id(product_id: str) -> dict | None:
    """Return the product dict for *product_id*, or None if not found."""
    _ensure_loaded()
    record = _products_index.get(product_id)  # type: ignore[union-attr]
    return dict(record) if record is not None else None


def get_all_customers() -> list[dict]:
    """Return a copy of the full customers list."""
    _ensure_loaded()
    return list(_customers_raw)  # type: ignore[arg-type]


def get_customer_by_id(customer_id: str) -> dict | None:
    """Return the customer dict for *customer_id*, or None if not found."""
    _ensure_loaded()
    record = _customers_index.get(customer_id)  # type: ignore[union-attr]
    return dict(record) if record is not None else None


def get_business_rules() -> dict:
    """Return a shallow copy of the business rules object."""
    _ensure_loaded()
    return dict(_business_rules_raw)  # type: ignore[arg-type]


def get_discount_policy() -> dict:
    """Return the discount_policy section from business_rules.json."""
    return get_business_rules()["discount_policy"]


def get_margin_policy() -> dict:
    """Return the margin_policy section from business_rules.json."""
    return get_business_rules()["margin_policy"]


def get_approval_policy() -> dict:
    """Return the approval_policy section from business_rules.json."""
    return get_business_rules()["approval_policy"]


def get_delivery_policy() -> dict:
    """Return the delivery_policy section from business_rules.json."""
    return get_business_rules()["delivery_policy"]


def get_installation_policy() -> dict:
    """Return the installation_policy section from business_rules.json."""
    return get_business_rules()["installation_policy"]


def get_customer_tier_policy() -> dict:
    """Return the customer_tier_policy section from business_rules.json."""
    return get_business_rules()["customer_tier_policy"]


def get_credit_policy() -> dict:
    """Return the credit_policy section from business_rules.json."""
    return get_business_rules()["credit_policy"]


def get_tax_policy() -> dict:
    """Return the tax_policy section from business_rules.json."""
    return get_business_rules()["tax_policy"]

