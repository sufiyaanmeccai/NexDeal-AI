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
