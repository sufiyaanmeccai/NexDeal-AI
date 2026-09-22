"""
tests/orchestration/test_human_approval.py — NexDeal AI  |  Phase 8
"""

import pytest
from unittest.mock import patch
from datetime import date
import asyncio

from agent_framework import WorkflowBuilder
from app.models.schemas import (
    QuoteRiskResult,
    ApprovalRequest,
    ApprovalResponse,
    HumanApprovalResult
)
from app.workflows.orchestrator import ApprovalGateExecutor

def make_fixture(decision: str, req_tier: str | None = None) -> QuoteRiskResult:
    return QuoteRiskResult(
        request_id="REQ-123",
        customer_reference="Acme",
        quote_decision=decision,
        risk_indicators=[],
        reasons=[],
        financial_summary_total="100.00",
        approval_requirement=req_tier, # type: ignore
        issues=[]
    )

@pytest.mark.anyio
async def test_approval_gate_bypassed_for_ready():
    # Arrange
    p8 = ApprovalGateExecutor(id="test_gate")
    wf = WorkflowBuilder(start_executor=p8).build()
    qrr = make_fixture("QUOTE_READY", "AUTO_APPROVED")
    
    # Act
    events = await wf.run(qrr)
    outputs = events.get_outputs()
    
    # Assert
    assert len(outputs) == 1
    out = outputs[0]
    assert out.status == "NO_APPROVAL_REQUIRED"
    assert out.original_quote_risk_result is qrr
    assert out.approval_request is None

@pytest.mark.anyio
async def test_approval_gate_pauses_for_human():
    p8 = ApprovalGateExecutor(id="test_gate")
    wf = WorkflowBuilder(start_executor=p8).build()
    qrr = make_fixture("HUMAN_APPROVAL_REQUIRED", "MANAGER_APPROVAL_REQUIRED")
    
    events = await wf.run(qrr)
    outputs = events.get_outputs()
    requests = events.get_request_info_events()
    
    assert len(outputs) == 0  # Paused!
    assert len(requests) == 1
    req = requests[0]
    assert isinstance(req.data, ApprovalRequest)
    assert req.data.requested_approval_level == "MANAGER_APPROVAL_REQUIRED"
    
    # Resume with approval
    resp = ApprovalResponse(approved=True, reviewer_note="OK")
    events2 = await wf.run(responses={req.request_id: resp})
    
    outputs2 = events2.get_outputs()
    assert len(outputs2) == 1
    out = outputs2[0]
    assert out.status == "APPROVED"
    assert out.approval_request.requested_approval_level == "MANAGER_APPROVAL_REQUIRED"

@pytest.mark.anyio
async def test_approval_gate_rejected():
    p8 = ApprovalGateExecutor(id="test_gate")
    wf = WorkflowBuilder(start_executor=p8).build()
    qrr = make_fixture("HUMAN_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED")
    
    events = await wf.run(qrr)
    requests = events.get_request_info_events()
    req = requests[0]
    
    # Resume with rejection
    resp = ApprovalResponse(approved=False, reviewer_note="Too risky")
    events2 = await wf.run(responses={req.request_id: resp})
    
    outputs2 = events2.get_outputs()
    out = outputs2[0]
    assert out.status == "REJECTED"

@pytest.mark.anyio
async def test_approval_gate_bypassed_if_missing_tier():
    # HUMAN_APPROVAL_REQUIRED but missing tier for some reason -> wait, 
    # the schema enforces a tier or NOT_EVALUATED.
    p8 = ApprovalGateExecutor(id="test_gate")
    wf = WorkflowBuilder(start_executor=p8).build()
    qrr = make_fixture("HUMAN_APPROVAL_REQUIRED", "NOT_EVALUATED")
    
    events = await wf.run(qrr)
    outputs = events.get_outputs()
    
    assert len(outputs) == 1
    out = outputs[0]
    assert out.status == "NO_APPROVAL_REQUIRED"
