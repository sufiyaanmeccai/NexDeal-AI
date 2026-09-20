# NexDeal AI

> **B2B Quotation & Order Processing — Powered by Microsoft Foundry AI Agents**

NexDeal AI transforms messy B2B customer requests (emails, messages, faxes) into validated quotations and orders through a coordinated team of specialised AI agents. It eliminates manual data entry, enforces pricing and compliance rules, and routes edge-cases to human review — all within a single, auditable workflow.

---

## Table of Contents

1. [What NexDeal AI Does](#what-nexdeal-ai-does)
2. [High-Level Architecture](#high-level-architecture)
3. [Current Status — Phase 0](#current-status--phase-0-foundation)
4. [Current Status — Phase 1](#current-status--phase-1-synthetic-data)
5. [Current Status — Phase 2](#current-status--phase-2-deterministic-business-tools)
6. [What Is Already in Azure](#what-is-already-in-azure)
7. [What Is NOT Yet Implemented](#what-is-not-yet-implemented)
8. [Prerequisites](#prerequisites)
9. [Setup & Running the Smoke Test](#setup--running-the-smoke-test)
10. [Running Tests](#running-tests)
11. [Project Roadmap](#project-roadmap)

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

**Phase 0 is complete and fully preserved.**

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

## Current Status — Phase 1: Synthetic Data

**Phase 1 is complete. No Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `data/products.json` — 12 B2B products | ✅ Done |
| `data/customers.json` — 8 B2B customer profiles | ✅ Done |
| `data/business_rules.json` — 7 policy sections | ✅ Done |
| `tests/data/test_data_integrity.py` — integrity test suite | ✅ Done |

### What the Synthetic Dataset Represents

The three JSON files together form the **authoritative static data layer** for NexDeal AI:

| File | Records | Purpose |
|------|---------|----------|
| `data/products.json` | 12 products | B2B product catalogue (Servers, Networking, Storage, Security, Industrial, Power, Cabling) |
| `data/customers.json` | 8 customers | B2B account profiles across tiers, regions, industries, and account statuses |
| `data/business_rules.json` | 7 policy sections | Pricing, discount, margin, approval, delivery, installation, and credit policies |

### Why Deterministic Synthetic Data?

- **Reproducibility**: Every test, agent run, and evaluation produces identical results regardless of environment or date.
- **No external dependencies**: Data loading requires no network access, no database, and no Azure credentials.
- **Controlled edge cases**: Customer profiles deliberately include blocked accounts (`credit_hold`, `suspended`), `risk` payment histories, and tight credit limits so future tools and agents can be stress-tested against known inputs.
- **Future-safe**: When Phase 2 deterministic business tools are built (inventory lookup, pricing engine, credit check), they will read these same files — no schema migration needed.

### How to Run the Data Integrity Tests

```powershell
# From the project root with .venv activated:
pytest tests/data/test_data_integrity.py -v
```

Or run the full suite (Phase 0 config tests + Phase 1 data tests together):

```powershell
pytest tests/ -v
```

> **Note:** Agents, business tools, orchestration, and Foundry deployments are **not** implemented yet. Phase 1 is exclusively local static data.

---

## Current Status — Phase 2: Deterministic Business Tools

**Phase 2 is complete. No Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/tools/data_loader.py` — JSON data loader | ✅ Done |
| `app/tools/products.py` — Product lookup & search | ✅ Done |
| `app/tools/customers.py` — Customer lookup & status | ✅ Done |
| `app/tools/inventory.py` — Inventory availability check | ✅ Done |
| `app/tools/fulfilment.py` — Delivery feasibility & installation | ✅ Done |
| `app/tools/pricing.py` — Pricing & discount arithmetic | ✅ Done |
| `app/tools/policies.py` — Business policy evaluation | ✅ Done |
| `tests/tools/` — Full Phase 2 test suite (189 tests) | ✅ Done |

### Why a Separate Business Tools Layer?

NexDeal AI enforces a strict separation between **AI reasoning** and **authoritative calculation**:

- **Agents** (future phases) interpret natural language and make decisions.
- **Business tools** (this phase) perform all arithmetic, lookups, and policy checks using static JSON data.

This means no agent can hallucinate a price, discount, or credit limit — it must call a tool to retrieve the authoritative value. The tools are pure Python functions with no LLM calls, no Azure connections, and no side effects.

### Tool Modules

| Module | Public Functions | Reads From |
|--------|-----------------|------------|
| `data_loader.py` | `get_all_products`, `get_product_by_id`, `get_all_customers`, `get_customer_by_id`, `get_business_rules`, and per-section accessors | All three JSON files |
| `products.py` | `get_product`, `search_products` | `products.json` |
| `customers.py` | `get_customer`, `get_customer_pricing_tier`, `check_customer_account_status`, `get_customer_credit_info` | `customers.json` |
| `inventory.py` | `check_inventory` → `InventoryStatus` enum | `products.json` |
| `fulfilment.py` | `check_delivery_feasibility`, `check_installation_availability`, `get_installation_price` | `products.json`, `business_rules.json` |
| `pricing.py` | `calculate_subtotal`, `calculate_discount`, `calculate_discounted_total`, `calculate_customer_price`, `calculate_tax`, `calculate_margin` | `products.json`, `customers.json`, `business_rules.json` |
| `policies.py` | `check_discount_policy`, `check_margin_policy`, `check_approval_policy`, `check_credit_policy` | `customers.json`, `business_rules.json` |

### Design Principles

- **No hardcoded constants**: All thresholds (discount caps, margin minimums, approval levels, credit utilisation limits) are read from `business_rules.json` at call time. Changing a policy requires only editing the JSON, not the Python.
- **`decimal.Decimal` for all money**: Eliminates floating-point rounding errors in pricing and discount arithmetic (ROUND_HALF_UP convention).
- **Explicit `reference_date`**: Delivery feasibility accepts a caller-supplied date rather than `datetime.now()`, guaranteeing deterministic test results.
- **Typed outcomes**: Policy results use string enums (`InventoryStatus`, `DeliveryFeasibility`, `DiscountPolicyOutcome`, etc.) so future agents get machine-readable signals, not freeform text.
- **Read-only**: No tool modifies JSON files or holds mutable global state accessible to callers.

### How to Run the Phase 2 Tool Tests

```powershell
# Individual module tests:
pytest tests/tools/test_products.py -v
pytest tests/tools/test_customers.py -v
pytest tests/tools/test_inventory.py -v
pytest tests/tools/test_fulfilment.py -v
pytest tests/tools/test_pricing.py -v
pytest tests/tools/test_policies.py -v

# Full Phase 2 suite:
pytest tests/tools/ -v

# Complete suite (all phases):
pytest tests/ -v
```

> **Note:** AI agents, agent orchestration, and Foundry deployments are **not** implemented yet. Phase 2 is exclusively local Python business logic.

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

- [x] ~~**Synthetic data**~~ — ✅ Completed in Phase 1
- [x] ~~**Business tools**~~ — ✅ Completed in Phase 2 (`app/tools/`)
- [ ] **Four specialised AI agents** (Request Understanding, Product & Availability, Pricing & Policy, Quote & Risk)
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

The full test suite is **fully offline** (no network, no `.env` required).

### Phase 0 — Configuration Tests (`tests/test_config.py`)

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

### Phase 1 — Data Integrity Tests (`tests/data/test_data_integrity.py`)

Run in isolation:

```powershell
pytest tests/data/test_data_integrity.py -v
```

The data integrity suite validates:
- All three JSON files exist and parse as valid JSON
- `product_id` and `customer_id` uniqueness
- Numeric constraints (`unit_price > 0`, `inventory >= 0`, `lead_time_days >= 0`, etc.)
- Controlled categorical values (tiers, payment histories, account statuses, product statuses)
- Business rule threshold ordering (e.g., enterprise discount cap ≥ premium ≥ standard)
- Logical approval threshold ordering (`auto < manager < director < board`)
- Cross-file consistency (customer tiers match discount policy, discount limits within tier caps)

### Phase 2 — Business Tool Tests (`tests/tools/`)

Run in isolation:

```powershell
pytest tests/tools/ -v
```

The Phase 2 suite (189 tests) validates:
- All six tool modules import and function correctly against real Phase 1 JSON data
- Exact arithmetic correctness (`calculate_subtotal`, `calculate_discount`, `calculate_margin`)
- `decimal.Decimal` used throughout pricing (no float rounding errors)
- Policy thresholds read from `business_rules.json` at runtime (tests explicitly fail if Python hardcodes a different limit)
- Correct enum outcomes for all policy checks (`AVAILABLE`, `FEASIBLE`, `WITHIN_LIMIT`, `CREDIT_OK`, etc.)
- Determinism: identical inputs always produce identical outputs
- Cross-tool consistency: `get_product` price equals `calculate_subtotal` at quantity=1; customer `discount_limit` is always within tier cap

---

## Project Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Foundation — Python setup, configuration, Foundry connectivity | ✅ **Complete** |
| **1** | Synthetic Data — deterministic B2B products, customers, business rules | ✅ **Complete** |
| **2** | Tools — deterministic business logic: inventory, pricing, policies, fulfilment | ✅ **Complete** |
| 3 | Agents — four specialised Foundry agents | ⏳ Not started |
| 4 | Orchestration — multi-agent workflow, human-in-the-loop | ⏳ Not started |
| 5 | Evaluation & Tracing — quality metrics, OpenTelemetry | ⏳ Not started |
| 6 | Hosted Agent Deployment — containerised runtime on Foundry | ⏳ Not started |
| 7 | Frontend — web UI or Teams integration | ⏳ Not started |

---

*Built with Microsoft Foundry · Azure AI Projects SDK · Entra ID Authentication*
