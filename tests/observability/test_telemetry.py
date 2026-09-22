"""
tests/observability/test_telemetry.py — NexDeal AI  |  Phase 9
"""

import pytest
from unittest.mock import patch, MagicMock

import app.config
from app.config import Settings
import app.telemetry
from app.telemetry import configure_telemetry


@pytest.fixture(autouse=True)
def reset_telemetry_state():
    app.telemetry._telemetry_configured = False
    yield
    app.telemetry._telemetry_configured = False


@pytest.fixture
def mock_settings():
    def _mock(enable=False, log_sensitive=False, conn_str=None):
        return Settings(
            foundry_project_endpoint="https://test.services.ai.azure.com",
            foundry_model_name="gpt-4o-mini",
            enable_telemetry=enable,
            applicationinsights_connection_string=conn_str,
            log_sensitive_data=log_sensitive,
        )
    return _mock

@patch("app.telemetry.configure_otel_providers")
@patch("app.telemetry.enable_sensitive_telemetry")
def test_configure_telemetry_disabled(mock_sensitive, mock_providers, mock_settings):
    """If enable_telemetry is False, nothing should be configured."""
    with patch("app.telemetry.settings", mock_settings(enable=False)):
        configure_telemetry()
        mock_providers.assert_not_called()
        mock_sensitive.assert_not_called()

@patch("app.telemetry.configure_otel_providers")
@patch("app.telemetry.enable_sensitive_telemetry")
def test_configure_telemetry_console(mock_sensitive, mock_providers, mock_settings):
    """If enabled with no connection string, console exporters are used."""
    with patch("app.telemetry.settings", mock_settings(enable=True, conn_str=None)):
        configure_telemetry()
        mock_providers.assert_called_once_with(enable_console_exporters=True)
        mock_sensitive.assert_not_called()

@patch("app.telemetry.configure_otel_providers")
@patch("app.telemetry.enable_sensitive_telemetry")
def test_configure_telemetry_sensitive(mock_sensitive, mock_providers, mock_settings):
    """If log_sensitive_data is True, enable_sensitive_telemetry is called."""
    with patch("app.telemetry.settings", mock_settings(enable=True, log_sensitive=True)):
        configure_telemetry()
        mock_sensitive.assert_called_once()
        mock_providers.assert_called_once_with(enable_console_exporters=True)

@patch("app.telemetry.configure_otel_providers")
@patch("app.telemetry.enable_sensitive_telemetry")
def test_configure_telemetry_azure(mock_sensitive, mock_providers, mock_settings):
    """If conn_str provided, configure_azure_monitor is called."""
    with patch("app.telemetry.settings", mock_settings(enable=True, conn_str="InstrumentationKey=123")):
        mock_cam = MagicMock()
        mock_module = MagicMock()
        mock_module.configure_azure_monitor = mock_cam
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": mock_module}):
            configure_telemetry()

            mock_cam.assert_called_once_with(
                connection_string="InstrumentationKey=123"
            )
            mock_providers.assert_not_called()


def test_configure_telemetry_azure_missing_dependency(mock_settings):
    """If conn_str provided but azure-monitor-opentelemetry missing, raises RuntimeError."""
    with patch("app.telemetry.settings", mock_settings(enable=True, conn_str="InstrumentationKey=123")):
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": None}):
            with pytest.raises(RuntimeError, match="azure-monitor-opentelemetry is required"):
                configure_telemetry()


def test_azure_monitor_dependency_available():
    """Verify azure-monitor-opentelemetry package is installed and export function exists."""
    from azure.monitor.opentelemetry import configure_azure_monitor
    assert callable(configure_azure_monitor)


def test_workflow_execution_metric_failed():
    """Verify workflow_executions counter records failed status on exception."""
    import asyncio
    from unittest.mock import AsyncMock
    from app.workflows.orchestrator import run_orchestration, workflow_executions

    with patch("app.workflows.orchestrator.build_orchestration_workflow") as mock_build:
        mock_wf = MagicMock()
        mock_wf.run = AsyncMock(side_effect=RuntimeError("Simulated LLM crash"))
        mock_build.return_value = mock_wf

        with patch.object(workflow_executions, "add") as mock_add:
            with pytest.raises(RuntimeError, match="Simulated LLM crash"):
                asyncio.run(run_orchestration("Test request", "2026-10-15"))

            mock_add.assert_called_with(1, {"status": "failed"})

