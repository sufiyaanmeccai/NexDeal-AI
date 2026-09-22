"""
scripts/smoke_test_quote_risk.py — NexDeal AI  |  Phase 6
"""

import asyncio
import sys

from app.models.schemas import (
    StructuredRequest,
    RequestedItem,
    FulfilmentResult,
    FulfilmentItemResult,
    PricingPolicyResult,
    PricingLineItem,
)
from app.agents.quote_risk import run_quote_risk_sync

def main():
    # 1. StructuredRequest
    request = StructuredRequest(
        request_id="req-smoke-6",
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
        requested_discount_percent=5.0,
        missing_information=[],
        ambiguities=[]
    )
    
    # 2. FulfilmentResult
    fulfilment = FulfilmentResult(
        request_id="req-smoke-6",
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
    
    # 3. PricingPolicyResult (simulating Phase 5 output where margin is missing -> NOT_EVALUATED -> CLARIFICATION_REQUIRED)
    pricing = PricingPolicyResult(
        request_id="req-smoke-6",
        customer_reference="Meridian DataVault Inc.",
        line_items=[
            PricingLineItem(
                resolved_product_id="PRD-001",
                priced_quantity=10,
                unit_price="8750.00",
                subtotal="87500.00",
                applied_discount_amount="17500.00",
                final_price="70000.00",
                installation_price="1200.00",
                margin_impact=None,
                line_status="PRICED",
                issues=[]
            )
        ],
        total_revenue="71200.00",
        total_discount="17500.00",
        total_tax="14240.00",
        grand_total="85440.00",
        overall_margin=None,
        tripped_policies=[],
        approval_requirement="NOT_EVALUATED",
        credit_status="CREDIT_OK",
        overall_commercial_status="CLARIFICATION_REQUIRED",
        issues=[]
    )

    print("==================================================")
    print("PHASE 6 SMOKE TEST — QUOTE & RISK AGENT")
    print("==================================================")
    print("Running LLM agent... (this may take a few seconds)")
    
    try:
        result = run_quote_risk_sync(request, fulfilment, pricing)
        
        print(f"\\n--- Final Decision ---")
        print(f"Decision: {result.quote_decision}")
        
        print(f"\\n--- Risk Indicators ---")
        for risk in result.risk_indicators:
            print(f"  - {risk}")
            
        print(f"\\n--- Reasons ---")
        for reason in result.reasons:
            print(f"  - {reason}")
            
        print(f"\\n--- Output Schema Strictness ---")
        print("Schema verified implicitly by Pydantic.")
        
        # Hard assertion for smoke test: 
        # Phase 5 was CLARIFICATION_REQUIRED (due to missing margin),
        # therefore Phase 6 must be CUSTOMER_CLARIFICATION_REQUIRED
        if result.quote_decision != "CUSTOMER_CLARIFICATION_REQUIRED":
            print(f"\\nFAIL: Expected decision CUSTOMER_CLARIFICATION_REQUIRED, got {result.quote_decision}")
            sys.exit(1)
            
        if "COMMERCIAL_EVALUATION_INCOMPLETE" not in result.risk_indicators:
            print(f"\\nFAIL: Expected risk indicator COMMERCIAL_EVALUATION_INCOMPLETE")
            sys.exit(1)
            
        print("\\nSUCCESS: Phase 6 Quote & Risk smoke test passed!")
        sys.exit(0)
        
    except Exception as exc:
        print(f"\\nERROR: Smoke test failed due to exception:\\n{exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
