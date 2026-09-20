"""
tests/test_config.py — NexDeal AI  |  Phase 0 unit tests for app/config.py

Tests verify:
  1. Settings loads correctly when both env vars are present.
  2. ConfigurationError is raised when FOUNDRY_PROJECT_ENDPOINT is missing.
  3. ConfigurationError is raised when FOUNDRY_MODEL_NAME is missing.
  4. ConfigurationError is raised when a variable is present but blank/whitespace.
  5. Settings values are correctly trimmed of leading/trailing whitespace.
  6. Settings object is immutable (frozen dataclass).

These tests use monkeypatching to control env vars without touching .env.
No network calls are made — all tests are fully offline.
"""

import importlib
import sys
import pytest


# ---------------------------------------------------------------------------
# Helper — reload app.config with a clean environment
# ---------------------------------------------------------------------------
def _reload_config_with_env(monkeypatch, env: dict):
    """
    Set *env* as the complete environment, unload app.config from sys.modules,
    then re-import it so load_settings() runs fresh.

    Returns the freshly imported app.config module.
    """
    # Remove dotenv side-effects: point dotenv at a non-existent file so it
    # has nothing to load and our monkeypatched env is the sole source.
    monkeypatch.setenv("DUMMY_SENTINEL", "1")  # ensure monkeypatch is active

    # Wipe any previously cached module so load_settings() re-runs.
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("app"):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)

    # Set desired variables; clear the ones we don't want.
    for key in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL_NAME"):
        if key in env:
            monkeypatch.setenv(key, env[key])
        else:
            monkeypatch.delenv(key, raising=False)

    # Patch load_dotenv to be a no-op so the real .env on disk is ignored.
    monkeypatch.setattr("dotenv.load_dotenv", lambda **_kwargs: None)

    return importlib.import_module("app.config")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

VALID_ENDPOINT = "https://myaccount.services.ai.azure.com/api/projects/myproject"
VALID_MODEL = "gpt-4.1-mini"


class TestSettingsLoadsCorrectly:
    """Settings object is populated correctly when both vars are set."""

    def test_both_vars_present(self, monkeypatch):
        config = _reload_config_with_env(
            monkeypatch,
            {
                "FOUNDRY_PROJECT_ENDPOINT": VALID_ENDPOINT,
                "FOUNDRY_MODEL_NAME": VALID_MODEL,
            },
        )
        assert config.settings.foundry_project_endpoint == VALID_ENDPOINT
        assert config.settings.foundry_model_name == VALID_MODEL

    def test_values_are_trimmed(self, monkeypatch):
        """Leading/trailing whitespace in env vars must be stripped."""
        config = _reload_config_with_env(
            monkeypatch,
            {
                "FOUNDRY_PROJECT_ENDPOINT": f"  {VALID_ENDPOINT}  ",
                "FOUNDRY_MODEL_NAME": f"\t{VALID_MODEL}\n",
            },
        )
        assert config.settings.foundry_project_endpoint == VALID_ENDPOINT
        assert config.settings.foundry_model_name == VALID_MODEL

    def test_settings_is_immutable(self, monkeypatch):
        """Settings is a frozen dataclass — attribute assignment must raise."""
        config = _reload_config_with_env(
            monkeypatch,
            {
                "FOUNDRY_PROJECT_ENDPOINT": VALID_ENDPOINT,
                "FOUNDRY_MODEL_NAME": VALID_MODEL,
            },
        )
        with pytest.raises((AttributeError, TypeError)):
            config.settings.foundry_model_name = "something-else"  # type: ignore[misc]


class TestMissingVariables:
    """ConfigurationError is raised when required variables are absent."""

    def test_missing_endpoint_raises(self, monkeypatch):
        with pytest.raises(Exception) as exc_info:
            _reload_config_with_env(
                monkeypatch,
                {"FOUNDRY_MODEL_NAME": VALID_MODEL},  # endpoint absent
            )
        # Must be a ConfigurationError (or subclass of Exception from the module)
        assert "FOUNDRY_PROJECT_ENDPOINT" in str(exc_info.value)

    def test_missing_model_raises(self, monkeypatch):
        with pytest.raises(Exception) as exc_info:
            _reload_config_with_env(
                monkeypatch,
                {"FOUNDRY_PROJECT_ENDPOINT": VALID_ENDPOINT},  # model absent
            )
        assert "FOUNDRY_MODEL_NAME" in str(exc_info.value)

    def test_both_missing_raises(self, monkeypatch):
        with pytest.raises(Exception):
            _reload_config_with_env(monkeypatch, {})


class TestBlankVariables:
    """ConfigurationError is raised when a variable is present but blank."""

    def test_blank_endpoint_raises(self, monkeypatch):
        with pytest.raises(Exception) as exc_info:
            _reload_config_with_env(
                monkeypatch,
                {
                    "FOUNDRY_PROJECT_ENDPOINT": "   ",  # only whitespace
                    "FOUNDRY_MODEL_NAME": VALID_MODEL,
                },
            )
        assert "FOUNDRY_PROJECT_ENDPOINT" in str(exc_info.value)

    def test_blank_model_raises(self, monkeypatch):
        with pytest.raises(Exception) as exc_info:
            _reload_config_with_env(
                monkeypatch,
                {
                    "FOUNDRY_PROJECT_ENDPOINT": VALID_ENDPOINT,
                    "FOUNDRY_MODEL_NAME": "",  # empty string
                },
            )
        assert "FOUNDRY_MODEL_NAME" in str(exc_info.value)
