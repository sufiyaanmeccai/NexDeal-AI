import pytest
from demo.parser import parse_agent_response, ParseError

def test_parser_basic_dict():
    text = "status='NO_APPROVAL_REQUIRED' original_quote_risk_result=QuoteRiskResult(request_id=None, customer_reference='Acme Corp', quote_decision='QUOTE_READY', risk_indicators=['INVENTORY_UNAVAILABLE'], reasons=['Not enough stock.', 'Check inventory.'], financial_summary_total='500.00', approval_requirement='NOT_EVALUATED', issues=[]) approval_request=None approval_response=None"

    res = parse_agent_response(text)

    assert res['status'] == 'NO_APPROVAL_REQUIRED'
    assert res['original_quote_risk_result']['__class__'] == 'QuoteRiskResult'
    assert res['original_quote_risk_result']['request_id'] is None
    assert res['original_quote_risk_result']['customer_reference'] == 'Acme Corp'
    assert res['original_quote_risk_result']['quote_decision'] == 'QUOTE_READY'
    assert res['original_quote_risk_result']['risk_indicators'] == ['INVENTORY_UNAVAILABLE']
    assert res['original_quote_risk_result']['reasons'] == ['Not enough stock.', 'Check inventory.']
    assert res['original_quote_risk_result']['financial_summary_total'] == '500.00'
    assert res['original_quote_risk_result']['approval_requirement'] == 'NOT_EVALUATED'
    assert res['original_quote_risk_result']['issues'] == []
    assert res['approval_request'] is None
    assert res['approval_response'] is None

def test_parser_number():
    text = "count=42 price=19.99"
    res = parse_agent_response(text)
    assert res['count'] == 42
    assert res['price'] == 19.99

def test_parser_malformed():
    with pytest.raises(ParseError):
        parse_agent_response("status='unclosed_string")

    with pytest.raises(ParseError):
        parse_agent_response("obj=QuoteRiskResult(id=)")

def test_parser_exact_real_cloud_shape():
    text = "status='NO_APPROVAL_REQUIRED' original_quote_risk_result=QuoteRiskResult(request_id=None, customer_reference=None, quote_decision='CUSTOMER_CLARIFICATION_REQUIRED', risk_indicators=['COMMERCIAL_EVALUATION_INCOMPLETE', 'MISSING_REQUIRED_INFORMATION'], reasons=['The request is empty with no items or services specified.', 'Missing required information prevents proper fulfilment and pricing evaluation.', 'Clarification is required from the customer before proceeding.'], financial_summary_total='0.00', approval_requirement='NOT_EVALUATED', issues=['request is empty']) approval_request=None approval_response=None"
    res = parse_agent_response(text)
    assert res['status'] == 'NO_APPROVAL_REQUIRED'
    assert res['original_quote_risk_result']['quote_decision'] == 'CUSTOMER_CLARIFICATION_REQUIRED'
    assert len(res['original_quote_risk_result']['risk_indicators']) == 2
    assert len(res['original_quote_risk_result']['reasons']) == 3
    assert res['original_quote_risk_result']['issues'] == ['request is empty']

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from demo.server import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

@patch("demo.server.credential")
@patch("demo.server.httpx.AsyncClient.post")
def test_api_quote_success(mock_post, mock_credential):
    import os
    os.environ["FOUNDRY_AGENT_RESPONSES_ENDPOINT"] = "http://fake"
    from demo.server import app
    # Re-evaluate endpoint config in test

    class DummyToken:
        token = "fake_token"
    mock_credential.get_token = AsyncMock(return_value=DummyToken())

    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": [
            {
                "content": [
                    {
                        "text": "status='NO_APPROVAL_REQUIRED' original_quote_risk_result=QuoteRiskResult(id=1) approval_request=None approval_response=None"
                    }
                ]
            }
        ]
    }
    mock_resp.raise_for_status = lambda: None
    mock_post.return_value = mock_resp

    # We must mock ENDPOINT inside the module for the test
    with patch("demo.server.ENDPOINT", "http://fake"):
        response = client.post("/api/quote", json={"raw_request": "test"})
        if response.status_code != 200:
            print("ERROR:", response.json())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "NO_APPROVAL_REQUIRED"
