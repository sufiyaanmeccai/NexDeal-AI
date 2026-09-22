"""
scripts/smoke_test_observability.py — NexDeal AI  |  Phase 9

Smoke test for the OpenTelemetry integration.
Runs the workflow with telemetry enabled locally and verifies metrics/traces.
"""

import asyncio
import os
import sys

# Force telemetry environment variables for the smoke test
os.environ["ENABLE_TELEMETRY"] = "true"
os.environ["LOG_SENSITIVE_DATA"] = "false"
# Clear Azure connection string to ensure we fallback to console exporter
os.environ.pop("APPLICATIONINSIGHTS_CONNECTION_STRING", None)

from app.telemetry import configure_telemetry
from app.workflows.orchestrator import run_orchestration_sync


import io
from opentelemetry import trace
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor


def main():
    print("=== NexDeal AI Observability Smoke Test ===", flush=True)
    print("Configuring telemetry (Expect Console Span/Metric Exporters to initialize)...", flush=True)

    # Initialize OpenTelemetry
    configure_telemetry()

    # Capture the exact JSON telemetry output to memory for deterministic privacy assertion
    buf = io.StringIO()
    capture_exporter = ConsoleSpanExporter(out=buf)
    provider = trace.get_tracer_provider()
    actual_provider = getattr(provider, "_tracer_provider", provider)
    actual_provider.add_span_processor(SimpleSpanProcessor(capture_exporter))

    print("\nRunning workflow... Check stdout for OpenTelemetry span JSON payloads:", flush=True)
    print("-" * 60, flush=True)

    sample_request = "Acme Corp needs 5 enterprise switches (SW-1007)."
    reference_date = "2026-10-15"
    company_name = "Acme Corp"

    try:
        # Run workflow synchronously
        result = run_orchestration_sync(sample_request, reference_date)
    except Exception as e:
        print(f"Workflow failed: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    telemetry_output = buf.getvalue()

    # Deterministic privacy assertions on telemetry output
    assert len(telemetry_output) > 0, "Privacy assertion failed: no telemetry output was captured."

    assert sample_request not in telemetry_output, (
        "Privacy assertion failed: raw request emitted in telemetry output."
    )
    assert company_name not in telemetry_output, (
        "Privacy assertion failed: customer/company name emitted in telemetry output."
    )

    print("-" * 60, flush=True)
    print("Privacy verification: PASS (raw request and company name suppressed).", flush=True)
    print("Workflow completed successfully.", flush=True)
    print(f"Final output type: {type(result).__name__}", flush=True)


if __name__ == "__main__":
    main()
