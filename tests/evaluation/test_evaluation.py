"""
Tests for app/evaluation/evaluators.py
"""
import pytest
from app.evaluation.evaluators import (
    eval_scalar,
    eval_normalized_string,
    eval_set_equality,
    eval_decimal,
    evaluate_layer1
)

def test_eval_scalar():
    res = eval_scalar("test", "READY", "READY")
    assert res.passed is True
    
    res2 = eval_scalar("test", "READY", "UNAVAILABLE")
    assert res2.passed is False

def test_eval_normalized_string():
    res = eval_normalized_string("test", " Meridian   DataVault  Inc ", "Meridian DataVault Inc")
    assert res.passed is True
    
    res2 = eval_normalized_string("test", "Meridian DataVault", "Meridian DataVault Inc")
    assert res2.passed is False

def test_eval_set_equality():
    res = eval_set_equality("test", ["a", "b", "c"], ["c", "b", "a"])
    assert res.passed is True
    
    res2 = eval_set_equality("test", ["a", "b"], ["a", "b", "c"])
    assert res2.passed is False

def test_eval_decimal():
    res = eval_decimal("test", "10.00", "10.00")
    assert res.passed is True
    
    res2 = eval_decimal("test", "10.00", "10.01")
    assert res2.passed is False

def test_evaluate_layer1_full_match():
    # Construct a matching result and expected payload
    result = {
        "request_understanding": {
            "customer_reference": "Meridian DataVault Inc",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [
                {"product_id": "PRD-001", "quantity": 2}
            ],
            "missing_information": []
        },
        "product_availability": {
            "overall_status": "READY",
            "clarification_required": False,
            "items": [
                {"resolved_product_id": "PRD-001", "available_quantity": 24, "inventory_status": "AVAILABLE"}
            ]
        },
        "pricing_policy": {
            "total_revenue": "18400.00",
            "grand_total": "18400.00",
            "approval_requirement": "AUTO_APPROVED"
        },
        "quote_risk": {
            "quote_decision": "QUOTE_READY",
            "approval_requirement": "AUTO_APPROVED",
            "risk_indicators": []
        }
    }
    
    expected = {
        "request_understanding": {
            "customer_reference": "Meridian DataVault Inc",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [
                {"product_id": "PRD-001", "quantity": 2}
            ],
            "expected_missing_information": []
        },
        "product_availability": {
            "overall_status": "READY",
            "clarification_required": False,
            "items": [
                {"resolved_product_id": "PRD-001", "available_quantity": 24, "inventory_status": "AVAILABLE"}
            ]
        },
        "pricing_policy": {
            "total_revenue": "18400.00",
            "grand_total": "18400.00",
            "approval_requirement": "AUTO_APPROVED"
        },
        "quote_risk": {
            "quote_decision": "QUOTE_READY",
            "approval_requirement": "AUTO_APPROVED",
            "risk_indicators": []
        }
    }
    
    eval_results = evaluate_layer1(result, expected)
    assert all(r.passed for r in eval_results)

def test_evaluate_layer1_mismatch():
    result = {
        "request_understanding": {
            "customer_reference": "Meridian DataVault Inc",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [
                {"product_id": "PRD-001", "quantity": 2}
            ],
            "missing_information": []
        }
    }
    expected = {
        "request_understanding": {
            "customer_reference": "Axiom Manufacturing",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [
                {"product_id": "PRD-001", "quantity": 2}
            ],
            "expected_missing_information": []
        }
    }
    
    eval_results = evaluate_layer1(result, expected)
    passed = all(r.passed for r in eval_results)
    assert not passed

import copy

@pytest.fixture
def base_scenario_pair():
    res = {
        "request_understanding": {
            "customer_reference": "Meridian DataVault Inc",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [{"product_id": "PRD-001", "quantity": 2}],
            "missing_information": []
        },
        "product_availability": {
            "overall_status": "READY",
            "clarification_required": False,
            "items": [{"resolved_product_id": "PRD-001", "available_quantity": 24, "inventory_status": "AVAILABLE"}]
        },
        "pricing_policy": {
            "total_revenue": "18400.00",
            "grand_total": "18400.00",
            "approval_requirement": "AUTO_APPROVED"
        },
        "quote_risk": {
            "quote_decision": "QUOTE_READY",
            "approval_requirement": "AUTO_APPROVED",
            "risk_indicators": []
        },
        "human_approval": {
            "status": "NO_APPROVAL_REQUIRED"
        }
    }
    exp = {
        "request_understanding": {
            "customer_reference": "Meridian DataVault Inc",
            "requested_delivery_date": "2026-10-15",
            "installation_required": True,
            "requested_items": [{"product_id": "PRD-001", "quantity": 2}],
            "expected_missing_information": []
        },
        "product_availability": {
            "overall_status": "READY",
            "clarification_required": False,
            "items": [{"resolved_product_id": "PRD-001", "available_quantity": 24, "inventory_status": "AVAILABLE"}]
        },
        "pricing_policy": {
            "total_revenue": "18400.00",
            "grand_total": "18400.00",
            "approval_requirement": "AUTO_APPROVED"
        },
        "quote_risk": {
            "quote_decision": "QUOTE_READY",
            "approval_requirement": "AUTO_APPROVED",
            "risk_indicators": []
        },
        "human_approval": {
            "status": "NO_APPROVAL_REQUIRED"
        }
    }
    return res, exp

def test_negative_cases_a_through_h(base_scenario_pair):
    res_orig, exp = base_scenario_pair

    # A. Correct result -> PASS
    results_a = evaluate_layer1(res_orig, exp)
    assert all(r.passed for r in results_a)

    # B. Intentionally incorrect product ID -> FAIL
    bad_b = copy.deepcopy(res_orig)
    bad_b["request_understanding"]["requested_items"][0]["product_id"] = "PRD-999"
    results_b = evaluate_layer1(bad_b, exp)
    assert not all(r.passed for r in results_b)

    # C. Intentionally incorrect quantity -> FAIL
    bad_c = copy.deepcopy(res_orig)
    bad_c["request_understanding"]["requested_items"][0]["quantity"] = 99
    results_c = evaluate_layer1(bad_c, exp)
    assert not all(r.passed for r in results_c)

    # D. Intentionally incorrect inventory/fulfilment result -> FAIL
    bad_d = copy.deepcopy(res_orig)
    bad_d["product_availability"]["overall_status"] = "UNAVAILABLE"
    results_d = evaluate_layer1(bad_d, exp)
    assert not all(r.passed for r in results_d)

    # E. Intentionally incorrect total price -> FAIL
    bad_e = copy.deepcopy(res_orig)
    bad_e["pricing_policy"]["grand_total"] = "99999.00"
    results_e = evaluate_layer1(bad_e, exp)
    assert not all(r.passed for r in results_e)

    # F. Intentionally incorrect approval requirement -> FAIL
    bad_f = copy.deepcopy(res_orig)
    bad_f["quote_risk"]["approval_requirement"] = "BOARD_APPROVAL_REQUIRED"
    results_f = evaluate_layer1(bad_f, exp)
    assert not all(r.passed for r in results_f)

    # G. Intentionally incorrect quote decision -> FAIL
    bad_g = copy.deepcopy(res_orig)
    bad_g["quote_risk"]["quote_decision"] = "REQUEST_CANNOT_BE_FULFILLED"
    results_g = evaluate_layer1(bad_g, exp)
    assert not all(r.passed for r in results_g)

    # H. Intentionally incorrect risk indicators -> FAIL
    bad_h = copy.deepcopy(res_orig)
    bad_h["quote_risk"]["risk_indicators"] = ["CREDIT_BLOCKED"]
    results_h = evaluate_layer1(bad_h, exp)
    assert not all(r.passed for r in results_h)

def test_hitl_fixture_workflow_outcome():
    # Test human approval outcome matching
    res = {"human_approval": {"status": "APPROVED"}}
    exp = {"human_approval": {"status": "APPROVED"}}
    assert all(r.passed for r in evaluate_layer1(res, exp))

    res_rej = {"human_approval": {"status": "REJECTED"}}
    assert not all(r.passed for r in evaluate_layer1(res_rej, exp))

