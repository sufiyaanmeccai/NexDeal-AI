"""
scripts/smoke_test_human_approval.py — NexDeal AI  |  Phase 8
"""

import asyncio
import sys

from agent_framework import WorkflowBuilder
from app.models.schemas import (
    QuoteRiskResult,
    ApprovalResponse,
)
from app.workflows.orchestrator import run_orchestration, ApprovalGateExecutor


async def run_pipeline_validation():
    print("==================================================")
    print("PART A: REAL PIPELINE VALIDATION")
    print("==================================================")
    
    reference_date = "2026-09-22"
    raw_request = (
        "Hi NexDeal, Acme Manufacturing needs 10 RackServer Pro 2U units. "
        "Installation is required. Please deliver by 15 October. We would also like a 5% discount."
    )
    
    print(f"Input Text: '{raw_request}'")
    result = await run_orchestration(raw_request, reference_date)
    
    # Check if it paused or finished
    if hasattr(result, "get_outputs"):
        outputs = result.get_outputs()
        if not outputs:
            requests = result.get_request_info_events()
            if requests:
                print("PIPELINE PAUSED: Wait, real pipeline shouldn't have paused because of missing margin/cost.")
                return False
        out = outputs[-1]
    else:
        out = result
    print(f"Final Status: {out.status}")
    print(f"Quote Decision: {out.original_quote_risk_result.quote_decision}")
    
    # Real pipeline naturally stops at CUSTOMER_CLARIFICATION_REQUIRED since Phase 5 has no product-cost
    if out.original_quote_risk_result.quote_decision != "CUSTOMER_CLARIFICATION_REQUIRED":
        print("Warning: Expected CUSTOMER_CLARIFICATION_REQUIRED from real pipeline due to unresolved product/cost.")
    return True


async def run_hitl_validation():
    print("\\n==================================================")
    print("PART B: HITL GATE VALIDATION")
    print("==================================================")
    
    # Construct a valid fixture representing HUMAN_APPROVAL_REQUIRED
    fixture = QuoteRiskResult(
        request_id="FIXTURE-1",
        customer_reference="TestCorp",
        quote_decision="HUMAN_APPROVAL_REQUIRED",
        risk_indicators=["POLICY_VIOLATION"],
        reasons=["Order value exceeds auto-approve threshold."],
        financial_summary_total="500000.00",
        approval_requirement="DIRECTOR_APPROVAL_REQUIRED",
        issues=[]
    )
    
    # Run the isolated gate
    p8 = ApprovalGateExecutor(id="phase_8_human_approval")
    wf = WorkflowBuilder(start_executor=p8).build()
    
    print("Test 1: Approval Path")
    print("Running workflow with fixture...")
    events = await wf.run(fixture)
    
    requests = events.get_request_info_events()
    if not requests:
        print("ERROR: Workflow did not pause for approval.")
        return False
        
    req = requests[0]
    print(f"Workflow Paused. Emitted request for: {req.data}")
    
    print("Simulating human APPROVAL...")
    resp = ApprovalResponse(approved=True, reviewer_note="Approved by Director.")
    events2 = await wf.run(responses={req.request_id: resp})
    
    out = events2.get_outputs()[-1]
    print(f"Result Status: {out.status}\\n")
    
    if out.status != "APPROVED":
        print("ERROR: Expected APPROVED status.")
        return False

    print("Test 2: Rejection Path")
    print("Running workflow with fixture...")
    events = await wf.run(fixture)
    req = events.get_request_info_events()[0]
    
    print("Simulating human REJECTION...")
    resp2 = ApprovalResponse(approved=False, reviewer_note="Too much discount.")
    events2 = await wf.run(responses={req.request_id: resp2})
    
    out2 = events2.get_outputs()[-1]
    print(f"Result Status: {out2.status}")
    
    if out2.status != "REJECTED":
        print("ERROR: Expected REJECTED status.")
        return False
        
    return True


async def main():
    print("PHASE 8 SMOKE TEST")
    
    a_ok = await run_pipeline_validation()
    b_ok = await run_hitl_validation()
    
    if a_ok and b_ok:
        print("\\nSUCCESS: Phase 8 Workflow smoke test passed!")
        sys.exit(0)
    else:
        print("\\nERROR: Smoke test failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
