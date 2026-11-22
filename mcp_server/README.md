# PETRO-TWIN MCP server

This repository includes a local, read-only Model Context Protocol server using the official Python MCP SDK 2.3.0.

## Capabilities

Tools:
- `list_wells`: wells accessible in the active data mode.
- `get_well_configuration`: registered configuration for one well.
- `get_measurements`: recent measurements with IDs, time, unit, quality and provenance.
- `get_data_quality`: coverage, suspect records, stale variable types and readiness.
- `list_css_cycles`: recorded CSS cycles.
- `list_srp_records`: recorded SRP operational records.
- `list_operational_events`: recorded well events.
- `list_data_sources`: registered ingestion sources and last-ingestion status.

Resource:
- `petrotwin://domain/overview`: CSS/SRP definitions and evidence limitations.

Prompt:
- `investigate_well_evidence`: evidence-first investigation workflow.

All tools are annotated read-only and non-destructive. The server has no measurement-ingestion, optimizer, calibration, candidate approval, configuration activation, or control-dispatch tool. Field mode hides synthetic `BW-DEMO-*` profiles. Outputs must not be interpreted as validated operating instructions.

## Local setup

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m mcp_server.server
```

The default repository data mode is field mode and the default database is `data/petrotwin.sqlite3`. On process startup, the repository applies its idempotent schema migrations but does not seed synthetic wells. The server tools remain read-only after startup.

## Codex connection

For this workstation, a local project-scoped `.codex/config.toml` was created and excluded from Git because it contains an absolute path to the local virtual-environment interpreter. Open this repository as a trusted Codex project and restart Codex. Verify with `codex mcp list` or `/mcp` in the Codex TUI.

For another checkout, create `.codex/config.toml` with the local virtual-environment Python executable as `command`, `args = ["-m", "mcp_server.server"]`, and the repository root as `cwd`. The server uses local stdio; it does not need a public network listener or API key.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mcp_server -v
```

The tests use a temporary SQLite database and do not read or modify real well records.
