"""
app/tools/pricing.py — NexDeal AI  |  Phase 2

Deterministic pricing calculation tools using decimal.Decimal for all
monetary arithmetic to eliminate floating-point precision errors.

All unit prices originate from data/products.json.
All discount rules originate from data/business_rules.json.
No LLMs, no Azure calls, no mutations.

Rounding convention: ROUND_HALF_UP to 2 decimal places for all monetary
outputs (standard commercial rounding).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.tools.data_loader import (
    get_discount_policy,
    get_product_by_id,
    get_tax_policy,
)
from app.tools.customers import get_customer_pricing_tier, CustomerNotFoundError
from app.tools.products import ProductNotFoundError

# Precision sentinel used with quantize()
_CENT = Decimal("0.01")


def _to_decimal(value: int | float | str | Decimal, name: str = "value") -> Decimal:
    """Convert *value* to Decimal, raising TypeError on unsupported types."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception as exc:
            raise ValueError(f"{name} cannot be converted to Decimal: {value!r}") from exc
    raise TypeError(f"{name} must be numeric or Decimal, got {type(value).__name__!r}")


def _round_money(amount: Decimal) -> Decimal:
    """Round *amount* to 2 dp using ROUND_HALF_UP (commercial rounding)."""
    return amount.quantize(_CENT, rounding=ROUND_HALF_UP)


def _get_product_unit_price(product_id: str) -> Decimal:
    """Fetch and return the unit_price for *product_id* as a Decimal."""
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string.")
    record = get_product_by_id(product_id.strip())
    if record is None:
        raise ProductNotFoundError(
            f"Product '{product_id}' not found; cannot calculate price."
        )
    return Decimal(str(record["unit_price"]))


# ---------------------------------------------------------------------------
# Public pricing functions
# ---------------------------------------------------------------------------

def calculate_subtotal(product_id: str, quantity: int) -> Decimal:
    """
    Calculate the gross line subtotal: unit_price × quantity.

    Parameters
    ----------
    product_id : str
        Unique product identifier.
    quantity : int
        Number of units ordered. Must be >= 1.

    Returns
    -------
    Decimal
        Gross subtotal rounded to 2 decimal places (USD).

    Raises
    ------
    ValueError
        If quantity <= 0.
    ProductNotFoundError
        If product_id is not in the catalogue.
    """
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise TypeError(f"quantity must be an int, got {type(quantity).__name__!r}")
    if quantity <= 0:
        raise ValueError(f"quantity must be >= 1, got {quantity}")

    unit_price = _get_product_unit_price(product_id)
    return _round_money(unit_price * Decimal(quantity))


def calculate_discount(subtotal: Decimal | float, discount_percent: Decimal | float) -> Decimal:
    """
    Calculate the discount amount for a given subtotal and percentage.

    Parameters
    ----------
    subtotal : Decimal | float
        Gross line subtotal. Must be >= 0.
    discount_percent : Decimal | float
        Discount rate as a percentage (e.g. 15 for 15%). Must be 0–100.

    Returns
    -------
    Decimal
        Discount amount (positive) rounded to 2 dp.

    Raises
    ------
    ValueError
        If subtotal < 0 or discount_percent is outside [0, 100].
    """
    sub = _to_decimal(subtotal, "subtotal")
    pct = _to_decimal(discount_percent, "discount_percent")

    if sub < Decimal("0"):
        raise ValueError(f"subtotal must be >= 0, got {sub}")
    if pct < Decimal("0") or pct > Decimal("100"):
        raise ValueError(
            f"discount_percent must be between 0 and 100, got {pct}"
        )

    return _round_money(sub * pct / Decimal("100"))


def calculate_discounted_total(
    subtotal: Decimal | float,
    discount_percent: Decimal | float,
) -> Decimal:
    """
    Return the subtotal after applying the discount.

    Parameters
    ----------
    subtotal : Decimal | float
    discount_percent : Decimal | float

    Returns
    -------
    Decimal
        Net total after discount, rounded to 2 dp.
    """
    sub = _to_decimal(subtotal, "subtotal")
    discount_amount = calculate_discount(sub, discount_percent)
    return _round_money(sub - discount_amount)


def calculate_customer_price(
    product_id: str,
    quantity: int,
    customer_id: str,
) -> dict:
    """
    Apply customer-tier volume discounts to arrive at a net line price.

    Discount logic (from business_rules.json discount_policy):
      1. Determine the customer's tier max discount cap.
      2. Look up the applicable volume discount bracket for the subtotal.
      3. Effective discount = min(customer.discount_limit, tier_cap) + volume_additional.
         Volume additive never pushes the total above the tier cap.
      4. Apply to subtotal.

    Parameters
    ----------
    product_id : str
    quantity : int  — must be >= 1
    customer_id : str

    Returns
    -------
    dict with keys:
        product_id          str
        customer_id         str
        quantity            int
        unit_price          Decimal
        subtotal            Decimal   — gross (before discount)
        customer_tier       str
        tier_discount_cap   Decimal   — max discount % allowed by tier
        customer_discount   Decimal   — customer's own discount_limit %
        volume_discount_additional  Decimal  — extra % from volume bracket
        effective_discount  Decimal   — final applied discount %
        discount_amount     Decimal   — monetary discount
        net_total           Decimal   — subtotal minus discount

    Raises
    ------
    ProductNotFoundError / CustomerNotFoundError / ValueError
    """
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise TypeError(f"quantity must be an int, got {type(quantity).__name__!r}")
    if quantity <= 0:
        raise ValueError(f"quantity must be >= 1, got {quantity}")

    subtotal = calculate_subtotal(product_id, quantity)
    unit_price = _get_product_unit_price(product_id)

    # Customer data
    from app.tools.data_loader import get_customer_by_id
    record = get_customer_by_id(customer_id.strip() if isinstance(customer_id, str) else customer_id)
    if record is None:
        raise CustomerNotFoundError(
            f"Customer '{customer_id}' not found; cannot calculate customer price."
        )

    tier = record["customer_tier"]
    customer_discount_limit = Decimal(str(record["discount_limit"]))

    # Policy from JSON
    policy = get_discount_policy()
    tier_cap = Decimal(str(policy["max_discount_by_tier"][tier]))

    # Volume bracket — match the subtotal
    volume_additional = Decimal("0")
    for bracket in policy["volume_discount_brackets"]:
        min_val = Decimal(str(bracket["min_order_value_usd"]))
        max_val = bracket["max_order_value_usd"]
        max_val_d = Decimal(str(max_val)) if max_val is not None else None
        if subtotal >= min_val and (max_val_d is None or subtotal <= max_val_d):
            volume_additional = Decimal(str(bracket["additional_discount_pct"]))
            break

    # Effective discount: cap at tier_cap
    base = min(customer_discount_limit, tier_cap)
    effective_discount = min(base + volume_additional, tier_cap)

    discount_amount = calculate_discount(subtotal, effective_discount)
    net_total = _round_money(subtotal - discount_amount)

    return {
        "product_id": product_id.strip(),
        "customer_id": customer_id.strip() if isinstance(customer_id, str) else customer_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "subtotal": subtotal,
        "customer_tier": tier,
        "tier_discount_cap": tier_cap,
        "customer_discount": customer_discount_limit,
        "volume_discount_additional": volume_additional,
        "effective_discount": effective_discount,
        "discount_amount": discount_amount,
        "net_total": net_total,
    }


def calculate_tax(
    taxable_amount: Decimal | float,
    applicable_tax_rule: str = "standard",
) -> Decimal:
    """
    Calculate tax on a taxable amount using the authoritative tax policy
    from data/business_rules.json.

    Parameters
    ----------
    taxable_amount : Decimal | float
        The amount to apply tax to. Must be >= 0.
    applicable_tax_rule : str
        The authoritative tax rule identifier (e.g. 'standard', 'reduced', 'zero',
        'exempt', or a valid region name from business_rules.json like 'Europe',
        'North America'). Defaults to 'standard'.

    Returns
    -------
    Decimal
        Tax amount rounded to 2 dp using ROUND_HALF_UP.

    Raises
    ------
    TypeError
        If applicable_tax_rule is numeric (arbitrary caller-supplied rates are
        disallowed to preserve business_rules.json authority).
    ValueError
        If taxable_amount < 0 or applicable_tax_rule is unknown.
    """
    amount = _to_decimal(taxable_amount, "taxable_amount")
    if amount < Decimal("0"):
        raise ValueError(f"taxable_amount must be >= 0, got {amount}")

    if not isinstance(applicable_tax_rule, str) or isinstance(applicable_tax_rule, bool):
        raise TypeError(
            f"applicable_tax_rule must be a string rule name (e.g. 'standard', 'reduced', 'zero', 'exempt'), "
            f"got {type(applicable_tax_rule).__name__!r}. Tax rates are authoritative and must be "
            f"configured in business_rules.json."
        )

    rule_key = applicable_tax_rule.strip()
    if not rule_key:
        raise ValueError("applicable_tax_rule must be a non-empty string.")

    policy = get_tax_policy()
    tax_rules = policy.get("tax_rules", {})
    regional_rates = policy.get("regional_tax_rates", {})

    rate_raw = tax_rules.get(rule_key)
    if rate_raw is None:
        rate_raw = regional_rates.get(rule_key)
    if rate_raw is None:
        # Case-insensitive fallback
        for k, v in {**tax_rules, **regional_rates}.items():
            if k.lower() == rule_key.lower():
                rate_raw = v
                break

    if rate_raw is None:
        valid_rules = sorted(set(list(tax_rules.keys()) + list(regional_rates.keys())))
        raise ValueError(
            f"Unknown tax rule {applicable_tax_rule!r}. "
            f"Must be one of configured tax rules in business_rules.json: {valid_rules}"
        )

    rate = _to_decimal(rate_raw, "tax_rate")
    return _round_money(amount * rate / Decimal("100"))



def calculate_margin(revenue: Decimal | float, cost: Decimal | float) -> dict:
    """
    Calculate margin percentage given revenue and cost.

    Formula: margin_pct = (revenue - cost) / revenue × 100

    Parameters
    ----------
    revenue : Decimal | float
        Selling price (net total after any discounts). Must be > 0.
    cost : Decimal | float
        Cost of goods. Must be >= 0 and <= revenue.

    Returns
    -------
    dict with keys:
        revenue         Decimal
        cost            Decimal
        gross_profit    Decimal — revenue minus cost
        margin_pct      Decimal — gross margin percentage (2 dp)

    Raises
    ------
    ValueError
        If revenue <= 0, cost < 0, or cost > revenue.
    """
    rev = _to_decimal(revenue, "revenue")
    cst = _to_decimal(cost, "cost")

    if rev <= Decimal("0"):
        raise ValueError(f"revenue must be > 0, got {rev}")
    if cst < Decimal("0"):
        raise ValueError(f"cost must be >= 0, got {cst}")
    if cst > rev:
        raise ValueError(
            f"cost ({cst}) cannot exceed revenue ({rev}) — "
            "that would imply a negative margin."
        )

    gross_profit = _round_money(rev - cst)
    margin_pct = _round_money((rev - cst) / rev * Decimal("100"))

    return {
        "revenue": _round_money(rev),
        "cost": _round_money(cst),
        "gross_profit": gross_profit,
        "margin_pct": margin_pct,
    }
