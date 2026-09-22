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

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from app.models.schemas import (
    StructuredRequest,
    FulfilmentResult,
    PricingPolicyResult,
    QuoteRiskResult,
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
        await ctx.yield_output(res)


def build_orchestration_workflow():
    """Builds and validates the deterministic 4-phase graph workflow."""
    p3 = Phase3Executor(id="phase_3_request_understanding")
    p4 = Phase4Executor(id="phase_4_product_availability")
    p5 = Phase5Executor(id="phase_5_pricing_policy")
    p6 = Phase6Executor(id="phase_6_quote_risk")

    return (
        WorkflowBuilder(start_executor=p3)
        .add_edge(p3, p4)
        .add_edge(p4, p5)
        .add_edge(p5, p6)
        .build()
    )


async def run_orchestration(raw_request: str, reference_date: str) -> QuoteRiskResult:
    """
    Executes the end-to-end NexDeal AI orchestration pipeline.
    
    Args:
        raw_request: The raw customer communication.
        reference_date: The explicitly injected evaluation date (YYYY-MM-DD).
    """
    wf = build_orchestration_workflow()
    
    events = await wf.run(WorkflowInput(raw_request=raw_request, reference_date=reference_date))
    
    outputs = events.get_outputs()
    if not outputs:
        raise RuntimeError("Workflow failed to produce a final QuoteRiskResult.")
        
    return outputs[-1]


def run_orchestration_sync(raw_request: str, reference_date: str) -> QuoteRiskResult:
    """Synchronous wrapper for run_orchestration."""
    return asyncio.run(run_orchestration(raw_request, reference_date))

