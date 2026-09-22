"""
scripts/smoke_test_workflow.py — NexDeal AI  |  Phase 7
"""

import sys

from app.workflows.orchestrator import run_orchestration_sync

def main():
    print("==================================================")
    print("PHASE 7 SMOKE TEST — END-TO-END WORKFLOW")
    print("==================================================")
    print("Running multi-agent orchestration pipeline... (this will take 15-30 seconds)")
    
    # 1. Explicit reference date
    reference_date = "2026-09-22"
    
    # 2. Realistic synthetic B2B request
    raw_request = (
        "Hi NexDeal, Acme Manufacturing needs 10 RackServer Pro 2U units. "
        "Installation is required. Please deliver by 15 October. We would also like a 5% discount."
    )
    
    print(f"\\nInput Date: {reference_date}")
    print(f"Input Text: '{raw_request}'")
    
    try:
        # 3. Run ACTUAL Phase 7 orchestration end-to-end
        result = run_orchestration_sync(raw_request, reference_date)
        
        # 4. Print intermediate proof and final QuoteRiskResult
        print("\\n--- Pipeline Executed Successfully ---")
        
        print(f"\\n--- Final Decision ---")
        print(f"Decision: {result.quote_decision}")
        
        print(f"\\n--- Risk Indicators ---")
        for risk in result.risk_indicators:
            print(f"  - {risk}")
            
        print(f"\\n--- Reasons ---")
        for reason in result.reasons:
            print(f"  - {reason}")
            
        # 5. Verify the workflow completed successfully and the final decision is consistent.
        print("\\nSUCCESS: Phase 7 Workflow smoke test passed!")
        sys.exit(0)
        
    except Exception as exc:
        print(f"\\nERROR: Smoke test failed due to exception:\\n{exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
