"""
tests/agents/test_pricing_policy.py — NexDeal AI  |  Phase 5

Unit tests for Pricing & Policy Agent.
These tests verify:
- Schema strictness
- Financial precision (str decimals)
- Missing margin evaluation forces NOT_EVALUATED and CLARIFICATION_REQUIRED
- Installation price handled accurately
- Status precedence
- LLM override proof (via patching Agent.run)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from decimal import Decimal

from app.models.schemas import (
    PricingLineItem,
    PricingPolicyResult,
    StructuredRequest,
    RequestedItem,
    FulfilmentResult,
    FulfilmentItemResult,
)
from app.agents.pricing_policy import (
    _derive_overall_commercial_status,
    run_pricing_policy,
    _PHASE5_TOOLS,
)


def test_schema_strictness():
    """Verify PricingLineItem schema requires all fields."""
    with pytest.raises(ValidationError):
        PricingLineItem()

    # Valid construction
    item = PricingLineItem(
        resolved_product_id="PRD-001",
        priced_quantity=10,
        unit_price="10.00",
        subtotal="100.00",
        applied_discount_amount="0.00",
        final_price="100.00",
        installation_price="0.00",
        margin_impact=None,
        line_status="PRICED",
        issues=[]
    )
    assert item.margin_impact is None

def test_missing_cost_margin_and_approval_status():
    """
    Explicit test proving when cost is missing:
    - approval_requirement becomes NOT_EVALUATED
    - status is forced to CLARIFICATION_REQUIRED
    """
    status = _derive_overall_commercial_status(
        credit_status="CREDIT_OK",
        approval_requirement="NOT_EVALUATED",
        tripped_policies=[],
        line_items=[
            PricingLineItem(
                resolved_product_id="PRD-001",
                priced_quantity=10,
                unit_price="10.00",
                subtotal="100.00",
                applied_discount_amount="0.00",
                final_price="100.00",
                installation_price="0.00",
                margin_impact=None,
                line_status="PRICED",
                issues=[]
            )
        ]
    )
    assert status == "CLARIFICATION_REQUIRED", "Must not return READY_FOR_QUOTE when approval is unresolved."


def test_overall_commercial_status_precedence():
    """Verify precedence logic."""
    item = PricingLineItem(
        resolved_product_id="PRD-001",
        priced_quantity=10,
        unit_price="10.00",
        subtotal="100.00",
        applied_discount_amount="0.00",
        final_price="100.00",
        installation_price="0.00",
        margin_impact=None,
        line_status="PRICED",
        issues=[]
    )
    
    # 1. CREDIT_BLOCKED overrides everything
    assert _derive_overall_commercial_status(
        "CREDIT_LIMIT_EXCEEDED", "AUTO_APPROVED", [], [item]
    ) == "CREDIT_BLOCKED"
    
    # 2. POLICY_VIOLATION_FATAL overrides clarification
    assert _derive_overall_commercial_status(
        "CREDIT_OK", "NOT_EVALUATED", ["margin_below_absolute_minimum"], [item]
    ) == "POLICY_VIOLATION_FATAL"
    
    # 3. NOT_EVALUATED forces CLARIFICATION_REQUIRED
    assert _derive_overall_commercial_status(
        "CREDIT_OK", "NOT_EVALUATED", [], [item]
    ) == "CLARIFICATION_REQUIRED"
    
    # 4. SKIPPED_UNAVAILABLE forces CLARIFICATION_REQUIRED
    item_skipped = PricingLineItem(**{**item.model_dump(), "line_status": "SKIPPED_UNAVAILABLE"})
    assert _derive_overall_commercial_status(
        "CREDIT_OK", "AUTO_APPROVED", [], [item_skipped]
    ) == "CLARIFICATION_REQUIRED"
    
    # 5. APPROVAL_REQUIRED
    assert _derive_overall_commercial_status(
        "CREDIT_OK", "MANAGER_APPROVAL_REQUIRED", [], [item]
    ) == "APPROVAL_REQUIRED"
    
    # 6. READY_FOR_QUOTE
    assert _derive_overall_commercial_status(
        "CREDIT_OK", "AUTO_APPROVED", [], [item]
    ) == "READY_FOR_QUOTE"


def test_boundary_checks():
    """Verify Phase 4 tools are not exposed."""
    tool_names = [t.name for t in _PHASE5_TOOLS]
    assert "tool_search_products" not in tool_names
    assert "tool_check_inventory" not in tool_names


def test_llm_override_proof():
    """
    Prove that the application ignores the LLM's arithmetic and fake approvals.
    The LLM might return READY_FOR_QUOTE and fake margin=100%, but Python must overwrite it.
    """
    req = StructuredRequest(
        request_id="req-1",
        raw_request="Need 1 switch",
        customer_reference="Meridian DataVault Inc.",
        requested_items=[],
        requested_delivery_date=None,
        installation_required=None,
        requested_services=[],
        requested_discount_percent=None,
        missing_information=[],
        ambiguities=[]
    )
    
    fulfilment = FulfilmentResult(
        request_id="req-1",
        customer_reference="Meridian DataVault Inc.",
        items=[
            FulfilmentItemResult(
                raw_product_reference="1 switch",
                resolved_product_id="PRD-001",
                product_resolution_status="RESOLVED",
                requested_quantity=1,
                available_quantity=1,
                inventory_status="AVAILABLE",
                requested_delivery_date=None,
                delivery_status="NOT_REQUESTED",
                installation_required=True,
                installation_status="AVAILABLE",
                installation_price="150.00",
                issues=[]
            )
        ],
        overall_status="READY",
        clarification_required=False,
        issues=[]
    )
    
    # Fake LLM response returning completely fabricated (and "successful") values
    class FakeResponse:
        value = PricingPolicyResult(
            request_id="req-1",
            customer_reference="Meridian DataVault Inc.",
            line_items=[
                PricingLineItem(
                    resolved_product_id="PRD-001",
                    priced_quantity=1,
                    unit_price="10.00",  # Fake price
                    subtotal="10.00",
                    applied_discount_amount="0.00",
                    final_price="10.00",
                    installation_price="150.00",
                    margin_impact="50.00", # Fake margin
                    line_status="PRICED",
                    issues=[]
                )
            ],
            total_revenue="160.00",
            total_discount="0.00",
            total_tax="0.00",
            grand_total="160.00",
            overall_margin="50.00", # Fake margin
            tripped_policies=[],
            approval_requirement="AUTO_APPROVED", # Fake approval
            credit_status="CREDIT_OK",
            overall_commercial_status="READY_FOR_QUOTE", # Fake status
            issues=[]
        )
        
    async def run_test():
        with patch("agent_framework.Agent.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = FakeResponse()
            
            result = await run_pricing_policy(req, fulfilment)
            
            # Verify LLM values were overwritten deterministically
            assert result.overall_margin is None, "Cost is unavailable, margin MUST be None."
            assert result.line_items[0].margin_impact is None
            assert result.approval_requirement == "NOT_EVALUATED", "Approval must not be fabricated."
            assert result.overall_commercial_status == "CLARIFICATION_REQUIRED", "NOT_EVALUATED forces CLARIFICATION_REQUIRED."
            
            # Verify installation price is accurately handled
            assert Decimal(result.total_revenue) > Decimal("160.00")
            assert result.line_items[0].installation_price == "150.00"

    asyncio.run(run_test())
