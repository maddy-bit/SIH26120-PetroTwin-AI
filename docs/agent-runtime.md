# MCP-backed industrial investigation agent

The active agent path is:

`React Copilot → FastAPI /api/v1/agent/investigate → AgentRuntime → MCP Client (stdio) → PETRO-TWIN read-only MCP Server → PostgreSQL/SQLite repository`

The agent retrieves well configuration, data quality, measurements, CSS cycles, SRP records, operational events and ingestion-source metadata before asking the configured LLM to synthesize the evidence. Follow-up model tool calls are limited to tools marked read-only and non-destructive by the MCP server. Runs, tool arguments, returned evidence, model identifier and final answer are persisted in `agent_runs`.

## Configure a model provider

The runtime accepts OpenAI-compatible Chat Completions APIs. Configure the following environment variables on the backend service:

- `PETROTWIN_AGENT_BASE_URL`: provider base URL, e.g. `https://api.openai.com/v1` or a trusted internal OpenAI-compatible endpoint.
- `PETROTWIN_AGENT_MODEL`: exact model identifier supported by that provider.
- `PETROTWIN_AGENT_API_KEY`: optional for local providers; required by most hosted providers. Store it as a secret, not in Git.
- `PETROTWIN_AGENT_TIMEOUT_SECONDS`: 10–180 seconds; default 60.
- `PETROTWIN_AGENT_MAX_TOOL_CALLS`: 7–12; default 8. Seven read-only calls are used for the initial evidence bundle.

Restart/redeploy the backend after setting variables. `GET /api/v1/agent/status` reports whether the provider is configured without returning the API key. Without a provider endpoint and model the agent fails closed with HTTP 503; it does not silently return a scripted answer.

## Agent API

- `GET /api/v1/agent/status`: configuration and read-only tool policy.
- `POST /api/v1/agent/investigate`: JSON body `{"well_id":"FIELD-001","question":"Assess the recorded CSS and SRP evidence.","days":30}`.
- `GET /api/v1/agent/runs?well_id=FIELD-001&limit=50`: persisted investigation history and tool traces.

The investigation endpoint requires the engineer/admin role in required-auth mode. Read-only tool calls cannot ingest, modify, approve, activate, or dispatch anything. The agent must distinguish measured records from synthetic data and must not present its response as operating guidance or field validation.

## IBM AssetOpsBench evaluation alignment

The run records expose the raw evidence and tool trace needed to build reproducible task evaluations. The initial PETRO-TWIN integration is an MCP-backed evidence agent, not a claim that the IBM AssetOpsBench benchmark suite has been installed or that an official AOB score has been achieved.

For an AOB-style evaluation, use fixed investigation scenarios and score task completion, tool correctness, evidence grounding, unsupported claims, abstention when required inputs are missing, trace reproducibility and human correction effort. Keep field and synthetic scenario results in separate cohorts. A benchmark pass is not a substitute for reservoir/pump engineering validation.
