"""Read-only MCP interface to PETRO-TWIN's existing operational data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from ml_service.config import config
from ml_service.persistence import AnalysisRepository

server = MCPServer(
    name="petro-twin-readonly",
    version="0.1.0",
    instructions=(
        "Read-only PETRO-TWIN data access. Distinguish measured records from "
        "synthetic/demo data. Never present model outputs as field-validated "
        "or operational instructions. No write, approval, activation, or dispatch tools exist."
    ),
)
repository = AnalysisRepository(config.database_url)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)


def _accessible_well(well_id: str) -> dict[str, Any]:
    """Return a configured well, rejecting demo profiles outside simulation mode."""
    well = repository.get_well(well_id)
    if well is None:
        raise ValueError(f"Unknown well_id: {well_id}")
    demo = well_id.upper().startswith("BW-DEMO-") or "demo well" in str(well.get("name", "")).lower()
    if config.data_mode != "simulation" and demo:
        raise ValueError("Synthetic development profiles are unavailable in field mode.")
    return well


def _iso_window(days: int) -> str:
    if not 1 <= days <= 3650:
        raise ValueError("days must be between 1 and 3650")
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@server.tool(annotations=READ_ONLY, structured_output=True)
def list_wells() -> dict[str, Any]:
    """List wells available in the current data mode; hides demo profiles in field mode."""
    wells = []
    for well in repository.list_wells():
        well_id = str(well.get("well_id", ""))
        demo = well_id.upper().startswith("BW-DEMO-") or "demo well" in str(well.get("name", "")).lower()
        if config.data_mode != "simulation" and demo:
            continue
        wells.append(well)
    return {"data_mode": config.data_mode, "count": len(wells), "wells": wells}


@server.tool(annotations=READ_ONLY, structured_output=True)
def get_well_configuration(well_id: str) -> dict[str, Any]:
    """Read the registered configuration for one accessible well."""
    return _accessible_well(well_id)


@server.tool(annotations=READ_ONLY, structured_output=True)
def get_measurements(
    well_id: str,
    days: int = 30,
    variable: str | None = None,
    quality_status: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Read recent measurements with timestamps, units, quality and provenance."""
    _accessible_well(well_id)
    if quality_status not in (None, "VALID", "SUSPECT"):
        raise ValueError("quality_status must be VALID, SUSPECT, or null")
    if not 1 <= limit <= 2000:
        raise ValueError("limit must be between 1 and 2000")
    records = repository.query_measurements(
        well_id, variable=variable, start_at=_iso_window(days),
        quality_status=quality_status, limit=limit,
    )
    return {"well_id": well_id, "days": days, "count": len(records), "records": records}


@server.tool(annotations=READ_ONLY, structured_output=True)
def get_data_quality(well_id: str, window_days: int = 30) -> dict[str, Any]:
    """Summarize measurement coverage, quality flags and stale variable types."""
    _accessible_well(well_id)
    start_at = _iso_window(window_days)
    records = repository.query_measurements(well_id, start_at=start_at, limit=10000)
    latest = repository.query_measurements(well_id, limit=10000)
    counts: dict[str, int] = {}
    latest_by_type: dict[str, dict[str, Any]] = {}
    for row in records:
        counts[row["variable"]] = counts.get(row["variable"], 0) + 1
    for row in latest:
        latest_by_type.setdefault(row["variable"], row)
    now = datetime.now(timezone.utc)
    stale = sorted(
        key for key, row in latest_by_type.items()
        if now - datetime.fromisoformat(row["measured_at"].replace("Z", "+00:00"))
        > timedelta(hours=24)
    )
    return {
        "well_id": well_id, "window_days": window_days, "record_count": len(records),
        "measurement_counts": counts, "stale_measurement_types": stale,
        "suspect_count": sum(row["quality_status"] != "VALID" for row in records),
        "readiness": "MEASUREMENTS_RECORDED_NOT_FIELD_MODEL_READY" if records else "NO_MEASUREMENTS",
        "calibration": "NOT_ESTABLISHED",
    }


@server.tool(annotations=READ_ONLY, structured_output=True)
def list_css_cycles(well_id: str) -> dict[str, Any]:
    """List recorded CSS cycles for an accessible well; does not infer missing cycles."""
    _accessible_well(well_id)
    cycles = repository.list_css_cycles(well_id)
    return {"well_id": well_id, "count": len(cycles), "cycles": cycles}


@server.tool(annotations=READ_ONLY, structured_output=True)
def list_srp_records(well_id: str, start_at: str | None = None, end_at: str | None = None) -> dict[str, Any]:
    """List recorded SRP operating records using optional timezone-aware ISO-8601 bounds."""
    _accessible_well(well_id)
    start = _parse_datetime(start_at, "start_at") if start_at else None
    end = _parse_datetime(end_at, "end_at") if end_at else None
    if start and end and end < start:
        raise ValueError("end_at must not precede start_at")
    records = repository.list_srp_records(
        well_id, start_at=start.isoformat() if start else None,
        end_at=end.isoformat() if end else None,
    )
    return {"well_id": well_id, "count": len(records), "records": records}


@server.tool(annotations=READ_ONLY, structured_output=True)
def list_operational_events(well_id: str, start_at: str | None = None, end_at: str | None = None) -> dict[str, Any]:
    """List recorded well events using optional timezone-aware ISO-8601 bounds."""
    _accessible_well(well_id)
    start = _parse_datetime(start_at, "start_at") if start_at else None
    end = _parse_datetime(end_at, "end_at") if end_at else None
    if start and end and end < start:
        raise ValueError("end_at must not precede start_at")
    events = repository.list_operational_events(
        well_id, start_at=start.isoformat() if start else None,
        end_at=end.isoformat() if end else None,
    )
    return {"well_id": well_id, "count": len(events), "events": events}


@server.tool(annotations=READ_ONLY, structured_output=True)
def list_data_sources() -> dict[str, Any]:
    """List registered ingestion sources and their recorded ingestion status."""
    sources = repository.list_data_sources()
    return {"count": len(sources), "sources": sources}


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


@server.resource(
    "petrotwin://domain/overview",
    name="PETRO-TWIN domain overview",
    description="Domain definitions and evidence limitations for CSS, SRP and the data mode.",
    mime_type="text/markdown",
)
def domain_overview() -> str:
    """Explain domain concepts and the distinction between measured and synthetic data."""
    return """# PETRO-TWIN domain overview

- CSS means Cyclic Steam Stimulation: steam heating changes the thermal state of a heavy-oil reservoir.
- SRP means Sucker Rod Pumping: a rod-lift system brings produced fluids to surface.
- The modeled coupling is CSS thermal state -> fluid viscosity -> SRP loading and modeled risk.
- Field-mode records are measured/registered data, but measurements alone do not validate a model.
- Synthetic demo wells and synthetic forecasts are not field evidence.
- Current field calibration, model uncertainty, and operational approval must be reported as not established unless explicit evidence says otherwise.
- This MCP server is read-only. It cannot write measurements, approve calibration, activate configurations, run control actions, or dispatch setpoints.
"""


@server.prompt(
    name="investigate_well_evidence",
    description="Create an evidence-first investigation plan for one PETRO-TWIN well.",
)
def investigate_well_evidence(well_id: str, question: str = "Assess current CSS/SRP evidence and data readiness.") -> str:
    """Guide an agent to inspect only traceable records and state evidence gaps."""
    return f"""Investigate well {well_id} for this question: {question}

Use the available read-only tools in this order:
1. Confirm the well exists and is accessible in the current data mode.
2. Read its registered configuration and measurement quality summary.
3. Retrieve relevant measurements, CSS cycle records, SRP records and operational events.
4. Cite measurement IDs, timestamps, units, quality flags and provenance in the result.
5. Separate directly observed facts, calculated summaries, assumptions and unavailable inputs.
6. Explicitly state that recorded measurements do not establish field calibration or model validity.
7. Do not invent missing values or recommend/dispatch operating setpoints.
"""


if __name__ == "__main__":
    repository.initialize()
    server.run(transport="stdio")
