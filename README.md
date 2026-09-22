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
6. [Current Status — Phase 3](#current-status--phase-3-request-understanding-agent)
7. [Current Status — Phase 4](#current-status--phase-4-product--availability-agent)
8. [Current Status — Phase 5](#current-status--phase-5-pricing--policy-agent)
9. [Current Status — Phase 6](#current-status--phase-6-quote--risk-agent)
10. [Current Status — Phase 7](#current-status--phase-7-multi-agent-orchestration)
11. [Current Status — Phase 8](#current-status--phase-8-human-approval-workflow)
12. [What Is Already in Azure](#what-is-already-in-azure)
13. [What Is NOT Yet Implemented](#what-is-not-yet-implemented)
14. [Prerequisites](#prerequisites)
15. [Setup & Running the Smoke Test](#setup--running-the-smoke-test)
16. [Running Tests](#running-tests)
17. [Project Roadmap](#project-roadmap)

---

## What NexDeal AI Does

A sales rep at a manufacturer receives a customer email: *"We need 500 units of item X, 200 of Y, fastest delivery, usual discount."*

NexDeal AI:

1. **Understands** the request (extracts items, quantities, specifications, customer reference, requested delivery date, services).
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
| `tests/tools/` — Full Phase 2 test suite (202 tests) | ✅ Done |

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

> **Note:** Agent orchestration and Foundry deployments for remaining agents are **not** implemented yet. Phase 2 is exclusively local Python business logic.

---

## Current Status — Phase 3: Request Understanding Agent

**Phase 3 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/models/__init__.py` — models package | ✅ Done |
| `app/models/schemas.py` — `RequestedItem` + `StructuredRequest` Pydantic schemas | ✅ Done |
| `app/agents/__init__.py` — agents package | ✅ Done |
| `app/agents/request_understanding.py` — Request Understanding Agent | ✅ Done |
| `tests/agents/test_request_understanding.py` — unit + boundary test suite (59 tests) | ✅ Done |
| `scripts/smoke_test_agent.py` — live integration smoke test | ✅ Done |
| `requirements.txt` updated with `agent-framework-foundry` and `pydantic>=2,<3` | ✅ Done |

### What the Request Understanding Agent Does

The Request Understanding Agent takes a raw, unstructured B2B customer request (email, chat message, form submission) and transforms it into a **validated `StructuredRequest`** object:

```
Free-text customer email
        │
        ▼
┌─────────────────────────────────────────────────────┐
│         Request Understanding Agent                 │
│  (FoundryChatClient + Agent + StructuredRequest)    │
└─────────────────────────────────────────────────────┘
        │
        ▼
  StructuredRequest
  ├── request_id: str | None                    (application-assigned; model returns null)
  ├── raw_request: str                          (original text preserved verbatim)
  ├── customer_reference: str | None            (customer name or company if stated)
  ├── requested_items: list[RequestedItem]
  │         ├── raw_product_reference: str      (customer's exact words, preserved verbatim)
  │         ├── product_id: str | None          (canonical ID ONLY when customer explicitly supplies one)
  │         ├── quantity: int | None            (numeric quantity requested)
  │         └── specifications: list[str]       (strict-schema 'key: value' strings, [] if none)
  ├── requested_delivery_date: str | None       (ISO 8601 when year explicit; raw phrasing or null if year unspecified)
  ├── installation_required: bool | None        (true/false/null tri-state)
  ├── requested_services: list[str]             (additional services requested, [] if none)
  ├── requested_discount_percent: float | None  (percentage only, never fixed amount)
  ├── missing_information: list[str]            (missing fulfillment details, [] if none)
  └── ambiguities: list[str]                    (conflicts/unclear statements, [] if none)
```

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Client pattern | `Agent(client=FoundryChatClient(...))` | Phase 3 code-first / direct-inference pattern; does not interfere with Phase 0's `AIProjectClient` |
| Authentication | `AzureCliCredential` | Required by project constraint (no `DefaultAzureCredential`) |
| Structured outputs | `response_format=StructuredRequest` via `agent.run(..., options={"response_format": ...})` | Agent Framework native structured outputs — no manual JSON parsing |
| Schema compliance | All fields declared with `Field(...)` (no defaults) | Foundry strict JSON Schema mode requires ALL fields in `required` |
| Nullable absence | `str \| None` type with no default | Allows model to return `null` for absent info without inventing data |
| Boundaries | No Phase 2 tool imports | Enforced by architecture test in `test_request_understanding.py` |

### Strict JSON Schema Compliance

Microsoft Foundry's strict JSON Schema mode requires every field to appear in the `required` list. In Pydantic v2, a field only appears in `required` when it has **no default value**. All nullable fields use `X | None` as the type with `Field(...)` — making them required but nullable:

```python
# ✅ Correct — appears in required, accepts null
customer_reference: str | None = Field(..., description="...")

# ❌ Wrong — would NOT appear in required, silently omitted
customer_reference: str | None = None
```

**Note:** `specifications` uses `list[str]` (not `dict[str, str]`) because Foundry strict mode
rejects the `additionalProperties` schema that `dict[str, str]` generates.
Specifications are encoded as `"key: value"` strings (e.g. `["port_count: 48", "colour: black"]`).

This is validated by `TestJsonSchemaCompliance` in the unit test suite.

### Phase 3 Boundaries (Enforced by Tests)

The Request Understanding Agent operates strictly within Phase 3 scope:
- ✅ Extracts `customer_reference`, `requested_items`, `requested_delivery_date`, `installation_required`, `requested_discount_percent`, `requested_services`, `missing_information`, `ambiguities`
- ✅ Preserves customer's exact wording in `raw_product_reference` and `raw_request`
- ✅ Returns null/[] for absent information instead of inventing data
- ✅ Sets `product_id` only when the customer explicitly supplies a canonical identifier
- ❌ Does NOT infer `product_id` from descriptive product text
- ❌ Does NOT check inventory (`app.tools.inventory`)
- ❌ Does NOT calculate prices or discounts (`app.tools.pricing`)
- ❌ Does NOT apply business policy rules (`app.tools.policies`)
- ❌ Does NOT check delivery feasibility (`app.tools.fulfilment`)

These boundaries are enforced by the `TestAgentModuleBoundaries` test class.

### How to Run the Phase 3 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/agents/test_request_understanding.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration smoke test (requires .env and az login):
python scripts/smoke_test_agent.py
```

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

## Current Status — Phase 4: Product & Availability Agent

**Phase 4 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/models/schemas.py` — `FulfilmentItemResult` + `FulfilmentResult` Pydantic schemas | ✅ Done |
| `app/agents/product_availability.py` — Product & Availability Agent | ✅ Done |
| `app/agents/__init__.py` — exports `check_availability`, `check_availability_sync` | ✅ Done |
| `tests/agents/test_product_availability.py` — unit + boundary test suite (99 tests) | ✅ Done |
| `scripts/smoke_test_product_availability.py` — live integration smoke test | ✅ Done |

### What the Product & Availability Agent Does

The Product & Availability Agent receives a validated `StructuredRequest` from Phase 3 and determines whether each requested product can be fulfilled:

```
  StructuredRequest (Phase 3 output)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│         Product & Availability Agent                    │
│  (FoundryChatClient + Agent + Phase 2 Tools)            │
│                                                         │
│  Calls:                                                 │
│   • search_products  — resolve descriptive references   │
│   • get_product      — confirm authoritative product    │
│   • check_inventory  — stock availability               │
│   • check_delivery_feasibility — delivery date check    │
│   • check_installation_availability — install check     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
  FulfilmentResult
  ├── request_id: str | None            (echoed from StructuredRequest)
  ├── customer_reference: str | None    (echoed from StructuredRequest)
  ├── items: list[FulfilmentItemResult]
  │       ├── raw_product_reference: str          (customer's exact words)
  │       ├── resolved_product_id: str | None     (authoritative ID or null)
  │       ├── product_resolution_status: Literal  (RESOLVED | AMBIGUOUS | NOT_FOUND)
  │       ├── requested_quantity: int | None
  │       ├── available_quantity: int | None      (authoritative from check_inventory)
  │       ├── inventory_status: Literal           (AVAILABLE | PARTIAL | UNAVAILABLE | NOT_EVALUATED)
  │       ├── requested_delivery_date: str | None (echoed from StructuredRequest)
  │       ├── delivery_status: Literal            (FEASIBLE | INFEASIBLE | NOT_REQUESTED | NEEDS_CLARIFICATION | NOT_EVALUATED)
  │       ├── installation_required: bool | None
  │       ├── installation_status: Literal        (AVAILABLE | UNAVAILABLE | NOT_REQUESTED | NEEDS_CLARIFICATION | NOT_EVALUATED)
  │       ├── installation_price: str | None      (decimal string, e.g. "450.00")
  │       └── issues: list[str]
  ├── overall_status: Literal           (application-derived — see precedence below)
  ├── clarification_required: bool
  └── issues: list[str]
```

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Client pattern | `Agent(client=FoundryChatClient(...), tools=[...])` | Same code-first pattern as Phase 3; tools registered via `@tool` decorator |
| Authentication | `AzureCliCredential` | Same as Phase 3; no `DefaultAzureCredential` |
| Tool registration | `@tool` decorator on wrapper functions | Agent Framework native pattern; generates JSON Schema automatically |
| Structured output | `response_format=FulfilmentResult` | Foundry strict JSON Schema; all 6 + 12 fields in `required` |
| `installation_price` as string | `str` (e.g. `"450.00"`) | Avoids `Decimal → float → JSON` precision issues |
| `reference_date` injection | Explicit `date` parameter on `check_availability()` | No clock calls — fully deterministic for testing |
| `overall_status` enforcement | Python `_derive_overall_status()` overwrites LLM value | LLM values for status fields are NOT trusted; deterministic logic always wins |

### Status Precedence (`overall_status` derivation)

The application layer computes `overall_status` deterministically after the agent responds.
Precedence from **highest to lowest**:

| Priority | Status | Triggered when |
|----------|--------|----------------|
| 1 | `CLARIFICATION_REQUIRED` | Any item unresolved (AMBIGUOUS/NOT_FOUND) OR delivery date is incomplete | 
| 2 | `INSTALLATION_UNAVAILABLE` | Any resolved item where installation is required but unavailable |
| 3 | `DELIVERY_CONFLICT` | Any item with infeasible delivery date |
| 4 | `UNAVAILABLE` | Any item with zero stock |
| 5 | `PARTIAL` | Any item with partial stock |
| 6 | `READY` | All required checks pass |

### Phase 4 Boundaries (Enforced by Tests)

The Product & Availability Agent operates strictly within Phase 4 scope:

**Allowed tools** (Phase 2 product/fulfilment domain only):
- ✅ `search_products` — keyword search to resolve descriptive product references
- ✅ `get_product` — confirm authoritative product record by ID
- ✅ `check_inventory` — authoritative stock availability
- ✅ `check_delivery_feasibility` — delivery date feasibility with explicit reference_date
- ✅ `check_installation_availability` — installation availability and price

**Forbidden tools** (enforced by architecture tests):
- ❌ `calculate_customer_price`, `calculate_tax`, `calculate_discount`, `calculate_margin` (pricing)
- ❌ `check_discount_policy`, `check_margin_policy`, `check_approval_policy` (policies)
- ❌ `get_customer`, `check_customer_account_status`, `get_customer_credit_info` (customers)

These boundaries are enforced by `TestArchitecturalBoundaries` in the unit test suite.

### How to Run the Phase 4 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/agents/test_product_availability.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration smoke test (requires .env and az login):
python scripts/smoke_test_product_availability.py
```

---

## Current Status — Phase 5: Pricing & Policy Agent

**Phase 5 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/models/schemas.py` — `PricingLineItem` + `PricingPolicyResult` schemas | ✅ Done |
| `app/agents/pricing_policy.py` — Pricing & Policy Agent logic | ✅ Done |
| `app/agents/__init__.py` — exports `run_pricing_policy` | ✅ Done |
| `tests/agents/test_pricing_policy.py` — comprehensive test suite | ✅ Done |
| `scripts/smoke_test_pricing_policy.py` — live integration smoke test | ✅ Done |

### What the Pricing & Policy Agent Does

The Pricing & Policy Agent takes the `StructuredRequest` (Phase 3) and `FulfilmentResult` (Phase 4), and produces a fully priced quotation while enforcing all business rules:

```
  StructuredRequest + FulfilmentResult
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│             Pricing & Policy Agent                  │
│  (FoundryChatClient + Agent + Phase 2 Tools)        │
│                                                     │
│  Calls:                                             │
│   • search_customers                                │
│   • get_customer                                    │
│   • calculate_customer_price                        │
│   • check_discount_policy                           │
│   • check_credit_policy                             │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
          PricingPolicyResult
```

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Calculation override | Python calculates final Math | The LLM only drafts; python logic iterates the authoritative Phase 4 items and uses Phase 2 deterministic tools to calculate final numbers. |
| Discount Policy | Applies strict limit | Discounts above tier limits trigger a policy violation flag, but may be overridable by approvals. |
| Cost missing | Overall margin is `None` | The current data models do not supply an authoritative cost base. We do not invent costs, so margin triggers force `CLARIFICATION_REQUIRED`. |
| Missing Installation | Excluded from calculation | Installation price is processed purely based on the deterministic output of Phase 4. |

### Status Precedence

Precedence from **highest to lowest**:

| Priority | Status | Triggered when |
|----------|--------|----------------|
| 1 | `CREDIT_BLOCKED` | Credit limit exceeded or account restricted. |
| 2 | `POLICY_VIOLATION_FATAL` | Margin falls below the absolute minimum limit. |
| 3 | `CLARIFICATION_REQUIRED` | Incomplete data, skipped items, or lack of authoritative cost to evaluate approval triggers. |
| 4 | `APPROVAL_REQUIRED` | Valid quote but requires manager/director/board approval based on discounts. |
| 5 | `READY_FOR_QUOTE` | All commercial and credit rules pass cleanly. |

### How to Run the Phase 5 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/agents/test_pricing_policy.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration smoke test (requires .env and az login):
python scripts/smoke_test_pricing_policy.py
```

---

## Current Status — Phase 6: Quote & Risk Agent

**Phase 6 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/models/schemas.py` — `QuoteRiskResult` schema | ✅ Done |
| `app/agents/quote_risk.py` — Quote & Risk Agent logic | ✅ Done |
| `app/agents/__init__.py` — exports `run_quote_risk` | ✅ Done |
| `tests/agents/test_quote_risk.py` — comprehensive test suite | ✅ Done |
| `scripts/smoke_test_quote_risk.py` — live integration smoke test | ✅ Done |

### What the Quote & Risk Agent Does

The Quote & Risk Agent acts as the final decision point before human review or quote dispatch. It receives the outputs of all three previous agents and determines the definitive `quote_decision` and `risk_indicators`.

```
  StructuredRequest + FulfilmentResult + PricingPolicyResult
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│               Quote & Risk Agent                    │
│   (FoundryChatClient + Agent + NO Phase 2 Tools)    │
│                                                     │
│  Synthesizes data and drafts reasons.               │
│  Python logic strictly reconciles the final status. │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
           QuoteRiskResult
```

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Application Authoritative | Python enforces decision precedence | The Quote & Risk Agent synthesizes facts into natural language reasons, but the final `quote_decision` is dictated deterministically by the application to prevent LLM hallucinations. |
| Risk Indicator Mapping | Strict derivation | `risk_indicators` are compiled directly from upstream flags (e.g. `inventory_status == "UNAVAILABLE"` maps strictly to `INVENTORY_UNAVAILABLE`). |
| No Phase 2 Tools | Agent has empty `tools` list | This agent is a pure synthesis layer over structured data. Upstream math and inventory facts are immutable. |

### Deterministic Precedence

The final `quote_decision` follows this strict fallback order (highest to lowest):
1. `REQUEST_CANNOT_BE_FULFILLED` — if Phase 4 is `UNAVAILABLE` or Phase 5 is `CREDIT_BLOCKED`/`POLICY_VIOLATION_FATAL`.
2. `CUSTOMER_CLARIFICATION_REQUIRED` — if Phase 3 has missing info/ambiguities, Phase 4 is `CLARIFICATION_REQUIRED`/`PARTIAL`/`DELIVERY_CONFLICT`/`INSTALLATION_UNAVAILABLE`, or Phase 5 is `CLARIFICATION_REQUIRED`.
3. `HUMAN_APPROVAL_REQUIRED` — if Phase 5 requires manager, director, or board approval.
4. `QUOTE_READY` — only if all previous conditions pass cleanly.

### How to Run the Phase 6 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/agents/test_quote_risk.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration smoke test (requires .env and az login):
python scripts/smoke_test_quote_risk.py
```

---

## Current Status — Phase 7: Multi-Agent Orchestration

**Phase 7 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/workflows/orchestrator.py` — Graph-based WorkflowBuilder orchestration | ✅ Done |
| `tests/orchestration/test_workflow.py` — comprehensive test suite | ✅ Done |
| `scripts/smoke_test_workflow.py` — live integration smoke test | ✅ Done |

### What the Orchestration Workflow Does

The Phase 7 Orchestration pipeline connects the four Specialized Agents (Phase 3 through Phase 6) into a strongly typed graph workflow using Microsoft `agent-framework`'s `WorkflowBuilder`. It avoids conversational/message-history chaining in favor of strictly passing the Pydantic application contracts (`StructuredRequest`, `FulfilmentResult`, `PricingPolicyResult`, `QuoteRiskResult`).

```
  WorkflowInput (raw_request + reference_date)
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Phase 3 Executor (Request Understanding Agent)     │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Phase 4 Executor (Product & Availability Agent)    │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Phase 5 Executor (Pricing & Policy Agent)          │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Phase 6 Executor (Quote & Risk Agent)              │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
           QuoteRiskResult (Final Workflow Output)
```

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| API Selection | `WorkflowBuilder` (agent-framework) | Provides deterministic, typed graph orchestration without experimental annotations. |
| Object Propagation | `WorkflowContext.set_state()` | Maintains strict typing without inventing a redundant monolithic envelope schema just for workflow messaging. |
| Reference Date | Explicit Injection | `reference_date` is strictly provided by the client application (caller) and travels down the graph to Phase 4. `datetime.now()` is forbidden. |
| Business vs Technical Failures | Complete traversal for business outcomes | Valid business blockers (`UNAVAILABLE`, `PARTIAL`, `CREDIT_BLOCKED`) proceed through the entire pipeline because each subsequent phase requires full lifecycle processing to generate accurate risk/reason logs. Technical exceptions halt the pipeline. |
| Business Logic | Existing Runners Only | Executes the exact same `run_*` agent entry points. No duplicated Math or agent rules are built into the orchestrator. |

### How to Run the Phase 7 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/orchestration/test_workflow.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration end-to-end smoke test (requires .env and az login):
python scripts/smoke_test_workflow.py
```

---

## Current Status — Phase 8: Human Approval Workflow

**Phase 8 is complete. No new Azure resources were created or modified.**

| Component | Status |
|-----------|--------|
| `app/models/schemas.py` — `ApprovalRequest`, `ApprovalResponse`, `HumanApprovalResult` schemas | ✅ Done |
| `app/workflows/orchestrator.py` — `ApprovalGateExecutor` implementation with `ctx.request_info` | ✅ Done |
| `tests/orchestration/test_human_approval.py` — isolated human-in-the-loop tests | ✅ Done |
| `scripts/smoke_test_human_approval.py` — live pipeline and HITL smoke test | ✅ Done |

### What the Human Approval Workflow Does

The Human Approval Workflow is an explicit, deterministic gate added to the end of the Phase 7 orchestration graph. It enforces the `HUMAN_APPROVAL_REQUIRED` decision made by the Phase 6 Quote & Risk Agent.

When an approval is required (e.g., `MANAGER_APPROVAL_REQUIRED`), the workflow **pauses** execution, emits a typed `ApprovalRequest` to an external reviewer, and waits. Once a human responds with a typed `ApprovalResponse`, the workflow resumes and produces a final deterministic `HumanApprovalResult`.

### Architecture & Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| HITL Mechanism | `ctx.request_info(..., ApprovalResponse)` | Native Microsoft `agent-framework` API for pausing and resuming execution with strongly typed contracts. |
| Approval State | Pending / Paused | Rather than returning a fake "pending" output, the workflow actually suspends execution. It returns a `WorkflowRunResult` event stream that clients can inspect for requests. |
| Deterministic Resume | `@response_handler` | The framework resumes through `workflow.run(responses=...)`, and Python logic strictly enforces that `approved=True` becomes `APPROVED` and `approved=False` becomes `REJECTED`. The LLM cannot auto-approve or override a rejection. |
| Scope Limitations | No Persistence/UI | Phase 8 strictly implements the logical orchestration gate. External APIs, databases, email notifications, and frontend UIs are deliberately deferred to future phases. |

### How to Run the Phase 8 Tests

```powershell
# Unit tests only (offline — no API call):
pytest tests/orchestration/test_human_approval.py -v

# Full suite (all phases, still offline):
pytest tests/ -v

# Live integration end-to-end smoke test (requires .env and az login):
python scripts/smoke_test_human_approval.py
```

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

- [x] ~~**Synthetic data**~~ — ✅ Completed in Phase 1
- [x] ~~**Business tools**~~ — ✅ Completed in Phase 2 (`app/tools/`)
- [x] ~~**Request Understanding Agent**~~ — ✅ Completed in Phase 3 (`app/agents/request_understanding.py`)
- [x] ~~**Product & Availability Agent**~~ — ✅ Completed in Phase 4 (`app/agents/product_availability.py`)
- [x] ~~**Pricing & Policy Agent**~~ — ✅ Completed in Phase 5 (`app/agents/pricing_policy.py`)
- [x] ~~**Quote & Risk Agent**~~ — ✅ Completed in Phase 6 (`app/agents/quote_risk.py`)
- [x] ~~**Agent orchestration layer**~~ — ✅ Completed in Phase 7 (`app/workflows/orchestrator.py`)
- [x] ~~**Human-in-the-loop approval workflow**~~ — ✅ Completed in Phase 8
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

Total: **420 tests** across Phases 0–4.

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

The Phase 2 suite (202 tests) validates:
- All six tool modules import and function correctly against real Phase 1 JSON data
- Exact arithmetic correctness (`calculate_subtotal`, `calculate_discount`, `calculate_margin`)
- `decimal.Decimal` used throughout pricing (no float rounding errors)
- Policy thresholds read from `business_rules.json` at runtime (tests explicitly fail if Python hardcodes a different limit)
- Correct enum outcomes for all policy checks (`AVAILABLE`, `FEASIBLE`, `WITHIN_LIMIT`, `CREDIT_OK`, etc.)
- Determinism: identical inputs always produce identical outputs
- Cross-tool consistency: `get_product` price equals `calculate_subtotal` at quantity=1; customer `discount_limit` is always within tier cap

### Phase 3 — Agent Tests (`tests/agents/test_request_understanding.py`)

Run in isolation:

```powershell
pytest tests/agents/test_request_understanding.py -v
```

The Phase 3 suite (59 tests, fully offline) validates:
- `RequestedItem` and `StructuredRequest` Pydantic construction and field semantics
- All nullable fields accept `None` but still fail validation when entirely omitted (required in schema)
- **Strict JSON Schema compliance**: every field appears in `required`; nullable fields use `anyOf:[type, null]` not defaults; `specifications` uses `list[str]` strict-schema representation
- Product ID contract: canonical IDs preserved when supplied by customer; null when product is descriptive
- Delivery date contract: ISO 8601 only when year is explicit; raw phrasing or null without guessing a year when year is unspecified
- Discount contract: percentage-only discounts captured; fixed cash amounts not converted to percentage
- Tri-state installation flag: explicit true, explicit false, or null when unmentioned
- Architectural boundaries: no Phase 2 tool imports in the agent module
- `AzureCliCredential` used (not `DefaultAzureCredential`)
- `FoundryChatClient` + `Agent` pattern used (not bare `AIProjectClient`)

Live smoke test (requires `.env` and `az login`):

```powershell
python scripts/smoke_test_agent.py
```

The smoke test sends a deliberately messy B2B customer email to the deployed Foundry model and validates the returned `StructuredRequest`.

### Phase 4 — Agent Tests (`tests/agents/test_product_availability.py`)

Run in isolation:

```powershell
pytest tests/agents/test_product_availability.py -v
```

The Phase 4 suite (99 tests, fully offline) validates:
- `FulfilmentItemResult` and `FulfilmentResult` Pydantic construction and field semantics
- All 12 + 6 fields appear in JSON schema `required` list (Foundry strict mode)
- Literal status fields reject invalid values at construction time
- `_derive_overall_status` precedence: all 6 outcomes with mixed-item scenarios
- **Tool wrapper behaviour**: `tool_search_products`, `tool_get_product`, `tool_check_inventory`, `tool_check_delivery_feasibility`, `tool_check_installation_availability` — happy path, error handling, type safety
- **Price field safety**: `unit_price` never appears in tool wrapper responses; `installation_price` is always a decimal string
- Application-level `overall_status` enforcement: LLM output is overwritten by Python logic
- Architectural boundaries: no pricing/policy/customer tool imports
- `AzureCliCredential` used (not `DefaultAzureCredential`)
- `reference_date` is a keyword-only parameter (clock injection, not `date.today()`)
- Tool list contains exactly the 5 allowed Phase 2 tools

Live smoke test (requires `.env` and `az login`):

```powershell
python scripts/smoke_test_product_availability.py
```

The smoke test constructs a `StructuredRequest` with two items (one descriptive, one with an explicit `product_id`), calls the live Foundry agent, and asserts the returned `FulfilmentResult` structure and per-item resolution logic.

---

## Project Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Foundation — Python setup, configuration, Foundry connectivity | ✅ **Complete** |
| **1** | Synthetic Data — deterministic B2B products, customers, business rules | ✅ **Complete** |
| **2** | Tools — deterministic business logic: inventory, pricing, policies, fulfilment | ✅ **Complete** |
| **3** | Request Understanding Agent — structured extraction of customer requests | ✅ **Complete** |
| **4** | Product & Availability Agent — product resolution, inventory & delivery checks | ✅ **Complete** |
| **5** | Pricing & Policy Agent — pricing, discount, margin, credit evaluation | ✅ **Complete** |
| **6** | Quote & Risk Agent — final quotation, risk scoring, human escalation | ✅ **Complete** |
| **7** | Orchestration — multi-agent workflow | ✅ **Complete** |
| **8** | Human Approval Workflow — human-in-the-loop | ✅ **Complete** |
| 9 | Evaluation & Tracing — quality metrics, OpenTelemetry | ⏳ Not started |
| 10 | Hosted Agent Deployment — containerised runtime on Foundry | ⏳ Not started |
| 11 | Frontend — web UI or Teams integration | ⏳ Not started |

---

*Built with Microsoft Foundry · Azure AI Projects SDK · Entra ID Authentication*
