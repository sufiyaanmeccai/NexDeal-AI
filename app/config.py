"""
app/config.py — NexDeal AI  |  Phase 0 configuration loader

Loads environment variables from .env (via python-dotenv) and exposes
a clean, validated Settings object. Any missing required variable raises
a clear ConfigurationError at import time, not buried in a runtime traceback.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when a required environment variable is missing or blank."""


def _require(name: str) -> str:
    """Return the value of *name* from the environment, or raise ConfigurationError."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Required environment variable '{name}' is missing or empty.\n"
            f"  1. Copy .env.example → .env\n"
            f"  2. Fill in the value for {name}\n"
            f"  3. Restart the process."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable, validated application settings for Phase 0."""

    foundry_project_endpoint: str
    """Foundry project endpoint URL.
    Format: https://<account>.services.ai.azure.com/api/projects/<project>
    """

    foundry_model_name: str
    """Deployment name of the model in your Foundry project (not the model family name)."""

    enable_telemetry: bool
    """Whether to configure telemetry exporters/providers (Azure or local console)."""

    applicationinsights_connection_string: str | None
    """Azure Monitor connection string. If missing but telemetry is enabled, defaults to local console exporter."""

    log_sensitive_data: bool
    """Whether to capture and emit sensitive data like customer names or raw requests."""


def load_settings() -> Settings:
    """Load .env, validate required variables, and return a Settings instance."""
    # Load .env from the project root (parent of app/).
    # override=False means already-set environment variables take precedence.
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path=dotenv_path, override=False)

    return Settings(
        foundry_project_endpoint=_require("FOUNDRY_PROJECT_ENDPOINT"),
        foundry_model_name=_require("FOUNDRY_MODEL_NAME"),
        enable_telemetry=os.environ.get("ENABLE_TELEMETRY", "false").strip().lower() == "true",
        applicationinsights_connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip() or None,
        log_sensitive_data=os.environ.get("LOG_SENSITIVE_DATA", "false").strip().lower() == "true",
    )


# Module-level singleton — validated once on first import.
settings = load_settings()
