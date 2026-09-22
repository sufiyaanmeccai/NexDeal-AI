"""
app/agents/pricing_policy.py — NexDeal AI  |  Phase 5

Pricing & Policy Agent
=======================
Receives a StructuredRequest and FulfilmentResult, calculates exact 
deterministic pricing and applies business policies, returning a 
reconciled PricingPolicyResult.

Architectural boundaries
------------------------
- ALL monetary math is done in Python using Phase 2 decimal logic.
- Phase 2 outputs are exactly replicated in the final result.
- Margins and approvals requiring cost are safely skipped, as no
  authoritative product cost exists.
- The final overall status is mathematically derived.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Literal

from azure.identity import AzureCliCredential

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient

from app.config import settings
from app.models.schemas import (
    FulfilmentResult,
    PricingLineItem,
    PricingPolicyResult,
    StructuredRequest,
)

# Phase 2 Tools
from app.tools.pricing import calculate_customer_price, calculate_tax
from app.tools.policies import check_discount_policy, check_credit_policy
from app.tools.customers import get_customer, CustomerNotFoundError
from app.tools.data_loader import get_all_customers


# ---------------------------------------------------------------------------
# Status Precedence
# ---------------------------------------------------------------------------

_COMMERCIAL_STATUS_PRECEDENCE = [
    "CREDIT_BLOCKED",
    "POLICY_VIOLATION_FATAL",
    "CLARIFICATION_REQUIRED",
    "APPROVAL_REQUIRED",
    "READY_FOR_QUOTE",
]

def _derive_overall_commercial_status(
    credit_status: str,
    approval_requirement: str,
    tripped_policies: list[str],
    line_items: list[PricingLineItem],
) -> Literal[
    "READY_FOR_QUOTE",
    "APPROVAL_REQUIRED",
    "CREDIT_BLOCKED",
    "CLARIFICATION_REQUIRED",
    "POLICY_VIOLATION_FATAL",
]:
    if credit_status in ("CREDIT_LIMIT_EXCEEDED", "ACCOUNT_RESTRICTED"):
        return "CREDIT_BLOCKED"
    
    if "margin_below_absolute_minimum" in tripped_policies:
        return "POLICY_VIOLATION_FATAL"
    
    # Check for SKIPPED_UNAVAILABLE or NEEDS_CLARIFICATION
    if any(item.line_status in ("SKIPPED_UNAVAILABLE", "NEEDS_CLARIFICATION") for item in line_items):
        return "CLARIFICATION_REQUIRED"
    
    # If approval evaluation is unresolved (NOT_EVALUATED)
    if approval_requirement == "NOT_EVALUATED":
        return "CLARIFICATION_REQUIRED"
        
    if approval_requirement in (
        "MANAGER_APPROVAL_REQUIRED",
        "DIRECTOR_APPROVAL_REQUIRED",
        "BOARD_APPROVAL_REQUIRED",
    ):
        return "APPROVAL_REQUIRED"
        
    return "READY_FOR_QUOTE"


# ---------------------------------------------------------------------------
# Agent-exposed tools (wrappers)
# ---------------------------------------------------------------------------

@tool
def tool_search_customers(query: str) -> str:
    """
    Search customers by name or ID. Use this to find the customer_id for a given customer_reference.
    
    Args:
        query: Customer name or reference.
    """
    term = query.strip().lower()
    customers = get_all_customers()
    if not term:
        return json.dumps([{"customer_id": c["customer_id"], "company_name": c["company_name"]} for c in customers])
    
    results = []
    for c in customers:
        if term in c["customer_id"].lower() or term in c["company_name"].lower():
            results.append({"customer_id": c["customer_id"], "company_name": c["company_name"]})
    return json.dumps(results)


@tool
def tool_get_customer(customer_id: str) -> str:
    """
    Get customer details by ID.
    
    Args:
        customer_id: Exact customer ID.
    """
    try:
        c = get_customer(customer_id)
        return json.dumps({
            "customer_id": c["customer_id"],
            "company_name": c["company_name"],
            "customer_tier": c["customer_tier"],
            "account_status": c["account_status"],
            "credit_limit": str(c["credit_limit"]),
            "discount_limit": str(c["discount_limit"])
        })
    except CustomerNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_calculate_customer_price(product_id: str, quantity: int, customer_id: str) -> str:
    """
    Calculate the effective customer price and volume discount for a product.
    
    Args:
        product_id: Exact product ID.
        quantity: Quantity requested.
        customer_id: Exact customer ID.
    """
    try:
        res = calculate_customer_price(product_id, quantity, customer_id)
        # Decimal to str
        for k, v in res.items():
            if isinstance(v, Decimal):
                res[k] = str(v)
        return json.dumps(res)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_check_discount_policy(customer_id: str, discount_percent: float) -> str:
    """
    Check if a proposed discount is within the customer's tier limit.
    """
    try:
        res = check_discount_policy(customer_id, Decimal(str(discount_percent)))
        for k, v in res.items():
            if isinstance(v, Decimal):
                res[k] = str(v)
        # outcome is Enum, convert to str
        res["outcome"] = res["outcome"].value if hasattr(res["outcome"], "value") else str(res["outcome"])
        return json.dumps(res)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@tool
def tool_check_credit_policy(customer_id: str, order_value: float) -> str:
    """
    Evaluate credit eligibility for the total order value.
    """
    try:
        res = check_credit_policy(customer_id, Decimal(str(order_value)))
        for k, v in res.items():
            if isinstance(v, Decimal):
                res[k] = str(v)
        res["outcome"] = res["outcome"].value if hasattr(res["outcome"], "value") else str(res["outcome"])
        return json.dumps(res)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


_PHASE5_TOOLS = [
    tool_search_customers,
    tool_get_customer,
    tool_calculate_customer_price,
    tool_check_discount_policy,
    tool_check_credit_policy,
]

_SYSTEM_INSTRUCTIONS = """\
You are the Pricing & Policy Agent for NexDeal AI.
You receive a StructuredRequest and a FulfilmentResult.
Your job is to determine the final pricing and policy outcomes.
Use the provided tools to lookup customer IDs, evaluate effective pricing per item, and check policies.
You MUST output a valid PricingPolicyResult JSON object.
"""

def build_agent() -> Agent:
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_name,
        credential=AzureCliCredential(),
    )
    return Agent(
        client=client,
        name="PricingPolicyAgent",
        instructions=_SYSTEM_INSTRUCTIONS,
        tools=_PHASE5_TOOLS,
    )


async def run_pricing_policy(
    request: StructuredRequest,
    fulfilment: FulfilmentResult,
) -> PricingPolicyResult:
    """
    Deterministically reconcile and return the pricing and policy result.
    """
    agent = build_agent()
    
    prompt = (
        f"StructuredRequest:\n{request.model_dump_json(indent=2)}\n\n"
        f"FulfilmentResult:\n{fulfilment.model_dump_json(indent=2)}"
    )
    
    response = await agent.run(
        prompt,
        options={"response_format": PricingPolicyResult},
    )
    
    draft: PricingPolicyResult | None = response.value
    if draft is None:
        raise ValueError("Pricing & Policy Agent returned no structured value.")
        
    # We ignore LLM draft arithmetic and recompute everything deterministically.
    
    customer_id = None
    # Attempt to resolve customer ID safely
    if draft.line_items and request.customer_reference:
        # Try to find a match via data_loader directly to ensure correctness
        customers = get_all_customers()
        term = request.customer_reference.strip().lower()
        for c in customers:
            if term == c["company_name"].lower() or term == c["customer_id"].lower():
                customer_id = c["customer_id"]
                break
                
    if customer_id is None and request.customer_reference:
        # Fallback to search
        customers = get_all_customers()
        term = request.customer_reference.strip().lower()
        for c in customers:
            if term in c["company_name"].lower() or term in c["customer_id"].lower():
                customer_id = c["customer_id"]
                break

    line_items: list[PricingLineItem] = []
    total_revenue = Decimal("0.00")
    total_discount_amount = Decimal("0.00")
    total_subtotal = Decimal("0.00")
    
    for f_item in fulfilment.items:
        if f_item.product_resolution_status != "RESOLVED" or f_item.inventory_status == "UNAVAILABLE":
            # Item not found or completely out of stock
            line_items.append(PricingLineItem(
                resolved_product_id=f_item.resolved_product_id,
                priced_quantity=None,
                unit_price="0.00",
                subtotal="0.00",
                applied_discount_amount="0.00",
                final_price="0.00",
                installation_price="0.00" if f_item.installation_price is None else f_item.installation_price,
                margin_impact=None,
                line_status="SKIPPED_UNAVAILABLE",
                issues=["Product unresolved or unavailable."]
            ))
            # Include installation price in revenue if it somehow exists
            if f_item.installation_price:
                total_revenue += Decimal(f_item.installation_price)
            continue
            
        # Resolved and has some stock
        quantity_to_price = f_item.available_quantity
        if quantity_to_price is None or quantity_to_price == 0:
             line_items.append(PricingLineItem(
                resolved_product_id=f_item.resolved_product_id,
                priced_quantity=None,
                unit_price="0.00",
                subtotal="0.00",
                applied_discount_amount="0.00",
                final_price="0.00",
                installation_price="0.00" if f_item.installation_price is None else f_item.installation_price,
                margin_impact=None,
                line_status="SKIPPED_UNAVAILABLE",
                issues=["Available quantity is zero or missing."]
            ))
             if f_item.installation_price:
                total_revenue += Decimal(f_item.installation_price)
             continue
             
        status: Literal["PRICED", "PRICED_PARTIAL", "NEEDS_CLARIFICATION"] = "PRICED"
        if f_item.inventory_status == "PARTIAL":
            status = "PRICED_PARTIAL"
            
        if not customer_id:
            # Cannot price without customer_id
            line_items.append(PricingLineItem(
                resolved_product_id=f_item.resolved_product_id,
                priced_quantity=quantity_to_price,
                unit_price="0.00",
                subtotal="0.00",
                applied_discount_amount="0.00",
                final_price="0.00",
                installation_price="0.00" if f_item.installation_price is None else f_item.installation_price,
                margin_impact=None,
                line_status="NEEDS_CLARIFICATION",
                issues=["Customer ID not resolved."]
            ))
            if f_item.installation_price:
                total_revenue += Decimal(f_item.installation_price)
            continue
            
        try:
            p_res = calculate_customer_price(f_item.resolved_product_id, quantity_to_price, customer_id)
            
            install_price = Decimal("0.00")
            if f_item.installation_price:
                install_price = Decimal(f_item.installation_price)
                
            line_items.append(PricingLineItem(
                resolved_product_id=f_item.resolved_product_id,
                priced_quantity=quantity_to_price,
                unit_price=str(p_res["unit_price"]),
                subtotal=str(p_res["subtotal"]),
                applied_discount_amount=str(p_res["discount_amount"]),
                final_price=str(p_res["net_total"]),
                installation_price=str(install_price),
                margin_impact=None,
                line_status=status,
                issues=[]
            ))
            
            total_subtotal += p_res["subtotal"]
            total_discount_amount += p_res["discount_amount"]
            total_revenue += p_res["net_total"] + install_price
            
        except Exception as exc:
            line_items.append(PricingLineItem(
                resolved_product_id=f_item.resolved_product_id,
                priced_quantity=quantity_to_price,
                unit_price="0.00",
                subtotal="0.00",
                applied_discount_amount="0.00",
                final_price="0.00",
                installation_price="0.00" if f_item.installation_price is None else f_item.installation_price,
                margin_impact=None,
                line_status="NEEDS_CLARIFICATION",
                issues=[f"Pricing error: {str(exc)}"]
            ))
            if f_item.installation_price:
                total_revenue += Decimal(f_item.installation_price)

    # -----------------------------------------------------------------------
    # Discount source & policy flow
    # -----------------------------------------------------------------------
    requested_discount = request.requested_discount_percent
    effective_discount_pct = Decimal("0.00")
    if total_subtotal > Decimal("0"):
        effective_discount_pct = (total_discount_amount / total_subtotal * Decimal("100")).quantize(Decimal("0.01"))
        
    policy_discount_pct = Decimal(str(requested_discount)) if requested_discount is not None else effective_discount_pct

    tripped_policies = []
    
    if customer_id:
        disc_check = check_discount_policy(customer_id, policy_discount_pct)
        out = disc_check["outcome"]
        if hasattr(out, "value"):
            out = out.value
        if out == "EXCEEDS_LIMIT":
            tripped_policies.append("discount_exceeds_tier_limit")

    # -----------------------------------------------------------------------
    # Tax & Totals
    # -----------------------------------------------------------------------
    total_tax = calculate_tax(total_revenue, "standard")
    grand_total = total_revenue + total_tax
    
    # -----------------------------------------------------------------------
    # Margin & Approval
    # -----------------------------------------------------------------------
    # Margin is explicitly unavailable. Set to None.
    overall_margin = None
    
    # Approval evaluates to NOT_EVALUATED because margin is unavailable.
    approval_requirement: Literal["AUTO_APPROVED", "MANAGER_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED", "BOARD_APPROVAL_REQUIRED", "NOT_EVALUATED"] = "NOT_EVALUATED"

    # -----------------------------------------------------------------------
    # Credit Policy
    # -----------------------------------------------------------------------
    credit_status: Literal["CREDIT_OK", "CREDIT_LIMIT_EXCEEDED", "ACCOUNT_RESTRICTED", "NOT_EVALUATED"] = "NOT_EVALUATED"
    if customer_id:
        try:
            c_check = check_credit_policy(customer_id, grand_total)
            out = c_check["outcome"]
            if hasattr(out, "value"):
                out = out.value
            if out == "CREDIT_LIMIT_EXCEEDED":
                credit_status = "CREDIT_LIMIT_EXCEEDED"
                tripped_policies.append("order_value_exceeds_customer_credit_limit")
            elif out == "ACCOUNT_RESTRICTED":
                credit_status = "ACCOUNT_RESTRICTED"
                tripped_policies.append("customer_account_status_not_active")
            else:
                credit_status = "CREDIT_OK"
        except Exception:
            credit_status = "NOT_EVALUATED"
            
    # -----------------------------------------------------------------------
    # Derived Overall Status
    # -----------------------------------------------------------------------
    overall_status = _derive_overall_commercial_status(
        credit_status,
        approval_requirement,
        tripped_policies,
        line_items,
    )
    
    return PricingPolicyResult(
        request_id=request.request_id,
        customer_reference=request.customer_reference,
        line_items=line_items,
        total_revenue=str(total_revenue),
        total_discount=str(total_discount_amount),
        total_tax=str(total_tax),
        grand_total=str(grand_total),
        overall_margin=None,
        tripped_policies=tripped_policies,
        approval_requirement=approval_requirement,
        credit_status=credit_status,
        overall_commercial_status=overall_status,
        issues=[]
    )

def run_pricing_policy_sync(
    request: StructuredRequest,
    fulfilment: FulfilmentResult,
) -> PricingPolicyResult:
    return asyncio.run(run_pricing_policy(request, fulfilment))
