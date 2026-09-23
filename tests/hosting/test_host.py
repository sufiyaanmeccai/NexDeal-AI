import pytest

def test_host_initialization():
    """Verify that the host server initializes without crashing."""
    try:
        from app.host import app
        assert app is not None

        # Verify it's an ASGI app wrapper (ResponsesHostServer)
        from agent_framework_foundry_hosting import ResponsesHostServer
        assert isinstance(app, ResponsesHostServer)
    except Exception as e:
        pytest.fail(f"Host initialization failed: {e}")

def test_hosted_message_text_extraction():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from app.workflows.orchestrator import Phase3Executor
    from agent_framework import Message

    executor = Phase3Executor(id="phase_3_request_understanding")
    mock_ctx = MagicMock()
    executor.process = AsyncMock()

    msg = Message(role="user", contents=["I need 50 laptops"])
    
    asyncio.run(executor.process_messages([msg], mock_ctx))
    
    executor.process.assert_called_once()
    called_input = executor.process.call_args[0][0]
    assert called_input.raw_request == "I need 50 laptops"
