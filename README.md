# NexDeal AI

> **B2B Quotation & Order Processing — Powered by Microsoft Foundry AI Agents**

## Overview
NexDeal AI transforms messy B2B customer requests (emails, messages, or form submissions) into validated quotations and orders through a coordinated team of specialised AI agents. It eliminates manual data entry, enforces pricing and compliance rules, and routes edge-cases to human review — all within a single, auditable workflow.

## Business Problem
A sales rep at a manufacturer receives a customer email: *"We need 500 units of item X, 200 of Y, fastest delivery, usual discount."*

Traditionally, this requires manual extraction, checking multiple inventory systems, calculating volume discounts, validating credit limits, and sending emails back and forth for clarification or manager approval.

## Solution
NexDeal AI automates this process:
1. **Understands** the request (extracts items, quantities, specifications, customer reference, requested delivery date, services).
2. **Checks** product availability and realistic delivery windows.
3. **Calculates** pricing using the correct tier, volume discounts, and applicable policies.
4. **Evaluates** risk (credit limit, margin, unusual patterns) and determines whether the request is quote-ready, requires clarification, requires human approval, or cannot be fulfilled.
5. **Produces** a validated quotation decision, with clarification or human-review routing when required.

## Core Architectural Principle
The guiding principle of NexDeal AI is:
**AI interprets, reasons, and orchestrates; authoritative tools and deterministic business logic calculate and execute.**

## Multi-Agent Architecture
NexDeal AI utilizes a multi-agent architecture built on Microsoft Foundry using the Azure AI Projects SDK.

### 1. Request Understanding Agent
Takes a raw, unstructured B2B customer request (email, chat message, form submission) and transforms it into a validated `StructuredRequest` object, strictly complying with JSON schema. It preserves the customer's exact wording and flags missing information or ambiguities.

### 2. Product & Availability Agent
Receives the `StructuredRequest` and determines whether each requested product can be fulfilled. It uses deterministic business tools to search products, check inventory, and assess delivery feasibility and installation availability.

### 3. Pricing & Policy Agent
Takes the `StructuredRequest` and `FulfilmentResult` and produces a fully priced quotation while enforcing all business rules. It calculates prices deterministically via Python tools and applies strict credit and discount policies.

### 4. Quote & Risk Agent
Acts as the final decision point before human review or quote dispatch. It synthesizes the data and drafts reasons. Python logic strictly reconciles the final status into one of four states: `QUOTE_READY`, `HUMAN_APPROVAL_REQUIRED`, `CUSTOMER_CLARIFICATION_REQUIRED`, or `REQUEST_CANNOT_BE_FULFILLED`.

## Workflow
All agents are orchestrated into a strongly typed graph workflow using Microsoft `agent-framework`'s `WorkflowBuilder`. It avoids conversational/message-history chaining in favor of strictly passing the Pydantic application contracts.

```text
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
                    │             Human-in-the-loop Review (if flagged)           │
                    └─────────────────────────────────────────────────────────────┘
                                                   │
                                          Validated Quote Decision
```

## Deterministic Business Tools
NexDeal AI enforces a strict separation between **AI reasoning** and **authoritative calculation**.
Agents interpret natural language and make decisions. Business tools perform all arithmetic, lookups, and policy checks using static JSON data (`data/`). No agent can hallucinate a price, discount, or credit limit — it must call a pure Python tool to retrieve the authoritative value.

## Human-in-the-Loop
The Human Approval Workflow is an explicit, deterministic gate added to the end of the orchestration graph. It enforces the `HUMAN_APPROVAL_REQUIRED` decision made by the Quote & Risk Agent. When an approval is required, the workflow pauses execution, emits a typed `ApprovalRequest` to an external reviewer, and waits for a typed `ApprovalResponse` to resume execution.

## Microsoft Foundry Hosted Agent
NexDeal AI is deployed as a Hosted Agent on Microsoft Foundry.
- **Foundry Project:** `nexdeal-ai`
- **Model Deployment:** `gpt-4.1-mini`
- **Hosted Agent:** `nexdeal-ai` (Active version: 3)
- **Protocol:** Uses the standard Responses protocol.
- **Security:** The deployed Foundry Hosted Agent requires authenticated Azure/Entra access (via `DefaultAzureCredential`). No private endpoint credentials or secrets are published.

## Evaluation & Testing
The project includes a comprehensive offline testing and evaluation suite to validate deterministic behavior and agent safety:
- **30 Evaluation Scenarios:** Representing varied real-world edge cases.
- **466 Automated Tests:** Currently passing, covering unit boundaries and full pipeline validations.
- **Scope:** This represents project-level validation and testing, not a production benchmark.

## Demo UI
A browser-based demonstration application is available to interact with the deployed Hosted Agent.
- **Local FastAPI Proxy:** Handles secure server-side authentication with Azure Entra ID.
- **Browser Interface:** Provides an enterprise-grade UI to submit requests and view the resulting pipeline states and financial summaries.
- **Security:** The browser demo is intentionally local and proxies requests to the authenticated Foundry Hosted Agent.

## Live Demo Outcomes
The architecture defines four quotation decision states: QUOTE_READY, HUMAN_APPROVAL_REQUIRED, CUSTOMER_CLARIFICATION_REQUIRED, and REQUEST_CANNOT_BE_FULFILLED. The current live browser demonstration reliably reproduces the clarification and cannot-fulfilment paths.

*(Note: The current live browser interface does NOT fake approval continuation when the hosted response protocol does not expose the required continuation metadata. Green and orange states are handled correctly by the backend workflow, but full interactive hitl-continuation is limited in the UI).*

## Observability & Enterprise Foundations
NexDeal AI includes several enterprise-grade foundations:
- **Structured Hand-offs:** Strict Pydantic JSON schemas.
- **Deterministic Business Rules:** No LLM arithmetic.
- **HITL Boundary:** Native agent-framework pause/resume semantics.
- **Evaluation Framework:** Robust evaluation scenarios covering business logic edge cases.
- **Privacy-Aware Telemetry Configuration:** Foundations configured for safe Azure logging (not currently collecting production App Insights traces).
- **Hosted Agent Deployment:** Fully containerised deployment on Microsoft Foundry.

## Repository Structure

```text
NexDeal-AI/
├── app/
│   ├── agents/          # Agent implementations (Phases 3-6)
│   ├── evaluation/      # Evaluation metrics and runners
│   ├── models/          # Pydantic schemas (StructuredRequest, etc.)
│   ├── tools/           # Deterministic business tools
│   ├── workflows/       # Multi-agent graph orchestrator
│   └── host.py          # Foundry Hosted Agent entrypoint
├── data/                # Synthetic authoritative B2B datasets
├── demo/                # Local FastAPI demo UI and static assets
├── infra/               # Infrastructure configuration (azd)
├── scripts/             # Local execution and testing scripts
├── tests/               # 466 comprehensive Pytest tests
├── azure.yaml           # Azure Developer CLI deployment config
├── Dockerfile           # Hosted Agent container definition
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Getting Started

### Prerequisites
- Python 3.10+
- Windows PowerShell
- Azure CLI (`az login` must be authenticated to an account with access to the Foundry project)

### 1. Setup Environment
```powershell
# Activate virtual environment (ensure it is created first)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
```powershell
Copy-Item .env.example .env
```
Fill in `.env` with your `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL_NAME`, and `FOUNDRY_AGENT_RESPONSES_ENDPOINT`. (Never commit `.env`).

### 3. Run Tests
To run the full test suite (466 tests):
```powershell
pytest tests/ -v
```

### 4. Run the Local Demo
```powershell
.\.venv\Scripts\python.exe -m uvicorn demo.server:app --port 8000
```
Then navigate to http://localhost:8000 in your browser.

## Current Status
NexDeal AI is an enterprise-oriented MVP/prototype implemented and demonstrated with Microsoft Foundry, Hosted Agent deployment, four-agent orchestration, deterministic business tools, HITL workflow support, an evaluation framework, and a working web demo.
