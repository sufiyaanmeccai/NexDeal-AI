"""
app/tools/policies.py — NexDeal AI  |  Phase 2

Deterministic policy evaluation tools.

ALL thresholds are read EXCLUSIVELY from data/business_rules.json via
data_loader. No numeric limits are hardcoded anywhere in this module.
No LLMs, no Azure calls, no mutations.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from app.tools.data_loader import (
    get_approval_policy,
    get_credit_policy,
    get_discount_policy,
    get_margin_policy,
    get_customer_by_id,
)
from app.tools.customers import CustomerNotFoundError


# ---------------------------------------------------------------------------
# Policy outcome enumerations
# ---------------------------------------------------------------------------

class DiscountPolicyOutcome(str, Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    EXCEEDS_LIMIT = "EXCEEDS_LIMIT"


class MarginPolicyOutcome(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    LOW_MARGIN_FLAG = "LOW_MARGIN_FLAG"   # Above absolute min but below category min
    BELOW_MINIMUM = "BELOW_MINIMUM"       # Below absolute minimum — blocks order


class ApprovalPolicyOutcome(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    MANAGER_APPROVAL_REQUIRED = "MANAGER_APPROVAL_REQUIRED"
    DIRECTOR_APPROVAL_REQUIRED = "DIRECTOR_APPROVAL_REQUIRED"
    BOARD_APPROVAL_REQUIRED = "BOARD_APPROVAL_REQUIRED"


class CreditPolicyOutcome(str, Enum):
    CREDIT_OK = "CREDIT_OK"
    CREDIT_LIMIT_EXCEEDED = "CREDIT_LIMIT_EXCEEDED"
    ACCOUNT_RESTRICTED = "ACCOUNT_RESTRICTED"


# ---------------------------------------------------------------------------
# Policy evaluation tools
# ---------------------------------------------------------------------------

def check_discount_policy(customer_id: str, discount_percent: float | Decimal) -> dict:
    """
    Evaluate whether *discount_percent* is within the customer's tier limit.

    Thresholds sourced from business_rules.json discount_policy.max_discount_by_tier.

    Parameters
    ----------
    customer_id : str
    discount_percent : float | Decimal
        The proposed discount, as a percentage (e.g. 15 for 15%).

    Returns
    -------
    dict with keys:
        customer_id         str
        customer_tier       str
        proposed_discount   Decimal
        tier_cap            Decimal  — max allowed by tier from JSON
        customer_limit      Decimal  — this customer's personal discount_limit
        effective_cap       Decimal  — min(tier_cap, customer_limit)
        outcome             DiscountPolicyOutcome
        exceeds_by          Decimal  — 0 if WITHIN_LIMIT, positive if EXCEEDS

    Raises
    ------
    CustomerNotFoundError
    ValueError
        If discount_percent < 0 or > 100.
    """
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("customer_id must be a non-empty string.")

    proposed = Decimal(str(discount_percent))
    if proposed < Decimal("0") or proposed > Decimal("100"):
        raise ValueError(
            f"discount_percent must be 0–100, got {proposed}"
        )

    record = get_customer_by_id(customer_id.strip())
    if record is None:
        raise CustomerNotFoundError(f"Customer '{customer_id}' not found.")

    tier = record["customer_tier"]
    customer_limit = Decimal(str(record["discount_limit"]))

    policy = get_discount_policy()
    tier_cap = Decimal(str(policy["max_discount_by_tier"][tier]))

    # Effective cap is the stricter of the tier-level rule and the customer's own limit
    effective_cap = min(tier_cap, customer_limit)
    exceeds_by = max(Decimal("0"), proposed - effective_cap)
    outcome = (
        DiscountPolicyOutcome.WITHIN_LIMIT
        if proposed <= effective_cap
        else DiscountPolicyOutcome.EXCEEDS_LIMIT
    )

    return {
        "customer_id": customer_id.strip(),
        "customer_tier": tier,
        "proposed_discount": proposed,
        "tier_cap": tier_cap,
        "customer_limit": customer_limit,
        "effective_cap": effective_cap,
        "outcome": outcome,
        "exceeds_by": exceeds_by,
    }


def check_margin_policy(
    margin_percent: float | Decimal,
    product_category: str | None = None,
) -> dict:
    """
    Evaluate whether *margin_percent* is acceptable per the margin policy.

    Three tiers (all thresholds from business_rules.json margin_policy):
      - ACCEPTABLE:       margin_percent >= category_minimum (or absolute_minimum if no category)
      - LOW_MARGIN_FLAG:  absolute_minimum <= margin_percent < category_minimum
      - BELOW_MINIMUM:    margin_percent < absolute_minimum (blocks order)

    Parameters
    ----------
    margin_percent : float | Decimal
        Gross margin as a percentage (e.g. 22.5).
    product_category : str | None
        Product category (e.g. "Servers"). If None, only absolute minimum is applied.

    Returns
    -------
    dict with keys:
        margin_percent          Decimal
        product_category        str | None
        absolute_minimum        Decimal  — from JSON
        category_minimum        Decimal | None
        low_margin_flag_at      Decimal  — from JSON
        outcome                 MarginPolicyOutcome

    Raises
    ------
    ValueError
        If margin_percent is outside a sensible range (< -100 or > 100).
    """
    margin = Decimal(str(margin_percent))
    if margin < Decimal("-100") or margin > Decimal("100"):
        raise ValueError(f"margin_percent must be -100 to 100, got {margin}")

    policy = get_margin_policy()
    abs_min = Decimal(str(policy["absolute_minimum_margin_pct"]))
    flag_at = Decimal(str(policy["low_margin_flag_threshold_pct"]))

    cat_min: Decimal | None = None
    if product_category is not None:
        cat_min_raw = policy["minimum_margin_pct_by_category"].get(product_category)
        if cat_min_raw is not None:
            cat_min = Decimal(str(cat_min_raw))

    effective_min = cat_min if cat_min is not None else abs_min

    if margin < abs_min:
        outcome = MarginPolicyOutcome.BELOW_MINIMUM
    elif margin < effective_min:
        outcome = MarginPolicyOutcome.LOW_MARGIN_FLAG
    else:
        outcome = MarginPolicyOutcome.ACCEPTABLE

    return {
        "margin_percent": margin,
        "product_category": product_category,
        "absolute_minimum": abs_min,
        "category_minimum": cat_min,
        "low_margin_flag_at": flag_at,
        "outcome": outcome,
    }


def check_approval_policy(
    order_value: float | Decimal,
    discount_percent: float | Decimal,
    margin_percent: float | Decimal,
    customer_id: str | None = None,
    product_category: str | None = None,
) -> dict:
    """
    Determine what level of approval is required for an order.

    Approval is escalated if any trigger condition is met. Thresholds
    sourced exclusively from business_rules.json approval_policy.

    Trigger conditions evaluated:
      1. order_value > auto_approve_threshold
      2. discount_percent exceeds customer's effective cap (if customer_id given)
      3. margin below category minimum (LOW_MARGIN_FLAG or BELOW_MINIMUM)

    Parameters
    ----------
    order_value : float | Decimal
        Total order value (net, after discount). Must be >= 0.
    discount_percent : float | Decimal
        Applied discount percentage.
    margin_percent : float | Decimal
        Gross margin percentage.
    customer_id : str | None
        Optional. If provided, discount policy check includes customer limit.
    product_category : str | None
        Optional. Used for category-specific margin check.

    Returns
    -------
    dict with keys:
        order_value             Decimal
        discount_percent        Decimal
        margin_percent          Decimal
        triggers_fired          list[str]   — which policy triggers were hit
        outcome                 ApprovalPolicyOutcome
        auto_approve_threshold  Decimal
        manager_threshold       Decimal
        director_threshold      Decimal
        board_threshold         Decimal

    Raises
    ------
    ValueError
        If order_value < 0.
    """
    order_val = Decimal(str(order_value))
    disc_pct = Decimal(str(discount_percent))
    marg_pct = Decimal(str(margin_percent))

    if order_val < Decimal("0"):
        raise ValueError(f"order_value must be >= 0, got {order_val}")

    policy = get_approval_policy()
    auto_thresh = Decimal(str(policy["auto_approve_threshold_usd"]))
    mgr_thresh = Decimal(str(policy["manager_approval_threshold_usd"]))
    dir_thresh = Decimal(str(policy["director_approval_threshold_usd"]))
    board_thresh = Decimal(str(policy["board_approval_threshold_usd"]))

    triggers: list[str] = []

    # Trigger 1: order value
    if order_val > auto_thresh:
        triggers.append("order_value_exceeds_auto_approve_threshold")

    # Trigger 2: discount policy
    if customer_id is not None:
        disc_result = check_discount_policy(customer_id, disc_pct)
        if disc_result["outcome"] == DiscountPolicyOutcome.EXCEEDS_LIMIT:
            triggers.append("discount_exceeds_tier_limit")
    # Without customer context we cannot evaluate discount trigger.

    # Trigger 3: margin policy
    margin_result = check_margin_policy(marg_pct, product_category)
    if margin_result["outcome"] in (
        MarginPolicyOutcome.LOW_MARGIN_FLAG,
        MarginPolicyOutcome.BELOW_MINIMUM,
    ):
        triggers.append("margin_below_category_minimum")

    # Determine approval level from order value (highest threshold reached)
    if order_val > board_thresh:
        outcome = ApprovalPolicyOutcome.BOARD_APPROVAL_REQUIRED
    elif order_val > dir_thresh:
        outcome = ApprovalPolicyOutcome.DIRECTOR_APPROVAL_REQUIRED
    elif order_val > mgr_thresh:
        outcome = ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED
    elif triggers:
        # Triggered but below manager threshold → manager review is minimum
        outcome = ApprovalPolicyOutcome.MANAGER_APPROVAL_REQUIRED
    else:
        outcome = ApprovalPolicyOutcome.AUTO_APPROVED

    return {
        "order_value": order_val,
        "discount_percent": disc_pct,
        "margin_percent": marg_pct,
        "triggers_fired": triggers,
        "outcome": outcome,
        "auto_approve_threshold": auto_thresh,
        "manager_threshold": mgr_thresh,
        "director_threshold": dir_thresh,
        "board_threshold": board_thresh,
    }


def check_credit_policy(customer_id: str, order_value: float | Decimal) -> dict:
    """
    Evaluate credit eligibility for a given order value.

    Logic (all thresholds from business_rules.json credit_policy):
      - If account_status is in blocked_account_statuses → ACCOUNT_RESTRICTED
      - If order_value > credit_limit → CREDIT_LIMIT_EXCEEDED
      - Otherwise → CREDIT_OK

    Parameters
    ----------
    customer_id : str
    order_value : float | Decimal
        Total order value (must be >= 0).

    Returns
    -------
    dict with keys:
        customer_id         str
        order_value         Decimal
        credit_limit        Decimal  — from customers.json
        account_status      str
        payment_history     str
        outcome             CreditPolicyOutcome
        utilisation_pct     Decimal  — order_value / credit_limit × 100
        warning_threshold   Decimal  — from JSON (credit_utilisation_warning_pct)
        block_threshold     Decimal  — from JSON (credit_utilisation_block_pct)
        utilisation_warning bool     — True if utilisation_pct >= warning_threshold

    Raises
    ------
    CustomerNotFoundError
    ValueError
        If order_value < 0.
    """
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("customer_id must be a non-empty string.")

    order_val = Decimal(str(order_value))
    if order_val < Decimal("0"):
        raise ValueError(f"order_value must be >= 0, got {order_val}")

    record = get_customer_by_id(customer_id.strip())
    if record is None:
        raise CustomerNotFoundError(f"Customer '{customer_id}' not found.")

    credit_policy = get_credit_policy()
    blocked_statuses = set(credit_policy["blocked_account_statuses"])
    valid_statuses = set(credit_policy["valid_account_statuses_for_order"])
    warn_pct = Decimal(str(credit_policy["credit_utilisation_warning_pct"]))
    block_pct = Decimal(str(credit_policy["credit_utilisation_block_pct"]))

    account_status = record["account_status"]
    credit_limit = Decimal(str(record["credit_limit"]))
    utilisation_pct = (order_val / credit_limit * Decimal("100")).quantize(
        Decimal("0.01")
    ) if credit_limit > Decimal("0") else Decimal("0")

    if account_status in blocked_statuses or account_status not in valid_statuses:
        outcome = CreditPolicyOutcome.ACCOUNT_RESTRICTED
    elif order_val > credit_limit:
        outcome = CreditPolicyOutcome.CREDIT_LIMIT_EXCEEDED
    else:
        outcome = CreditPolicyOutcome.CREDIT_OK

    return {
        "customer_id": customer_id.strip(),
        "order_value": order_val,
        "credit_limit": credit_limit,
        "account_status": account_status,
        "payment_history": record["payment_history"],
        "outcome": outcome,
        "utilisation_pct": utilisation_pct,
        "warning_threshold": warn_pct,
        "block_threshold": block_pct,
        "utilisation_warning": utilisation_pct >= warn_pct,
    }
