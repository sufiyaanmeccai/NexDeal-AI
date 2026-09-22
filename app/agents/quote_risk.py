"""
app/agents/quote_risk.py — NexDeal AI  |  Phase 6

Quote & Risk Agent
==================
Evaluates upstream facts to generate risk indicators and output a quote decision.
The definitive decision and final risks are strictly reconciled by Python logic.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from app.config import settings
from app.models.schemas import (
    StructuredRequest,
    FulfilmentResult,
    PricingPolicyResult,
    QuoteRiskResult,
)


_SYSTEM_INSTRUCTIONS = """\
You are the Quote & Risk Agent for NexDeal AI.
You receive three validated upstream objects:
1. StructuredRequest
2. FulfilmentResult
3. PricingPolicyResult

Your job is to synthesize these facts and output a draft QuoteRiskResult.
DO NOT recalculate any math. Do NOT alter upstream facts.
The application will override your drafted quote_decision and risk_indicators based on strict determinism.
Provide clear natural-language reasons summarizing any blocks or risks.
"""

def build_quote_risk_agent() -> Agent:
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_name,
        credential=AzureCliCredential(),
    )
    return Agent(
        client=client,
        name="QuoteRiskAgent",
        instructions=_SYSTEM_INSTRUCTIONS,
        tools=[],  # Pure decision agent, no Phase 2 tools
    )

async def run_quote_risk(
    request: StructuredRequest,
    fulfilment: FulfilmentResult,
    pricing: PricingPolicyResult,
) -> QuoteRiskResult:
    agent = build_quote_risk_agent()

    prompt = (
        f"StructuredRequest:\\n{request.model_dump_json(indent=2)}\\n\\n"
        f"FulfilmentResult:\\n{fulfilment.model_dump_json(indent=2)}\\n\\n"
        f"PricingPolicyResult:\\n{pricing.model_dump_json(indent=2)}"
    )

    response = await agent.run(
        prompt,
        options={"response_format": QuoteRiskResult}
    )

    draft: QuoteRiskResult | None = response.value
    if draft is None:
        raise ValueError("Quote & Risk Agent returned no structured value.")

    # -----------------------------------------------------------------------
    # Application-Authoritative Reconciliation
    # -----------------------------------------------------------------------
    
    # 1. Deterministic Risk Indicators
    final_risks: set[Literal[
        "UNRESOLVED_PRODUCT", "MISSING_REQUIRED_INFORMATION", "INVENTORY_UNAVAILABLE", 
        "PARTIAL_FULFILMENT", "DELIVERY_CONFLICT", "INSTALLATION_UNAVAILABLE", 
        "CREDIT_BLOCKED", "POLICY_VIOLATION", "APPROVAL_REQUIRED", "COMMERCIAL_EVALUATION_INCOMPLETE"
    ]] = set()

    if request.missing_information or request.ambiguities:
        final_risks.add("MISSING_REQUIRED_INFORMATION")
    
    for f_item in fulfilment.items:
        if f_item.product_resolution_status != "RESOLVED":
            final_risks.add("UNRESOLVED_PRODUCT")
        if f_item.inventory_status == "UNAVAILABLE":
            final_risks.add("INVENTORY_UNAVAILABLE")
        if f_item.inventory_status == "PARTIAL":
            final_risks.add("PARTIAL_FULFILMENT")
        if f_item.delivery_status == "INFEASIBLE":
            final_risks.add("DELIVERY_CONFLICT")
        if f_item.installation_status == "UNAVAILABLE":
            final_risks.add("INSTALLATION_UNAVAILABLE")
            
    if pricing.credit_status in ("CREDIT_LIMIT_EXCEEDED", "ACCOUNT_RESTRICTED"):
        final_risks.add("CREDIT_BLOCKED")
        
    if pricing.overall_commercial_status == "POLICY_VIOLATION_FATAL":
        final_risks.add("POLICY_VIOLATION")
        
    if pricing.approval_requirement in ("MANAGER_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED", "BOARD_APPROVAL_REQUIRED"):
        final_risks.add("APPROVAL_REQUIRED")
        
    if pricing.approval_requirement == "NOT_EVALUATED" or pricing.overall_commercial_status == "CLARIFICATION_REQUIRED":
        final_risks.add("COMMERCIAL_EVALUATION_INCOMPLETE")

    # 2. Deterministic Decision Precedence
    decision: Literal["QUOTE_READY", "HUMAN_APPROVAL_REQUIRED", "CUSTOMER_CLARIFICATION_REQUIRED", "REQUEST_CANNOT_BE_FULFILLED"] = "QUOTE_READY"
    
    # Check precedence from highest (1) to lowest (6)
    if fulfilment.overall_status == "UNAVAILABLE":
        decision = "REQUEST_CANNOT_BE_FULFILLED"
    elif pricing.overall_commercial_status in ("CREDIT_BLOCKED", "POLICY_VIOLATION_FATAL"):
        decision = "REQUEST_CANNOT_BE_FULFILLED"
    elif request.missing_information or request.ambiguities:
        decision = "CUSTOMER_CLARIFICATION_REQUIRED"
    elif fulfilment.overall_status in ("CLARIFICATION_REQUIRED", "PARTIAL", "DELIVERY_CONFLICT", "INSTALLATION_UNAVAILABLE"):
        decision = "CUSTOMER_CLARIFICATION_REQUIRED"
    elif pricing.overall_commercial_status == "CLARIFICATION_REQUIRED":
        decision = "CUSTOMER_CLARIFICATION_REQUIRED"
    elif pricing.overall_commercial_status == "APPROVAL_REQUIRED":
        decision = "HUMAN_APPROVAL_REQUIRED"

    # 3. Deterministic reasons / issues
    final_reasons = list(draft.reasons)
    final_issues = list(draft.issues)
    
    # Append blocking upstream reasons if missing
    if decision != "QUOTE_READY" and not final_reasons:
        final_reasons.append(f"Derived status: {decision}")

    return QuoteRiskResult(
        request_id=request.request_id,
        customer_reference=request.customer_reference,
        quote_decision=decision,
        risk_indicators=list(final_risks),
        reasons=final_reasons,
        financial_summary_total=pricing.grand_total,
        approval_requirement=pricing.approval_requirement,
        issues=final_issues
    )

def run_quote_risk_sync(
    request: StructuredRequest,
    fulfilment: FulfilmentResult,
    pricing: PricingPolicyResult,
) -> QuoteRiskResult:
    return asyncio.run(run_quote_risk(request, fulfilment, pricing))
