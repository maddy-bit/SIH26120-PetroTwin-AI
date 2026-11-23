# PETRO-TWIN industrial investigation agent

## Runtime architecture

The active LLM agent path is:

`React Copilot → FastAPI /api/v1/agent/investigate → AgentRuntime → MCP Client (stdio) → read-only PETRO-TWIN MCP server → shared repository → configured OpenAI-compatible model`.

The previous `agent/agent_supervisor.py` remains a deterministic simulator-only workflow for demo operations and finite-grid optimization. It is not the LLM agent. The measured-evidence investigation agent is `agent/agent_runtime.py`.

## Evidence retrieval and tool safety

Before synthesis, the agent retrieves:
- selected well configuration;
- quality summary for the requested observation window;
- measurements with timestamps, units and provenance;
- registered CSS cycles;
- SRP records;
- operational events;
- registered data-source metadata.

It launches the project's MCP server through stdio using the same configured SQLite/PostgreSQL repository. Candidate MCP tools are filtered using the read-only and non-destructive annotations. Every call is checked against this allowlist again before execution. The server exposes no ingestion, mutation, approval, optimizer activation or setpoint-dispatch tool.

The model prompt requires separation of measured evidence, assumptions, simulated values, estimates and missing evidence. It must not claim field calibration from an ingested record set. The agent records model ID, tool arguments, evidence outputs, durations and final answer in `agent_runs`.

## Provider setup

The agent uses an OpenAI-compatible chat-completions API. Set the following variables on the backend:
- `PETROTWIN_AGENT_BASE_URL`: provider base URL, such as an API's `/v1` endpoint or trusted internal local model endpoint.
- `PETROTWIN_AGENT_MODEL`: exact supported model name.
- `PETROTWIN_AGENT_API_KEY`: optional for local providers, normally required for hosted providers.
- `PETROTWIN_AGENT_TIMEOUT_SECONDS`: 10–180 seconds.
- `PETROTWIN_AGENT_MAX_TOOL_CALLS`: 7–12; the first seven are the mandatory evidence retrieval calls.

The key must be injected through a secret manager or protected runtime environment. It is never returned by the status endpoint. If provider configuration is absent, the investigation endpoint returns HTTP 503; it does not generate a scripted answer and present it as an LLM result.

## API

- `GET /api/v1/agent/status`: reports configuration state and the read-only tool policy.
- `POST /api/v1/agent/investigate`: `{"well_id":"FIELD-001","question":"Summarize the measured thermal and SRP evidence.","days":30}`.
- `GET /api/v1/agent/runs?well_id=FIELD-001&limit=50`: persisted investigation runs and evidence traces.

In required-auth mode, investigation is restricted to the engineer/admin roles. Browsing evidence is not an operational authorization. The agent cannot dispatch setpoints or perform write operations.

## IBM AssetOpsBench evaluation alignment

Persisted runs provide the evidence and tool trace needed to create repeatable industrial-agent tasks. Evaluation dimensions should include task completion, evidence correctness, tool selection/call correctness, unsupported claims, abstention under missing inputs, trace reproducibility, and human correction effort. Synthetic and measured-data task cohorts must be evaluated separately.

This implementation is an MCP-backed PETRO-TWIN investigation agent. It is **not** an assertion that the official IBM AssetOpsBench benchmark suite has been integrated or that an official benchmark score has been earned.
