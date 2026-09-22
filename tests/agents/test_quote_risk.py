"""
tests/agents/test_quote_risk.py
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.models.schemas import (
    StructuredRequest,
    RequestedItem,
    FulfilmentResult,
    FulfilmentItemResult,
    PricingPolicyResult,
    PricingLineItem,
    QuoteRiskResult,
)
from app.agents.quote_risk import run_quote_risk_sync, build_quote_risk_agent


def create_valid_request(missing_info=None, ambiguities=None):
    return StructuredRequest(
        request_id="REQ-123",
        raw_request="Need 10 switches",
        customer_reference="Acme Corp",
        requested_items=[],
        requested_delivery_date=None,
        installation_required=False,
        requested_services=[],
        requested_discount_percent=None,
        missing_information=missing_info or [],
        ambiguities=ambiguities or []
    )

def create_valid_fulfilment(overall_status="READY", items=None):
    return FulfilmentResult(
        request_id="REQ-123",
        customer_reference="Acme Corp",
        items=items or [],
        overall_status=overall_status,
        clarification_required=False,
        issues=[]
    )

def create_valid_pricing(overall_commercial_status="READY_FOR_QUOTE", credit_status="CREDIT_OK", approval_requirement="AUTO_APPROVED"):
    return PricingPolicyResult(
        request_id="REQ-123",
        customer_reference="Acme Corp",
        line_items=[],
        total_revenue="0.00",
        total_discount="0.00",
        total_tax="0.00",
        grand_total="12345.67",
        overall_margin=None,
        tripped_policies=[],
        approval_requirement=approval_requirement,
        credit_status=credit_status,
        overall_commercial_status=overall_commercial_status,
        issues=[]
    )

def mock_agent_with_draft(quote_decision="QUOTE_READY", risk_indicators=None, reasons=None, approval_requirement="AUTO_APPROVED"):
    draft = QuoteRiskResult(
        request_id="REQ-123",
        customer_reference="Acme Corp",
        quote_decision=quote_decision,
        risk_indicators=risk_indicators or [],
        reasons=reasons if reasons is not None else ["LLM Reason"],
        financial_summary_total="999.99", # Wrong to test override
        approval_requirement=approval_requirement,
        issues=[]
    )
    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.value = draft
    
    async def mock_run(*args, **kwargs):
        # Store the prompt for serialization checks
        mock_agent.last_prompt = args[0]
        return mock_response
        
    mock_agent.run = mock_run
    return mock_agent

# 1. Schema Strictness
def test_schema_strictness():
    # If we pass an invalid literal, pydantic raises ValueError
    with pytest.raises(ValueError):
        QuoteRiskResult(
            request_id="REQ-123",
            customer_reference="Acme Corp",
            quote_decision="INVALID_STATUS", # type: ignore
            risk_indicators=[],
            reasons=[],
            financial_summary_total="10.00",
            approval_requirement="AUTO_APPROVED",
            issues=[]
        )

# 2. Phase 3 Clarification Mapping & 5. LLM Override Proof (Decision - Phase 3)
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_phase_3_missing_info_forces_clarification(mock_build):
    mock_agent = mock_agent_with_draft(quote_decision="QUOTE_READY")
    mock_build.return_value = mock_agent

    req = create_valid_request(missing_info=["Missing quantity"])
    ful = create_valid_fulfilment()
    pri = create_valid_pricing()

    res = run_quote_risk_sync(req, ful, pri)
    
    assert res.quote_decision == "CUSTOMER_CLARIFICATION_REQUIRED"
    assert "MISSING_REQUIRED_INFORMATION" in res.risk_indicators

@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_phase_3_ambiguity_forces_clarification(mock_build):
    mock_agent = mock_agent_with_draft(quote_decision="QUOTE_READY")
    mock_build.return_value = mock_agent

    req = create_valid_request(ambiguities=["Unclear if enterprise or standard"])
    ful = create_valid_fulfilment()
    pri = create_valid_pricing()

    res = run_quote_risk_sync(req, ful, pri)
    
    assert res.quote_decision == "CUSTOMER_CLARIFICATION_REQUIRED"
    assert "MISSING_REQUIRED_INFORMATION" in res.risk_indicators

# 3. Phase 4 Status Mapping & 6. LLM Override Proof
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_phase_4_status_mapping(mock_build):
    mock_agent = mock_agent_with_draft(quote_decision="QUOTE_READY")
    mock_build.return_value = mock_agent

    req = create_valid_request()
    pri = create_valid_pricing()

    # PARTIAL -> CLARIFICATION
    ful = create_valid_fulfilment(overall_status="PARTIAL")
    res = run_quote_risk_sync(req, ful, pri)
    assert res.quote_decision == "CUSTOMER_CLARIFICATION_REQUIRED"
    
    # UNAVAILABLE -> CANNOT BE FULFILLED
    ful = create_valid_fulfilment(overall_status="UNAVAILABLE")
    res = run_quote_risk_sync(req, ful, pri)
    assert res.quote_decision == "REQUEST_CANNOT_BE_FULFILLED"

# 4. Phase 5 Status Mapping
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_phase_5_status_mapping(mock_build):
    mock_agent = mock_agent_with_draft(quote_decision="QUOTE_READY")
    mock_build.return_value = mock_agent
    req = create_valid_request()
    ful = create_valid_fulfilment()

    # CREDIT_BLOCKED -> CANNOT BE FULFILLED
    pri = create_valid_pricing(overall_commercial_status="CREDIT_BLOCKED", credit_status="CREDIT_LIMIT_EXCEEDED")
    res = run_quote_risk_sync(req, ful, pri)
    assert res.quote_decision == "REQUEST_CANNOT_BE_FULFILLED"
    assert "CREDIT_BLOCKED" in res.risk_indicators

    # POLICY_VIOLATION_FATAL -> CANNOT BE FULFILLED
    pri = create_valid_pricing(overall_commercial_status="POLICY_VIOLATION_FATAL")
    res = run_quote_risk_sync(req, ful, pri)
    assert res.quote_decision == "REQUEST_CANNOT_BE_FULFILLED"
    assert "POLICY_VIOLATION" in res.risk_indicators

    # APPROVAL_REQUIRED -> HUMAN_APPROVAL_REQUIRED
    pri = create_valid_pricing(overall_commercial_status="APPROVAL_REQUIRED", approval_requirement="MANAGER_APPROVAL_REQUIRED")
    res = run_quote_risk_sync(req, ful, pri)
    assert res.quote_decision == "HUMAN_APPROVAL_REQUIRED"
    assert "APPROVAL_REQUIRED" in res.risk_indicators

# 7. LLM Override Proof (Risk & Approval)
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_llm_cannot_invent_risks_or_approval(mock_build):
    # LLM hallucinates risk and approval
    mock_agent = mock_agent_with_draft(
        risk_indicators=["INVENTORY_UNAVAILABLE"], 
        approval_requirement="BOARD_APPROVAL_REQUIRED"
    )
    mock_build.return_value = mock_agent

    req = create_valid_request()
    ful = create_valid_fulfilment()
    pri = create_valid_pricing(approval_requirement="AUTO_APPROVED")

    res = run_quote_risk_sync(req, ful, pri)
    # The application clears hallucinatory risks because upstream facts are pristine
    assert "INVENTORY_UNAVAILABLE" not in res.risk_indicators
    # Approval must be from Phase 5
    assert res.approval_requirement == "AUTO_APPROVED"

# 8. LLM Override Proof (Reasons)
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_llm_reasons_preserved_but_appended(mock_build):
    mock_agent = mock_agent_with_draft(reasons=[]) # LLM omits reasons
    mock_build.return_value = mock_agent

    req = create_valid_request()
    ful = create_valid_fulfilment(overall_status="UNAVAILABLE")
    pri = create_valid_pricing()

    res = run_quote_risk_sync(req, ful, pri)
    # Should have a reason appended by python logic since status is not QUOTE_READY
    assert len(res.reasons) > 0
    assert "REQUEST_CANNOT_BE_FULFILLED" in res.reasons[0]

# 9. LLM Override Proof (Facts)
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_financial_summary_preserved(mock_build):
    mock_agent = mock_agent_with_draft() # LLM returns 999.99
    mock_build.return_value = mock_agent

    req = create_valid_request()
    ful = create_valid_fulfilment()
    pri = create_valid_pricing() # has 12345.67

    res = run_quote_risk_sync(req, ful, pri)
    assert res.financial_summary_total == "12345.67"

# 10. Precedence Logic
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_quote_ready_only_when_all_pass(mock_build):
    mock_agent = mock_agent_with_draft(quote_decision="CUSTOMER_CLARIFICATION_REQUIRED") # LLM says clarification
    mock_build.return_value = mock_agent

    req = create_valid_request()
    ful = create_valid_fulfilment()
    pri = create_valid_pricing()

    res = run_quote_risk_sync(req, ful, pri)
    # Application overrides LLM to QUOTE_READY because all inputs are perfect
    assert res.quote_decision == "QUOTE_READY"

# 11. Serialization Validation
@patch("app.agents.quote_risk.build_quote_risk_agent")
def test_inputs_serialized_in_prompt(mock_build):
    mock_agent = mock_agent_with_draft()
    mock_build.return_value = mock_agent

    req = create_valid_request()
    ful = create_valid_fulfilment()
    pri = create_valid_pricing()

    run_quote_risk_sync(req, ful, pri)
    
    prompt = mock_agent.last_prompt
    assert "StructuredRequest:" in prompt
    assert "FulfilmentResult:" in prompt
    assert "PricingPolicyResult:" in prompt
    assert req.model_dump_json(indent=2) in prompt
    assert ful.model_dump_json(indent=2) in prompt
    assert pri.model_dump_json(indent=2) in prompt

# Removed invalid test
