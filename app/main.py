"""
app/main.py — NexDeal AI  |  Phase 0 Foundry Connectivity Smoke Test

Flow (verified against azure-ai-projects 2.5.0+ official docs):
  1. Load configuration (FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL_NAME from .env)
  2. Acquire DefaultAzureCredential  (uses 'az login' for local dev)
  3. Construct AIProjectClient(endpoint=..., credential=...)
  4. Obtain authenticated OpenAI client via project_client.get_openai_client()
  5. Call the Responses API: openai_client.responses.create(model=..., input=...)
  6. Access response.output_text and print it
  7. Report PASS or FAIL with a clear, actionable error message

This file is Phase 0 only — NO agents, NO business logic, NO tools.
"""

import os
import sys

# Ensure the project root is on sys.path so `from app.config import ...`
# works whether the script is run as:
#   python app/main.py        (direct)
#   python -m app.main        (module)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Step 1 — Load configuration
# ---------------------------------------------------------------------------
def _load_config():
    """Import settings or print a clean config error and exit."""
    try:
        from app.config import settings, ConfigurationError
        return settings, ConfigurationError
    except Exception as exc:
        print(f"\n[FAIL] Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main smoke test
# ---------------------------------------------------------------------------
def run_smoke_test() -> bool:
    """
    Execute the Phase 0 connectivity smoke test.

    Returns True on success, False on failure.
    Prints a clear, categorised error message for every failure mode.
    """
    print("=" * 60)
    print("  NexDeal AI — Phase 0 Foundry Connectivity Smoke Test")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1 — Configuration
    # ------------------------------------------------------------------
    settings, ConfigurationError = _load_config()

    print(f"\n[OK] FOUNDRY_PROJECT_ENDPOINT : {settings.foundry_project_endpoint}")
    print(f"[OK] FOUNDRY_MODEL_NAME       : {settings.foundry_model_name}")

    # ------------------------------------------------------------------
    # Step 2 — Imports (late-import so missing packages give clear errors)
    # ------------------------------------------------------------------
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
        from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
    except ModuleNotFoundError as exc:
        print(
            f"\n[FAIL] Missing dependency: {exc}\n"
            f"       Run:  pip install -r requirements.txt",
            file=sys.stderr,
        )
        return False

    # ------------------------------------------------------------------
    # Step 3 — Azure CLI authentication check (advisory)
    # ------------------------------------------------------------------
    try:
        credential = DefaultAzureCredential()
        # Force token acquisition now so we get a clear auth error up-front
        # rather than a cryptic failure deep inside the SDK.
        credential.get_token("https://cognitiveservices.azure.com/.default")
        print("\n[OK] DefaultAzureCredential — token acquired (az login active)")
    except Exception as auth_exc:
        # Classify the error as clearly as possible
        msg = str(auth_exc)
        if "AzureCliCredential" in msg or "az login" in msg.lower() or "cli" in msg.lower():
            print(
                "\n[FAIL] Azure CLI authentication failed.\n"
                "       You are not logged in.  Run:  az login\n"
                f"       Detail: {auth_exc}",
                file=sys.stderr,
            )
        else:
            print(
                f"\n[FAIL] Credential acquisition failed: {auth_exc}",
                file=sys.stderr,
            )
        return False

    # ------------------------------------------------------------------
    # Step 4 — Build AIProjectClient and call Responses API
    # ------------------------------------------------------------------
    SMOKE_PROMPT = "Reply with exactly: NexDeal local connection is working."

    try:
        with (
            DefaultAzureCredential() as cred,
            AIProjectClient(
                endpoint=settings.foundry_project_endpoint,
                credential=cred,
            ) as project_client,
        ):
            print("\n[OK] AIProjectClient constructed")

            with project_client.get_openai_client() as openai_client:
                print("[OK] OpenAI client obtained via get_openai_client()")
                print(f"\n[..] Sending smoke-test prompt to '{settings.foundry_model_name}' ...")

                response = openai_client.responses.create(
                    model=settings.foundry_model_name,
                    input=SMOKE_PROMPT,
                )

    # -- Error categories --------------------------------------------------
    except HttpResponseError as http_exc:
        status = http_exc.status_code
        reason = http_exc.reason

        if status == 401:
            print(
                f"\n[FAIL] Authorization failure (HTTP 401 Unauthorized).\n"
                f"       Your identity may lack the required Foundry RBAC role.\n"
                f"       Check 'Access Control (IAM)' on your Azure AI Project resource.\n"
                f"       Detail: {http_exc.message}",
                file=sys.stderr,
            )
        elif status == 403:
            print(
                f"\n[FAIL] Forbidden (HTTP 403).\n"
                f"       Your identity is authenticated but not authorised.\n"
                f"       Detail: {http_exc.message}",
                file=sys.stderr,
            )
        elif status == 404:
            print(
                f"\n[FAIL] Not Found (HTTP 404).\n"
                f"       Possible causes:\n"
                f"         • FOUNDRY_PROJECT_ENDPOINT is incorrect or the project does not exist.\n"
                f"         • FOUNDRY_MODEL_NAME '{settings.foundry_model_name}' is not a valid deployment name.\n"
                f"       Detail: {http_exc.message}",
                file=sys.stderr,
            )
        else:
            print(
                f"\n[FAIL] API error (HTTP {status} {reason}).\n"
                f"       Detail: {http_exc.message}",
                file=sys.stderr,
            )
        return False

    except ValueError as val_exc:
        # Usually an invalid endpoint URL
        print(
            f"\n[FAIL] Invalid configuration value: {val_exc}\n"
            f"       Check that FOUNDRY_PROJECT_ENDPOINT is a valid URL.",
            file=sys.stderr,
        )
        return False

    except OSError as net_exc:
        print(
            f"\n[FAIL] Network / connectivity error: {net_exc}\n"
            f"       Check your internet connection and firewall settings.",
            file=sys.stderr,
        )
        return False

    except Exception as exc:
        print(
            f"\n[FAIL] Unexpected error during model invocation: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return False

    # ------------------------------------------------------------------
    # Step 5 — Validate and print response
    # ------------------------------------------------------------------
    output_text = response.output_text
    print(f"\n[OK] Model response received:\n       \"{output_text}\"")
    print("\n" + "=" * 60)
    print("  RESULT: PASS — Foundry connectivity confirmed.")
    print("=" * 60 + "\n")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
