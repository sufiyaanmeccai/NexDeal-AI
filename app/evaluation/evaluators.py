"""
app/evaluation/evaluators.py — NexDeal AI | Phase 10

Deterministic evaluation logic.
"""

import json
from decimal import Decimal
from pydantic import BaseModel
from typing import Any

class EvaluatorResult(BaseModel):
    name: str
    passed: bool
    details: str

def eval_scalar(name: str, actual: Any, expected: Any) -> EvaluatorResult:
    """Exact scalar equality"""
    passed = actual == expected
    return EvaluatorResult(
        name=name,
        passed=passed,
        details=f"Expected '{expected}', got '{actual}'" if not passed else f"Match: '{actual}'"
    )

def eval_normalized_string(name: str, actual: str | None, expected: str | None) -> EvaluatorResult:
    """Normalized string equality"""
    act_norm = " ".join(actual.strip().rstrip(".").lower().split()) if actual else ""
    exp_norm = " ".join(expected.strip().rstrip(".").lower().split()) if expected else ""
    passed = act_norm == exp_norm
    return EvaluatorResult(
        name=name,
        passed=passed,
        details=f"Expected '{expected}', got '{actual}'" if not passed else f"Match: '{actual}'"
    )

def eval_set_equality(name: str, actual: list | set, expected: list | set) -> EvaluatorResult:
    """Set equality for order-independent collections"""
    act_set = set(actual) if actual is not None else set()
    exp_set = set(expected) if expected is not None else set()
    passed = act_set == exp_set
    return EvaluatorResult(
        name=name,
        passed=passed,
        details=f"Expected {sorted(exp_set)}, got {sorted(act_set)}" if not passed else f"Match: {sorted(act_set)}"
    )

def eval_decimal(name: str, actual: str | None, expected: str | None) -> EvaluatorResult:
    """Decimal financial comparisons"""
    try:
        act_dec = Decimal(actual) if actual else None
        exp_dec = Decimal(expected) if expected else None
        passed = act_dec == exp_dec
    except Exception:
        passed = False
        
    return EvaluatorResult(
        name=name,
        passed=passed,
        details=f"Expected {expected}, got {actual}" if not passed else f"Match: {actual}"
    )

def evaluate_layer1(result_data: dict, expected: dict) -> list[EvaluatorResult]:
    """
    Run all deterministic checks for Layer 1.
    result_data should be a dict containing keys mapping to phase results.
    """
    eval_results = []
    
    # 1. Request Understanding (Phase 3)
    if "request_understanding" in expected and "request_understanding" in result_data:
        exp_ru = expected["request_understanding"]
        act_ru = result_data["request_understanding"]
        
        eval_results.append(eval_normalized_string("ru_customer_reference", act_ru.get("customer_reference"), exp_ru.get("customer_reference")))
        eval_results.append(eval_scalar("ru_requested_delivery_date", act_ru.get("requested_delivery_date"), exp_ru.get("requested_delivery_date")))
        eval_results.append(eval_scalar("ru_installation_required", act_ru.get("installation_required"), exp_ru.get("installation_required")))
        
        # requested items list check (check product_ids and quantities)
        act_items = act_ru.get("requested_items", [])
        exp_items = exp_ru.get("requested_items", [])
        
        # compare counts
        eval_results.append(eval_scalar("ru_items_count", len(act_items), len(exp_items)))
        
        def _item_key(x):
            return (str(x.get("product_id") or ""), int(x.get("quantity") or 0))
        act_item_tups = [(i.get("product_id"), i.get("quantity")) for i in sorted(act_items, key=_item_key)]
        exp_item_tups = [(i.get("product_id"), i.get("quantity")) for i in sorted(exp_items, key=_item_key)]
        
        eval_results.append(eval_scalar("ru_items_match", act_item_tups, exp_item_tups))
        
        # expected ambiguities / missing
        act_missing = act_ru.get("missing_information", [])
        exp_missing = exp_ru.get("expected_missing_information", [])
        if exp_missing:
            # Special case: If expecting a missing customer reference, evaluate via the first-class field
            # rather than requiring an exact phrase in the missing_information text.
            all_found = True
            for em in exp_missing:
                if "customer reference" in em.lower():
                    if act_ru.get("customer_reference") is not None:
                        all_found = False
                else:
                    if not any(em.lower() in am.lower() for am in act_missing):
                        all_found = False
                        
            eval_results.append(EvaluatorResult(
                name="ru_expected_missing_info",
                passed=all_found,
                details=f"Expected {exp_missing} in {act_missing} or via field check" if not all_found else f"Matched: {exp_missing}"
            ))
        else:
            eval_results.append(EvaluatorResult(
                name="ru_expected_missing_info",
                passed=True,
                details="No missing info required"
            ))

    # 2. Product & Availability (Phase 4)
    if "product_availability" in expected and "product_availability" in result_data:
        exp_pa = expected["product_availability"]
        act_pa = result_data["product_availability"]
        
        eval_results.append(eval_scalar("pa_overall_status", act_pa.get("overall_status"), exp_pa.get("overall_status")))
        eval_results.append(eval_scalar("pa_clarification_required", act_pa.get("clarification_required"), exp_pa.get("clarification_required")))
        
        act_items_pa = act_pa.get("items", [])
        exp_items_pa = exp_pa.get("items", [])
        
        # Just check the aggregated tuples for availability
        def _pa_key(x):
            return (str(x.get("resolved_product_id") or ""), int(x.get("available_quantity") or 0), str(x.get("inventory_status") or ""))
        act_pa_tups = [(i.get("resolved_product_id"), i.get("available_quantity"), i.get("inventory_status")) for i in sorted(act_items_pa, key=_pa_key)]
        exp_pa_tups = [(i.get("resolved_product_id"), i.get("available_quantity"), i.get("inventory_status")) for i in sorted(exp_items_pa, key=_pa_key)]
        
        eval_results.append(eval_scalar("pa_items_inventory_match", act_pa_tups, exp_pa_tups))
        
    # 3. Pricing & Policy (Phase 5)
    if "pricing_policy" in expected and "pricing_policy" in result_data:
        exp_pp = expected["pricing_policy"]
        act_pp = result_data["pricing_policy"]
        
        eval_results.append(eval_decimal("pp_total_revenue", act_pp.get("total_revenue"), exp_pp.get("total_revenue")))
        eval_results.append(eval_decimal("pp_grand_total", act_pp.get("grand_total"), exp_pp.get("grand_total")))
        eval_results.append(eval_scalar("pp_approval_requirement", act_pp.get("approval_requirement"), exp_pp.get("approval_requirement")))

    # 0. Schema / Type Validation
    if isinstance(result_data, dict):
        eval_results.append(EvaluatorResult(name="schema_valid", passed=True, details="Valid result dictionary structure"))
    else:
        eval_results.append(EvaluatorResult(name="schema_valid", passed=False, details=f"Expected dict, got {type(result_data)}"))

    # 4. Quote & Risk (Phase 6)
    if "quote_risk" in expected and "quote_risk" in result_data:
        exp_qr = expected["quote_risk"]
        act_qr = result_data["quote_risk"]
        
        eval_results.append(eval_scalar("qr_quote_decision", act_qr.get("quote_decision"), exp_qr.get("quote_decision")))
        eval_results.append(eval_scalar("qr_approval_requirement", act_qr.get("approval_requirement"), exp_qr.get("approval_requirement")))
        
        act_risks = set(act_qr.get("risk_indicators", []))
        exp_risks = set(exp_qr.get("risk_indicators", []))
        risks_match = (act_risks == exp_risks) or (act_risks - {"MISSING_REQUIRED_INFORMATION"} == exp_risks)
        eval_results.append(EvaluatorResult(
            name="qr_risk_indicators",
            passed=risks_match,
            details=f"Expected {sorted(exp_risks)}, got {sorted(act_risks)}" if not risks_match else f"Match: {sorted(act_risks)}"
        ))

    # 5. Human Approval / Workflow Outcome (Phase 8 / HITL fixture)
    if "human_approval" in expected and "human_approval" in result_data:
        exp_ha = expected["human_approval"]
        act_ha = result_data["human_approval"]
        eval_results.append(eval_scalar("ha_status", act_ha.get("status"), exp_ha.get("status")))
        
    return eval_results

