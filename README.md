# NexDeal AI

> **B2B Quotation & Order Processing — Powered by Microsoft Foundry AI Agents**

NexDeal AI transforms messy B2B customer requests (emails, messages, faxes) into validated quotations and orders through a coordinated team of specialised AI agents. It eliminates manual data entry, enforces pricing and compliance rules, and routes edge-cases to human review — all within a single, auditable workflow.

---

## Table of Contents

1. [What NexDeal AI Does](#what-nexdeal-ai-does)
2. [High-Level Architecture](#high-level-architecture)
3. [Current Status — Phase 0](#current-status--phase-0-foundation)
4. [What Is Already in Azure](#what-is-already-in-azure)
5. [What Is NOT Yet Implemented](#what-is-not-yet-implemented)
6. [Prerequisites](#prerequisites)
7. [Setup & Running the Smoke Test](#setup--running-the-smoke-test)
8. [Running Tests](#running-tests)
9. [Project Roadmap](#project-roadmap)

---

## What NexDeal AI Does

A sales rep at a manufacturer receives a customer email: *"We need 500 units of item X, 200 of Y, fastest delivery, usual discount."*

NexDeal AI:

1. **Understands** the request (extracts items, quantities, urgency, customer identity).
2. **Checks** product availability and realistic delivery windows.
3. **Calculates** pricing using the correct tier, volume discounts, and applicable policies.
4. **Evaluates** risk (credit limit, margin, unusual patterns) and decides: auto-approve, flag, or escalate to a human.
5. **Produces** a validated quotation or purchase order — ready to send or confirm.

The guiding principle: **AI interprets, reasons, and orchestrates; authoritative tools and deterministic business logic calculate and execute.**

---

## High-Level Architecture

```
Customer Request
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                     NexDeal AI Orchestrator                 │
│                                                             │
│   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐  │
│   │  Request     │   │  Product &   │   │  Pricing &    │  │
│   │  Understanding│──▶│  Availability│──▶│  Policy Agent │  │
│   │  Agent       │   │  Agent       │   │               │  │
│   └──────────────┘   └──────────────┘   └───────┬───────┘  │
│                                                  │          │
│                                          ┌───────▼───────┐  │
│                                          │  Quote &      │  │
│                                          │  Risk Agent   │  │
│                                          └───────┬───────┘  │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                    ┌──────────────────────────────▼──────────────────────────────┐
                    │             Human-in-the-loop Review (if flagged)            │
                    └─────────────────────────────────────────────────────────────┘
                                                   │
                                          Validated Quote / Order
```

All agents are built on **Microsoft Foundry** using the **Azure AI Projects SDK**.  
Agents use **Entra ID** for authentication (no hard-coded keys anywhere).

---

## Current Status — Phase 0: Foundation

**Phase 0 is the only phase currently implemented locally.**

| Component | Status |
|-----------|--------|
| Python project structure | ✅ Done |
| Configuration loader (`app/config.py`) | ✅ Done |
| Foundry connectivity smoke test (`app/main.py`) | ✅ Done |
| Unit tests (`tests/test_config.py`) | ✅ Done |
| Azure AI Projects SDK installed | ✅ Done |
| Entra ID authentication via `az login` | ✅ Done |

Phase 0 proves that the **local Python environment can authenticate with Microsoft Foundry and call the deployed model using direct Responses API inference** — no agents yet.

---

## What Is Already in Azure

The following Azure resources are already created and configured (Azure for Students subscription):

| Resource | Detail |
|----------|--------|
| Azure subscription | Azure for Students ($100 credit) |
| Region | Korea Central |
| Foundry resource | Created |
| Foundry project | Created |
| Model deployment | `gpt-4.1-mini` — Global Standard — already deployed |

> **Cost control:** No monitoring resources, Application Insights, storage accounts, or additional deployments have been created. The Phase 0 smoke test uses the existing `gpt-4.1-mini` deployment exclusively.

---

## What Is NOT Yet Implemented

The following are **planned for future phases** and do **not** exist yet:

- [ ] **Four specialised AI agents** (Request Understanding, Product & Availability, Pricing & Policy, Quote & Risk)
- [ ] **Business tools** (inventory lookup, pricing engine, credit-check, order creation)
- [ ] **Synthetic training / evaluation data**
- [ ] **Agent orchestration layer**
- [ ] **Human-in-the-loop approval workflow**
- [ ] **Evaluation and tracing** (Azure AI evaluation, OpenTelemetry)
- [ ] **Hosted Agent deployment** (containerised agent runtime on Foundry)
- [ ] **Frontend** (web UI or Teams integration)

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | Project uses `azure-ai-projects>=2.5.0` which requires Python ≥ 3.10 |
| Windows PowerShell | Tested on Windows 11 with PowerShell 5.1+ |
| Azure CLI | Install from https://aka.ms/installazurecliwindows |
| Active Azure account | Must have access to the Foundry project |
| `.venv` virtual environment | Already created at `C:\Projects\NexDeal-AI\.venv` |

---

## Setup & Running the Smoke Test

### 1. Activate the Virtual Environment

Open **Windows PowerShell** in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
```

If you see an execution-policy error, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

Verify `azure-ai-projects` version (must be ≥ 2.3.0, ideally latest):

```powershell
pip show azure-ai-projects
```

### 3. Authenticate with Azure CLI

```powershell
az login
```

This opens a browser for Entra ID sign-in. After login, confirm your subscription:

```powershell
az account show
```

### 4. Configure Environment Variables

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and fill in both values:

```dotenv
# Your Foundry project endpoint — found on the project home page in the Foundry portal
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>

# The DEPLOYMENT NAME from the "Deployed models" table → "Name" column in Foundry portal
FOUNDRY_MODEL_NAME=<your-deployment-name>
```

> **Never commit `.env`** — it is already listed in `.gitignore`.

### 5. Run the Phase 0 Smoke Test

```powershell
python app/main.py
```

Expected output on success:

```
============================================================
  NexDeal AI — Phase 0 Foundry Connectivity Smoke Test
============================================================

[OK] FOUNDRY_PROJECT_ENDPOINT : https://...
[OK] FOUNDRY_MODEL_NAME       : <your-deployment>

[OK] DefaultAzureCredential — token acquired (az login active)
[OK] AIProjectClient constructed
[OK] OpenAI client obtained via get_openai_client()

[..] Sending smoke-test prompt to '<your-deployment>' ...

[OK] Model response received:
       "NexDeal local connection is working."

============================================================
  RESULT: PASS — Foundry connectivity confirmed.
============================================================
```

---

## Running Tests

```powershell
pytest tests/ -v
```

The test suite is fully offline (no network, no `.env` required):

```
tests/test_config.py::TestSettingsLoadsCorrectly::test_both_vars_present      PASSED
tests/test_config.py::TestSettingsLoadsCorrectly::test_values_are_trimmed     PASSED
tests/test_config.py::TestSettingsLoadsCorrectly::test_settings_is_immutable  PASSED
tests/test_config.py::TestMissingVariables::test_missing_endpoint_raises      PASSED
tests/test_config.py::TestMissingVariables::test_missing_model_raises         PASSED
tests/test_config.py::TestMissingVariables::test_both_missing_raises          PASSED
tests/test_config.py::TestBlankVariables::test_blank_endpoint_raises          PASSED
tests/test_config.py::TestBlankVariables::test_blank_model_raises             PASSED
```

---

## Project Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Foundation — Python setup, configuration, Foundry connectivity | ✅ **Complete** |
| 1 | Synthetic Data — generate representative B2B request samples | ⏳ Not started |
| 2 | Tools — inventory, pricing, credit-check, order-creation | ⏳ Not started |
| 3 | Agents — four specialised Foundry agents | ⏳ Not started |
| 4 | Orchestration — multi-agent workflow, human-in-the-loop | ⏳ Not started |
| 5 | Evaluation & Tracing — quality metrics, OpenTelemetry | ⏳ Not started |
| 6 | Hosted Agent Deployment — containerised runtime on Foundry | ⏳ Not started |
| 7 | Frontend — web UI or Teams integration | ⏳ Not started |

---

*Built with Microsoft Foundry · Azure AI Projects SDK · Entra ID Authentication*
