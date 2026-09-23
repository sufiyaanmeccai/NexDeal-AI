"""
app/host.py — NexDeal AI  |  Phase 11A

Minimal hosting adapter to expose the NexDeal multi-agent workflow
via the Foundry Invocations protocol.
"""

from agent_framework_foundry_hosting import ResponsesHostServer
from app.workflows.orchestrator import build_orchestration_workflow

# 1. Build the existing workflow
wf = build_orchestration_workflow()

# 2. Convert the workflow to a hosted agent
agent = wf.as_agent(name="nexdeal-ai-agent")

# 3. Mount into the Responses server (this is an ASGI application)
# ResponsesHostServer automatically uses Foundry-backed durable stores for checkpoints/HITL
app = ResponsesHostServer(agent)
