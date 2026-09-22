"""
app/workflows/orchestrator.py — NexDeal AI  |  Phase 7

Multi-Agent Orchestration
=========================
Connects Phase 3, 4, 5, and 6 into a sequential typed workflow using Microsoft Agent Framework.
"""

import asyncio
from datetime import date
from dataclasses import dataclass
from typing import Any

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler, response_handler

from app.models.schemas import (
    StructuredRequest,
    FulfilmentResult,
    PricingPolicyResult,
    QuoteRiskResult,
    ApprovalRequest,
    ApprovalResponse,
    HumanApprovalResult,
)
from app.agents.request_understanding import understand_request
from app.agents.product_availability import check_availability
from app.agents.pricing_policy import run_pricing_policy
from app.agents.quote_risk import run_quote_risk


@dataclass
class WorkflowInput:
    """Explicit typed input for the orchestration pipeline."""
    raw_request: str
    reference_date: str


class Phase3Executor(Executor):
    @handler
    async def process(self, msg: WorkflowInput, ctx: WorkflowContext[StructuredRequest]) -> None:
        """Runs the Request Understanding Agent (Phase 3)."""
        # Store reference_date for Phase 4
        ctx.set_state("reference_date", msg.reference_date)
        
        req = await understand_request(msg.raw_request)
        ctx.set_state("structured_request", req)
        await ctx.send_message(req)


class Phase4Executor(Executor):
    @handler
    async def process(self, req: StructuredRequest, ctx: WorkflowContext[FulfilmentResult]) -> None:
        """Runs the Product & Availability Agent (Phase 4)."""
        ref_date_str = ctx.get_state("reference_date")
        ref_date = date.fromisoformat(ref_date_str)
        
        ful = await check_availability(req, reference_date=ref_date)
        ctx.set_state("fulfilment_result", ful)
        await ctx.send_message(ful)


class Phase5Executor(Executor):
    @handler
    async def process(self, ful: FulfilmentResult, ctx: WorkflowContext[PricingPolicyResult]) -> None:
        """Runs the Pricing & Policy Agent (Phase 5)."""
        req = ctx.get_state("structured_request")
        
        pri = await run_pricing_policy(req, ful)
        ctx.set_state("pricing_policy_result", pri)
        await ctx.send_message(pri)


class Phase6Executor(Executor):
    @handler
    async def process(self, pri: PricingPolicyResult, ctx: WorkflowContext[QuoteRiskResult]) -> None:
        """Runs the Quote & Risk Agent (Phase 6)."""
        req = ctx.get_state("structured_request")
        ful = ctx.get_state("fulfilment_result")
        
        res = await run_quote_risk(req, ful, pri)
        await ctx.send_message(res)


class ApprovalGateExecutor(Executor):
    @handler
    async def process(self, res: QuoteRiskResult, ctx: WorkflowContext[HumanApprovalResult]) -> None:
        """Runs the Phase 8 Human Approval Gate."""
        # Determine if approval is genuinely required
        real_tiers = ["MANAGER_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED", "BOARD_APPROVAL_REQUIRED"]
        
        if res.quote_decision == "HUMAN_APPROVAL_REQUIRED" and res.approval_requirement in real_tiers:
            # We must emit a typed approval request and pause
            req = ApprovalRequest(
                request_id=res.request_id,
                customer_reference=res.customer_reference,
                requested_approval_level=res.approval_requirement,  # type: ignore
                financial_summary_total=res.financial_summary_total,
                risk_indicators=res.risk_indicators,  # type: ignore
                reasons=res.reasons,
                approval_question=f"Please review and approve this quote. Total: {res.financial_summary_total}."
            )
            
            ctx.set_state("pending_quote_risk_result", res)
            ctx.set_state("pending_approval_request", req)
            
            await ctx.request_info(req, ApprovalResponse)
        else:
            # Bypass approval gate for all other terminal states
            out = HumanApprovalResult(
                status="NO_APPROVAL_REQUIRED",
                original_quote_risk_result=res,
                approval_request=None,
                approval_response=None
            )
            await ctx.yield_output(out)

    @response_handler
    async def handle_approval(self, original_request: ApprovalRequest, response: ApprovalResponse, ctx: WorkflowContext[HumanApprovalResult]) -> None:
        """Resumes the workflow when a human response is provided."""
        res = ctx.get_state("pending_quote_risk_result")
        req = original_request or ctx.get_state("pending_approval_request")
        
        if response.approved:
            status_val = "APPROVED"
        else:
            status_val = "REJECTED"
            
        out = HumanApprovalResult(
            status=status_val,
            original_quote_risk_result=res,
            approval_request=req,
            approval_response=response
        )
        await ctx.yield_output(out)


def build_orchestration_workflow():
    """Builds and validates the deterministic 4-phase graph workflow."""
    p3 = Phase3Executor(id="phase_3_request_understanding")
    p4 = Phase4Executor(id="phase_4_product_availability")
    p5 = Phase5Executor(id="phase_5_pricing_policy")
    p6 = Phase6Executor(id="phase_6_quote_risk")
    p8 = ApprovalGateExecutor(id="phase_8_human_approval")

    return (
        WorkflowBuilder(start_executor=p3)
        .add_edge(p3, p4)
        .add_edge(p4, p5)
        .add_edge(p5, p6)
        .add_edge(p6, p8)
        .build()
    )


async def run_orchestration(raw_request: str, reference_date: str) -> HumanApprovalResult | Any:
    """
    Executes the end-to-end NexDeal AI orchestration pipeline.
    
    Args:
        raw_request: The raw customer communication.
        reference_date: The explicitly injected evaluation date (YYYY-MM-DD).
    Returns:
        The final HumanApprovalResult, or the WorkflowRunResult event stream if paused.
    """
    wf = build_orchestration_workflow()
    
    events = await wf.run(WorkflowInput(raw_request=raw_request, reference_date=reference_date))
    
    outputs = events.get_outputs()
    if not outputs:
        # It's paused pending approval, return the event stream so caller can inspect get_request_info_events()
        return events
        
    return outputs[-1]


def run_orchestration_sync(raw_request: str, reference_date: str) -> HumanApprovalResult | Any:
    """Synchronous wrapper for run_orchestration."""
    return asyncio.run(run_orchestration(raw_request, reference_date))

