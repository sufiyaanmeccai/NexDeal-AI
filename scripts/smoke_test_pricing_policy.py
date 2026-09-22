"""
scripts/smoke_test_pricing_policy.py — NexDeal AI  |  Phase 5

Live smoke test for the Pricing & Policy Agent.
Runs the agent against a hardcoded StructuredRequest and FulfilmentResult, 
verifying that deterministic logic correctly overrides the LLM draft, evaluates 
policies, and computes pricing safely without the missing cost data.
"""

import asyncio
import sys
from decimal import Decimal

from app.models.schemas import (
    StructuredRequest,
    RequestedItem,
    FulfilmentResult,
    FulfilmentItemResult,
)
from app.agents.pricing_policy import run_pricing_policy_sync


def main():
    # 1. Create a dummy StructuredRequest based on Phase 1 data.
    request = StructuredRequest(
        request_id="req-smoke-5",
        raw_request="We need 10 RackServer Pro 2U units from Meridian DataVault Inc.",
        customer_reference="Meridian DataVault Inc.",
        requested_items=[
            RequestedItem(
                raw_product_reference="RackServer Pro 2U",
                product_id=None,
                quantity=10,
                specifications=[]
            )
        ],
        requested_delivery_date=None,
        installation_required=True,
        requested_services=[],
        requested_discount_percent=5.0, # requesting 5%
        missing_information=[],
        ambiguities=[]
    )
    
    # 2. Create the associated FulfilmentResult.
    # Product PRD-001 is "RackServer Pro 2U"
    fulfilment = FulfilmentResult(
        request_id="req-smoke-5",
        customer_reference="Meridian DataVault Inc.",
        items=[
            FulfilmentItemResult(
                raw_product_reference="RackServer Pro 2U",
                resolved_product_id="PRD-001",
                product_resolution_status="RESOLVED",
                requested_quantity=10,
                available_quantity=10,
                inventory_status="AVAILABLE",
                requested_delivery_date=None,
                delivery_status="NOT_REQUESTED",
                installation_required=True,
                installation_status="AVAILABLE",
                installation_price="1200.00",
                issues=[]
            )
        ],
        overall_status="READY",
        clarification_required=False,
        issues=[]
    )
    
    print("==================================================")
    print("PHASE 5 SMOKE TEST — PRICING & POLICY AGENT")
    print("==================================================")
    print("Running LLM agent... (this may take a few seconds)")
    
    try:
        result = run_pricing_policy_sync(request, fulfilment)
        
        # Verify and print results
        print("\n--- Output Schema Validation ---")
        print("Schema strictness verified implicitly by Pydantic.")
        
        print("\n--- Commercial Status ---")
        print(f"Overall Status: {result.overall_commercial_status}")
        print(f"Approval Requirement: {result.approval_requirement}")
        print(f"Credit Status: {result.credit_status}")
        print(f"Tripped Policies: {result.tripped_policies}")
        
        print("\n--- Totals ---")
        print(f"Total Revenue: {result.total_revenue}")
        print(f"Total Discount: {result.total_discount}")
        print(f"Total Tax: {result.total_tax}")
        print(f"Grand Total: {result.grand_total}")
        
        print("\n--- Items ---")
        for idx, item in enumerate(result.line_items, 1):
            print(f"Item {idx}: {item.resolved_product_id} (qty {item.priced_quantity})")
            print(f"  Unit Price: {item.unit_price}")
            print(f"  Subtotal: {item.subtotal}")
            print(f"  Discount: {item.applied_discount_amount}")
            print(f"  Final Price: {item.final_price}")
            print(f"  Installation: {item.installation_price}")
            print(f"  Margin Impact: {item.margin_impact}")
            print(f"  Status: {item.line_status}")
            
        # Hard assertion for smoke test
        if result.approval_requirement != "NOT_EVALUATED":
            print("\nFAIL: approval_requirement must be NOT_EVALUATED due to missing margin.")
            sys.exit(1)
        if result.overall_margin is not None:
            print("\nFAIL: overall_margin must be None.")
            sys.exit(1)
        if result.overall_commercial_status != "CLARIFICATION_REQUIRED":
            print("\nFAIL: overall_commercial_status must be CLARIFICATION_REQUIRED.")
            sys.exit(1)
            
        print("\nSUCCESS: Phase 5 Pricing & Policy smoke test passed!")
        sys.exit(0)
        
    except Exception as exc:
        print(f"\nERROR: Smoke test failed due to exception:\n{exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
