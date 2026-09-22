"""
app/telemetry.py — NexDeal AI  |  Phase 9

Configures OpenTelemetry for the application.
"""

from agent_framework.observability import configure_otel_providers, enable_sensitive_telemetry

from app.config import settings


_telemetry_configured = False


def configure_telemetry(force: bool = False) -> None:
    """Configure telemetry based on application settings."""
    global _telemetry_configured
    if _telemetry_configured and not force:
        return

    if not settings.enable_telemetry:
        return

    _telemetry_configured = True

    if settings.log_sensitive_data:
        enable_sensitive_telemetry()

    if settings.applicationinsights_connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ImportError as exc:
            raise RuntimeError(
                "azure-monitor-opentelemetry is required when APPLICATIONINSIGHTS_CONNECTION_STRING is configured."
            ) from exc
        configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
    else:
        # Default to local console exporters if no connection string is provided
        configure_otel_providers(enable_console_exporters=True)
