"""Persistence boundary for wells, measurements, data sources, and saved analyses."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote


class AnalysisRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.is_postgres = database_url.startswith(("postgres://", "postgresql://"))
        if not self.is_postgres:
            if not database_url.startswith("sqlite:///"):
                raise ValueError("DATABASE_URL must use sqlite:/// or postgresql://")
            self.sqlite_path = Path(unquote(database_url[len("sqlite:///"):])).resolve()
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PostgreSQL configured but psycopg is not installed") from exc
            conn = psycopg.connect(self.database_url)
        else:
            conn = sqlite3.connect(self.sqlite_path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self.is_postgres else statement

    def initialize(self) -> None:
        with self._connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            version = row[0] or 0
            if version < 1:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS wells (well_id TEXT PRIMARY KEY, configuration_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS analysis_runs (run_id TEXT PRIMARY KEY, well_id TEXT NOT NULL, kind TEXT NOT NULL, source_mode TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                    "CREATE INDEX IF NOT EXISTS idx_analysis_runs_well_created ON analysis_runs(well_id, created_at)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"),
                             (1, datetime.now(timezone.utc).isoformat()))
            if version < 2:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS data_sources (source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, display_name TEXT NOT NULL, configured_at TEXT NOT NULL, last_ingested_at TEXT)",
                    "CREATE TABLE IF NOT EXISTS measurements (measurement_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), source_id TEXT NOT NULL REFERENCES data_sources(source_id), measured_at TEXT NOT NULL, variable TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, quality_status TEXT NOT NULL, external_id TEXT, provenance_json TEXT NOT NULL, UNIQUE(well_id, source_id, measured_at, variable))",
                    "CREATE INDEX IF NOT EXISTS idx_measurements_well_time ON measurements(well_id, measured_at)",
                    "CREATE INDEX IF NOT EXISTS idx_measurements_well_variable_time ON measurements(well_id, variable, measured_at)",
                    "CREATE TABLE IF NOT EXISTS ingestion_rejections (rejection_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, rejected_at TEXT NOT NULL, row_json TEXT NOT NULL, reason TEXT NOT NULL)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"),
                             (2, datetime.now(timezone.utc).isoformat()))
            if version < 3:
                conn.execute("CREATE TABLE IF NOT EXISTS twin_state_snapshots (snapshot_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), state_version INTEGER NOT NULL, created_at TEXT NOT NULL, window_start TEXT NOT NULL, window_end TEXT NOT NULL, payload_json TEXT NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_twin_snapshots_well_created ON twin_state_snapshots(well_id, created_at)")
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"),
                             (3, datetime.now(timezone.utc).isoformat()))
            if version < 4:
                conn.execute("CREATE TABLE IF NOT EXISTS well_physical_configurations (configuration_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), config_version INTEGER NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(well_id,config_version))")
                conn.execute("CREATE TABLE IF NOT EXISTS physics_execution_runs (run_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), snapshot_id TEXT NOT NULL, config_id TEXT, created_at TEXT NOT NULL, payload_json TEXT NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_physics_runs_well_created ON physics_execution_runs(well_id,created_at)")
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (4, datetime.now(timezone.utc).isoformat()))
            if version < 5:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS calibration_datasets (dataset_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), model_id TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
                    "CREATE INDEX IF NOT EXISTS idx_calibration_datasets_well_created ON calibration_datasets(well_id,created_at)",
                    "CREATE TABLE IF NOT EXISTS calibration_runs (calibration_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), dataset_id TEXT NOT NULL REFERENCES calibration_datasets(dataset_id), created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
                    "CREATE INDEX IF NOT EXISTS idx_calibration_runs_well_created ON calibration_runs(well_id,created_at)",
                    "CREATE TABLE IF NOT EXISTS calibration_candidates (candidate_id TEXT PRIMARY KEY, calibration_id TEXT NOT NULL UNIQUE REFERENCES calibration_runs(calibration_id), well_id TEXT NOT NULL REFERENCES wells(well_id), model_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
                    "CREATE INDEX IF NOT EXISTS idx_calibration_candidates_well_created ON calibration_candidates(well_id,created_at)",
                    "CREATE TABLE IF NOT EXISTS validation_runs (validation_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES calibration_candidates(candidate_id), dataset_id TEXT NOT NULL REFERENCES calibration_datasets(dataset_id), created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS validation_policies (model_id TEXT NOT NULL, policy_version INTEGER NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(model_id,policy_version))",
                    "CREATE TABLE IF NOT EXISTS calibration_candidate_events (event_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES calibration_candidates(candidate_id), created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (5, datetime.now(timezone.utc).isoformat()))
            if version < 6:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS css_cycles (cycle_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), cycle_number INTEGER NOT NULL, status TEXT NOT NULL, injection_start TEXT, production_restart TEXT, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(well_id,cycle_number), UNIQUE(well_id,fingerprint))",
                    "CREATE INDEX IF NOT EXISTS idx_css_cycles_well_time ON css_cycles(well_id,injection_start)",
                    "CREATE TABLE IF NOT EXISTS operational_events (event_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), cycle_id TEXT REFERENCES css_cycles(cycle_id), event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, external_id TEXT, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(well_id,fingerprint), UNIQUE(well_id,external_id))",
                    "CREATE INDEX IF NOT EXISTS idx_operational_events_well_time ON operational_events(well_id,occurred_at)",
                    "CREATE TABLE IF NOT EXISTS srp_operational_records (record_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), record_type TEXT NOT NULL, valid_at TEXT NOT NULL, external_id TEXT, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(well_id,fingerprint), UNIQUE(well_id,external_id))",
                    "CREATE INDEX IF NOT EXISTS idx_srp_records_well_time ON srp_operational_records(well_id,valid_at)",
                    "CREATE TABLE IF NOT EXISTS operational_measurement_links (link_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, measurement_id TEXT NOT NULL REFERENCES measurements(measurement_id), relation TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(entity_type,entity_id,measurement_id,relation))",
                    "CREATE INDEX IF NOT EXISTS idx_operational_links_entity ON operational_measurement_links(entity_type,entity_id)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (6, datetime.now(timezone.utc).isoformat()))
            if version < 7:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS auth_users (user_id TEXT PRIMARY KEY, username TEXT NOT NULL, username_normalized TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, is_active INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS auth_sessions (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES auth_users(user_id), issued_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT)",
                    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id,expires_at)",
                    "CREATE TABLE IF NOT EXISTS auth_audit_events (event_id TEXT PRIMARY KEY, user_id TEXT, action TEXT NOT NULL, resource TEXT NOT NULL, outcome TEXT NOT NULL, ip_address TEXT, correlation_id TEXT, created_at TEXT NOT NULL, details_json TEXT NOT NULL)",
                    "CREATE INDEX IF NOT EXISTS idx_auth_audit_created ON auth_audit_events(created_at)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (7, datetime.now(timezone.utc).isoformat()))
            if version < 8:
                conn.execute("CREATE TABLE IF NOT EXISTS agent_runs (run_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), actor_user_id TEXT, provider_model TEXT NOT NULL, status TEXT NOT NULL, prompt TEXT NOT NULL, answer TEXT NOT NULL, tool_trace_json TEXT NOT NULL, created_at TEXT NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_well_created ON agent_runs(well_id,created_at)")
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (8, datetime.now(timezone.utc).isoformat()))
            if version < 9:
                for statement in [
                    "CREATE TABLE IF NOT EXISTS model_registry (model_id TEXT PRIMARY KEY, well_id TEXT NOT NULL REFERENCES wells(well_id), model_family TEXT NOT NULL, horizon_days INTEGER NOT NULL, lifecycle_status TEXT NOT NULL, feature_schema_json TEXT NOT NULL, dataset_fingerprint TEXT NOT NULL, sample_count INTEGER NOT NULL, train_count INTEGER NOT NULL, validation_count INTEGER NOT NULL, test_count INTEGER NOT NULL, metrics_json TEXT NOT NULL, artifact_path TEXT, artifact_sha256 TEXT, created_at TEXT NOT NULL, approved_at TEXT, approved_by TEXT)",
                    "CREATE INDEX IF NOT EXISTS idx_model_registry_well_status ON model_registry(well_id,lifecycle_status,horizon_days,created_at)",
                ]:
                    conn.execute(statement)
                conn.execute(self._sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)"), (9, datetime.now(timezone.utc).isoformat()))

    def seed_wells(self, wells: dict[str, dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            for well_id, configuration in wells.items():
                conn.execute(
                    self._sql("INSERT INTO wells(well_id, configuration_json, created_at) VALUES (?, ?, ?) ON CONFLICT(well_id) DO NOTHING"),
                    (well_id, json.dumps(configuration, separators=(",", ":")), now),
                )

    def list_wells(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT well_id, configuration_json FROM wells ORDER BY well_id").fetchall()
        return [{"well_id": row[0], **json.loads(row[1])} for row in rows]

    def get_well(self, well_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                self._sql("SELECT configuration_json FROM wells WHERE well_id = ?"), (well_id,)
            ).fetchone()
        return {"well_id": well_id, **json.loads(row[0])} if row else None

    def create_well(self, well_id: str, configuration: dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                self._sql("INSERT INTO wells(well_id, configuration_json, created_at) VALUES (?, ?, ?)"),
                (well_id, json.dumps(configuration, separators=(",", ":")), datetime.now(timezone.utc).isoformat()),
            )

    def ingest_measurements(self, records: list[dict[str, Any]], source_id: str,
                            source_type: str, rejected: list[dict[str, str]]) -> dict[str, int | list[dict[str, str]]]:
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        duplicates = 0
        unknown_well_rejections: list[dict[str, str]] = []
        with self._connection() as conn:
            conn.execute(
                self._sql("INSERT INTO data_sources(source_id, source_type, display_name, configured_at, last_ingested_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(source_id) DO UPDATE SET last_ingested_at = excluded.last_ingested_at"),
                (source_id, source_type, source_id, now, now),
            )
            for record in records:
                exists = conn.execute(self._sql("SELECT 1 FROM wells WHERE well_id = ?"), (record["well_id"],)).fetchone()
                if not exists:
                    rejection = {"row": record.get("external_id") or record["well_id"], "reason": f"Unknown well_id: {record['well_id']}"}
                    unknown_well_rejections.append(rejection)
                    continue
                result = conn.execute(
                    self._sql("INSERT INTO measurements(measurement_id, well_id, source_id, measured_at, variable, value, unit, quality_status, external_id, provenance_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(well_id, source_id, measured_at, variable) DO NOTHING"),
                    (str(uuid.uuid4()), record["well_id"], source_id, record["measured_at"], record["variable"], record["value"], record["unit"], record["quality_status"], record.get("external_id"), json.dumps(record["provenance"], separators=(",", ":"))),
                )
                if result.rowcount == 1:
                    inserted += 1
                else:
                    duplicates += 1
            for rejection in rejected + unknown_well_rejections:
                conn.execute(
                    self._sql("INSERT INTO ingestion_rejections(rejection_id, source_id, rejected_at, row_json, reason) VALUES (?, ?, ?, ?, ?)"),
                    (str(uuid.uuid4()), source_id, now, json.dumps(rejection, separators=(",", ":")), rejection["reason"]),
                )
        return {"inserted": inserted, "duplicates": duplicates, "rejected": unknown_well_rejections}

    def list_measurements(self, well_id: str, days: int | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [well_id]
        where = "well_id = ?"
        if days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where += " AND measured_at >= ?"
            params.append(cutoff)
        with self._connection() as conn:
            rows = conn.execute(
                self._sql(f"SELECT measurement_id, well_id, source_id, measured_at, variable, value, unit, quality_status, provenance_json FROM measurements WHERE {where} ORDER BY measured_at ASC"),
                tuple(params),
            ).fetchall()
        return [{
            "measurement_id": row[0], "well_id": row[1], "source_id": row[2],
            "measured_at": row[3], "variable": row[4], "value": row[5],
            "unit": row[6], "quality_status": row[7], "provenance": json.loads(row[8]),
        } for row in rows]

    def query_measurements(self, well_id: str, *, variable: str | None = None,
                           start_at: str | None = None, end_at: str | None = None,
                           quality_status: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        clauses = ["well_id = ?"]
        params: list[Any] = [well_id]
        for column, value in (("variable =", variable), ("measured_at >=", start_at),
                              ("measured_at <=", end_at), ("quality_status =", quality_status)):
            if value is not None:
                clauses.append(f"{column} ?")
                params.append(value)
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(self._sql(
                "SELECT measurement_id,well_id,source_id,measured_at,variable,value,unit,quality_status,provenance_json "
                f"FROM measurements WHERE {' AND '.join(clauses)} ORDER BY measured_at DESC LIMIT ?"
            ), tuple(params)).fetchall()
        return [{"measurement_id": r[0], "well_id": r[1], "source_id": r[2], "measured_at": r[3],
                 "variable": r[4], "value": r[5], "unit": r[6], "quality_status": r[7],
                 "provenance": json.loads(r[8])} for r in rows]

    def save_twin_snapshot(self, well_id: str, window_start: str, window_end: str,
                           payload: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        with self._connection() as conn:
            row = conn.execute(self._sql("SELECT COALESCE(MAX(state_version),0)+1 FROM twin_state_snapshots WHERE well_id=?"), (well_id,)).fetchone()
            version = int(row[0])
            created_at = datetime.now(timezone.utc).isoformat()
            conn.execute(self._sql("INSERT INTO twin_state_snapshots(snapshot_id,well_id,state_version,created_at,window_start,window_end,payload_json) VALUES (?,?,?,?,?,?,?)"),
                         (snapshot_id, well_id, version, created_at, window_start, window_end, json.dumps(payload, separators=(",", ":"))))
        return {"snapshot_id": snapshot_id, "well_id": well_id, "state_version": version,
                "created_at": created_at, "window_start": window_start, "window_end": window_end, **payload}

    def get_twin_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql("SELECT snapshot_id,well_id,state_version,created_at,window_start,window_end,payload_json FROM twin_state_snapshots WHERE snapshot_id=?"), (snapshot_id,)).fetchone()
        if not row: return None
        return {"snapshot_id":row[0],"well_id":row[1],"state_version":row[2],"created_at":row[3],"window_start":row[4],"window_end":row[5],**json.loads(row[6])}

    def save_physical_configuration(self, well_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        config_id = str(uuid.uuid4()); now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            version = int(conn.execute(self._sql("SELECT COALESCE(MAX(config_version),0)+1 FROM well_physical_configurations WHERE well_id=?"), (well_id,)).fetchone()[0])
            versioned_payload = dict(payload)
            versioned_payload["parameters"] = {
                key: {**parameter, "configuration_version": version}
                for key, parameter in payload.get("parameters", {}).items()
            }
            conn.execute(self._sql("INSERT INTO well_physical_configurations(configuration_id,well_id,config_version,created_at,payload_json) VALUES (?,?,?,?,?)"), (config_id,well_id,version,now,json.dumps(versioned_payload,separators=(",",":"))))
        return {"configuration_id":config_id,"well_id":well_id,"config_version":version,"created_at":now,**versioned_payload}

    def get_physical_configuration(self, well_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT configuration_id,config_version,created_at,payload_json FROM well_physical_configurations WHERE well_id=? ORDER BY config_version DESC LIMIT 1"),(well_id,)).fetchone()
        return {"configuration_id":row[0],"well_id":well_id,"config_version":row[1],"created_at":row[2],**json.loads(row[3])} if row else None

    def get_physical_configuration_by_id(self, configuration_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT configuration_id,well_id,config_version,created_at,payload_json FROM well_physical_configurations WHERE configuration_id=?"),(configuration_id,)).fetchone()
        return {"configuration_id":row[0],"well_id":row[1],"config_version":row[2],"created_at":row[3],**json.loads(row[4])} if row else None

    def save_physics_run(self, well_id: str, snapshot_id: str, config_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        run_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO physics_execution_runs(run_id,well_id,snapshot_id,config_id,created_at,payload_json) VALUES (?,?,?,?,?,?)"),(run_id,well_id,snapshot_id,config_id,now,json.dumps(payload,separators=(",",":"))))
        return {"run_id":run_id,"well_id":well_id,"snapshot_id":snapshot_id,"configuration_id":config_id,"created_at":now,**payload}

    def get_physics_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT run_id,well_id,snapshot_id,config_id,created_at,payload_json FROM physics_execution_runs WHERE run_id=?"),(run_id,)).fetchone()
        return {"run_id":row[0],"well_id":row[1],"snapshot_id":row[2],"configuration_id":row[3],"created_at":row[4],**json.loads(row[5])} if row else None

    def list_physics_runs(self, well_id: str, limit: int=50) -> list[dict[str, Any]]:
        with self._connection() as conn:
            ids=conn.execute(self._sql("SELECT run_id FROM physics_execution_runs WHERE well_id=? ORDER BY created_at DESC LIMIT ?"),(well_id,limit)).fetchall()
        return [self.get_physics_run(row[0]) for row in ids]

    def save_calibration_dataset(self, payload: dict[str, Any]) -> dict[str, Any]:
        dataset_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO calibration_datasets(dataset_id,well_id,model_id,fingerprint,created_at,payload_json) VALUES (?,?,?,?,?,?)"),(dataset_id,payload["well_id"],payload["model_id"],payload["fingerprint"],now,json.dumps(payload,separators=(",",":"))))
        return {"dataset_id":dataset_id,"created_at":now,**payload}

    def get_calibration_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT dataset_id,created_at,payload_json FROM calibration_datasets WHERE dataset_id=?"),(dataset_id,)).fetchone()
        return {"dataset_id":row[0],"created_at":row[1],**json.loads(row[2])} if row else None

    def save_calibration(self, well_id: str, dataset_id: str, payload: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
        calibration_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO calibration_runs(calibration_id,well_id,dataset_id,created_at,payload_json) VALUES (?,?,?,?,?)"),(calibration_id,well_id,dataset_id,now,json.dumps(payload,separators=(",",":"))))
            if candidate is not None:
                candidate_id=str(uuid.uuid4()); candidate_payload={**candidate,"candidate_id":candidate_id,"calibration_id":calibration_id,"well_id":well_id,"created_at":now}
                conn.execute(self._sql("INSERT INTO calibration_candidates(candidate_id,calibration_id,well_id,model_id,status,created_at,payload_json) VALUES (?,?,?,?,?,?,?)"),(candidate_id,calibration_id,well_id,candidate_payload["model_id"],candidate_payload["lifecycle_status"],now,json.dumps(candidate_payload,separators=(",",":"))))
                for index, state in enumerate(("DRAFT", "CALIBRATION_COMPLETED", "VALIDATION_PENDING")):
                    event_id=str(uuid.uuid4()); event={"state":state,"event_type":"LIFECYCLE_TRANSITION","actor_authentication":"NOT_AVAILABLE"}
                    transition_at=(datetime.fromisoformat(now)+timedelta(microseconds=index)).isoformat()
                    conn.execute(self._sql("INSERT INTO calibration_candidate_events(event_id,candidate_id,created_at,payload_json) VALUES (?,?,?,?)"),(event_id,candidate_id,transition_at,json.dumps(event,separators=(",",":"))))
                payload={**payload,"candidate":candidate_payload}
                conn.execute(self._sql("UPDATE calibration_runs SET payload_json=? WHERE calibration_id=?"),(json.dumps(payload,separators=(",",":")),calibration_id))
        return {"calibration_id":calibration_id,"well_id":well_id,"dataset_id":dataset_id,"created_at":now,**payload}

    def get_calibration(self, calibration_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT calibration_id,well_id,dataset_id,created_at,payload_json FROM calibration_runs WHERE calibration_id=?"),(calibration_id,)).fetchone()
        return {"calibration_id":row[0],"well_id":row[1],"dataset_id":row[2],"created_at":row[3],**json.loads(row[4])} if row else None

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT candidate_id,payload_json FROM calibration_candidates WHERE candidate_id=?"),(candidate_id,)).fetchone()
        return {"candidate_id":row[0],**json.loads(row[1])} if row else None

    def update_candidate(self, candidate_id: str, payload: dict[str, Any], status: str) -> None:
        with self._connection() as conn:
            conn.execute(self._sql("UPDATE calibration_candidates SET status=?,payload_json=? WHERE candidate_id=?"),(status,json.dumps(payload,separators=(",",":")),candidate_id))
            row=conn.execute(self._sql("SELECT payload_json FROM calibration_runs WHERE calibration_id=?"),(payload["calibration_id"],)).fetchone()
            if row:
                run_payload=json.loads(row[0]); run_payload["candidate"]=payload
                conn.execute(self._sql("UPDATE calibration_runs SET payload_json=? WHERE calibration_id=?"),(json.dumps(run_payload,separators=(",",":")),payload["calibration_id"]))

    def list_candidates(self, well_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute(self._sql("SELECT payload_json FROM calibration_candidates WHERE well_id=? ORDER BY created_at DESC"),(well_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_validation_policy(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            version=int(conn.execute(self._sql("SELECT COALESCE(MAX(policy_version),0)+1 FROM validation_policies WHERE model_id=?"),(model_id,)).fetchone()[0])
            stored={**payload,"model_id":model_id,"policy_version":version,"created_at":now,"policy_origin":"OPERATOR_OR_RESEARCH_DEFINED_NOT_UNIVERSAL"}
            conn.execute(self._sql("INSERT INTO validation_policies(model_id,policy_version,created_at,payload_json) VALUES (?,?,?,?)"),(model_id,version,now,json.dumps(stored,separators=(",",":"))))
        return stored

    def get_validation_policy(self, model_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT payload_json FROM validation_policies WHERE model_id=? ORDER BY policy_version DESC LIMIT 1"),(model_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_validation_run(self, candidate_id: str, dataset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        validation_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO validation_runs(validation_id,candidate_id,dataset_id,created_at,payload_json) VALUES (?,?,?,?,?)"),(validation_id,candidate_id,dataset_id,now,json.dumps(payload,separators=(",",":"))))
        return {"validation_id":validation_id,"candidate_id":candidate_id,"dataset_id":dataset_id,"created_at":now,**payload}

    def get_validation_run(self, validation_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT validation_id,candidate_id,dataset_id,created_at,payload_json FROM validation_runs WHERE validation_id=?"),(validation_id,)).fetchone()
        return {"validation_id":row[0],"candidate_id":row[1],"dataset_id":row[2],"created_at":row[3],**json.loads(row[4])} if row else None

    def list_candidate_validation_runs(self, candidate_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute(self._sql("SELECT validation_id FROM validation_runs WHERE candidate_id=? ORDER BY created_at DESC"),(candidate_id,)).fetchall()
        return [self.get_validation_run(row[0]) for row in rows]

    def save_candidate_event(self, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO calibration_candidate_events(event_id,candidate_id,created_at,payload_json) VALUES (?,?,?,?)"),(event_id,candidate_id,now,json.dumps(payload,separators=(",",":"))))
        return {"event_id":event_id,"candidate_id":candidate_id,"created_at":now,**payload}

    def list_candidate_events(self, candidate_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute(self._sql("SELECT event_id,created_at,payload_json FROM calibration_candidate_events WHERE candidate_id=? ORDER BY created_at,event_id"),(candidate_id,)).fetchall()
        return [{"event_id":row[0],"candidate_id":candidate_id,"created_at":row[1],**json.loads(row[2])} for row in rows]

    def latest_measurements(self, well_id: str) -> dict[str, dict[str, Any]]:
        records = self.list_measurements(well_id)
        latest: dict[str, dict[str, Any]] = {}
        for record in records:
            latest[record["variable"]] = record
        return latest

    def _operational_exists(self, table: str, record_id: str) -> bool:
        if table not in {"css_cycles", "operational_events", "srp_operational_records"}:
            raise ValueError("Unsupported operational record table")
        with self._connection() as conn:
            return conn.execute(self._sql(f"SELECT 1 FROM {table} WHERE " + ("cycle_id" if table == "css_cycles" else "event_id" if table == "operational_events" else "record_id") + "=?"), (record_id,)).fetchone() is not None

    def save_css_cycle(self, payload: dict[str, Any], *, update: bool = False) -> dict[str, Any]:
        cycle_id = payload.get("cycle_id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        value = {**payload, "cycle_id": cycle_id}
        if update and not self._operational_exists("css_cycles", cycle_id):
            return None
        with self._connection() as conn:
            if update:
                conn.execute(self._sql("UPDATE css_cycles SET cycle_number=?,status=?,injection_start=?,production_restart=?,fingerprint=?,payload_json=? WHERE cycle_id=?"),
                    (value["cycle_number"], value["status"], value.get("injection_start"), value.get("production_restart"), value["fingerprint"], json.dumps(value,separators=(",",":")), cycle_id))
            else:
                conn.execute(self._sql("INSERT INTO css_cycles(cycle_id,well_id,cycle_number,status,injection_start,production_restart,fingerprint,created_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?)"),
                    (cycle_id,value["well_id"],value["cycle_number"],value["status"],value.get("injection_start"),value.get("production_restart"),value["fingerprint"],now,json.dumps(value,separators=(",",":"))))
        return {**value, "created_at": now}

    def get_css_cycle(self, cycle_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT payload_json,created_at FROM css_cycles WHERE cycle_id=?"),(cycle_id,)).fetchone()
        return {**json.loads(row[0]),"created_at":row[1]} if row else None

    def list_css_cycles(self, well_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute(self._sql("SELECT payload_json,created_at FROM css_cycles WHERE well_id=? ORDER BY COALESCE(injection_start,created_at),cycle_number"),(well_id,)).fetchall()
        return [{**json.loads(row[0]),"created_at":row[1]} for row in rows]

    def archive_operational_record(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        table, id_column = {"css_cycle": ("css_cycles", "cycle_id"), "operational_event": ("operational_events", "event_id"), "srp_record": ("srp_operational_records", "record_id")}.get(entity_type, (None, None))
        if table is None: raise ValueError("Unsupported operational entity type")
        now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row=conn.execute(self._sql(f"SELECT payload_json FROM {table} WHERE {id_column}=?"),(entity_id,)).fetchone()
            if row is None: return None
            payload=json.loads(row[0]); payload["archived_at"]=now
            if entity_type=="css_cycle": payload["status"]="ARCHIVED"; conn.execute(self._sql("UPDATE css_cycles SET status='ARCHIVED',payload_json=? WHERE cycle_id=?"),(json.dumps(payload,separators=(",",":")),entity_id))
            else: conn.execute(self._sql(f"UPDATE {table} SET payload_json=? WHERE {id_column}=?"),(json.dumps(payload,separators=(",",":")),entity_id))
        return payload

    def update_operational_event(self, event_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT created_at FROM operational_events WHERE event_id=?"),(event_id,)).fetchone()
            if row is None: return None
            conn.execute(self._sql("UPDATE operational_events SET well_id=?,cycle_id=?,event_type=?,occurred_at=?,external_id=?,fingerprint=?,payload_json=? WHERE event_id=?"),(payload["well_id"],payload.get("cycle_id"),payload["event_type"],payload["occurred_at"],payload.get("external_id"),payload["fingerprint"],json.dumps({**payload,"event_id":event_id},separators=(",",":")),event_id))
        return {**payload,"event_id":event_id,"created_at":row[0]}

    def update_srp_record(self, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT created_at FROM srp_operational_records WHERE record_id=?"),(record_id,)).fetchone()
            if row is None: return None
            conn.execute(self._sql("UPDATE srp_operational_records SET well_id=?,record_type=?,valid_at=?,external_id=?,fingerprint=?,payload_json=? WHERE record_id=?"),(payload["well_id"],payload["record_type"],payload["valid_at"],payload.get("external_id"),payload["fingerprint"],json.dumps({**payload,"record_id":record_id},separators=(",",":")),record_id))
        return {**payload,"record_id":record_id,"created_at":row[0]}

    def save_operational_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id=payload.get("event_id") or str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat(); value={**payload,"event_id":event_id}
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO operational_events(event_id,well_id,cycle_id,event_type,occurred_at,external_id,fingerprint,created_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?)"),
                (event_id,value["well_id"],value.get("cycle_id"),value["event_type"],value["occurred_at"],value.get("external_id"),value["fingerprint"],now,json.dumps(value,separators=(",",":"))))
        return {**value,"created_at":now}

    def get_operational_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT payload_json,created_at FROM operational_events WHERE event_id=?"),(event_id,)).fetchone()
        return {**json.loads(row[0]),"created_at":row[1]} if row else None

    def list_operational_events(self, well_id: str, *, start_at: str | None = None, end_at: str | None = None) -> list[dict[str, Any]]:
        clauses=["well_id=?"]; args=[well_id]
        if start_at: clauses.append("occurred_at>=?"); args.append(start_at)
        if end_at: clauses.append("occurred_at<=?"); args.append(end_at)
        with self._connection() as conn:
            rows=conn.execute(self._sql(f"SELECT payload_json,created_at FROM operational_events WHERE {' AND '.join(clauses)} ORDER BY occurred_at,event_id"),args).fetchall()
        return [{**json.loads(row[0]),"created_at":row[1]} for row in rows]

    def save_srp_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_id=payload.get("record_id") or str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat(); value={**payload,"record_id":record_id}
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO srp_operational_records(record_id,well_id,record_type,valid_at,external_id,fingerprint,created_at,payload_json) VALUES (?,?,?,?,?,?,?,?)"),
                (record_id,value["well_id"],value["record_type"],value["valid_at"],value.get("external_id"),value["fingerprint"],now,json.dumps(value,separators=(",",":"))))
        return {**value,"created_at":now}

    def get_srp_record(self, record_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row=conn.execute(self._sql("SELECT payload_json,created_at FROM srp_operational_records WHERE record_id=?"),(record_id,)).fetchone()
        return {**json.loads(row[0]),"created_at":row[1]} if row else None

    def list_srp_records(self, well_id: str, *, start_at: str | None = None, end_at: str | None = None) -> list[dict[str, Any]]:
        clauses=["well_id=?"]; args=[well_id]
        if start_at: clauses.append("valid_at>=?"); args.append(start_at)
        if end_at: clauses.append("valid_at<=?"); args.append(end_at)
        with self._connection() as conn:
            rows=conn.execute(self._sql(f"SELECT payload_json,created_at FROM srp_operational_records WHERE {' AND '.join(clauses)} ORDER BY valid_at,record_id"),args).fetchall()
        return [{**json.loads(row[0]),"created_at":row[1]} for row in rows]

    def link_measurement(self, well_id: str, entity_type: str, entity_id: str, measurement_id: str, relation: str) -> dict[str, Any]:
        link_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(self._sql("INSERT INTO operational_measurement_links(link_id,well_id,entity_type,entity_id,measurement_id,relation,created_at) VALUES (?,?,?,?,?,?,?)"),(link_id,well_id,entity_type,entity_id,measurement_id,relation,now))
        return {"link_id":link_id,"well_id":well_id,"entity_type":entity_type,"entity_id":entity_id,"measurement_id":measurement_id,"relation":relation,"created_at":now}

    def list_measurement_links(self, *, well_id: str | None = None, entity_type: str | None = None, entity_id: str | None = None) -> list[dict[str, Any]]:
        clauses=[]; args=[]
        for key,value in (("well_id",well_id),("entity_type",entity_type),("entity_id",entity_id)):
            if value is not None: clauses.append(f"{key}=?"); args.append(value)
        query="SELECT link_id,well_id,entity_type,entity_id,measurement_id,relation,created_at FROM operational_measurement_links"+(f" WHERE {' AND '.join(clauses)}" if clauses else "")+" ORDER BY created_at,link_id"
        with self._connection() as conn: rows=conn.execute(self._sql(query),args).fetchall()
        return [dict(zip(("link_id","well_id","entity_type","entity_id","measurement_id","relation","created_at"),row)) for row in rows]

    def list_data_sources(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT source_id, source_type, display_name, configured_at, last_ingested_at FROM data_sources ORDER BY source_id").fetchall()
        return [{"source_id": row[0], "source_type": row[1], "display_name": row[2],
                 "configured_at": row[3], "last_ingested_at": row[4],
                 "connection_status": "INGESTION_RECORDED" if row[4] else "CONFIGURED_NOT_CONNECTED"}
                for row in rows]

    def record_ingestion_rejections(self, source_id: str, rejected: list[dict[str, str]]) -> None:
        if not rejected:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            for rejection in rejected:
                conn.execute(
                    self._sql("INSERT INTO ingestion_rejections(rejection_id, source_id, rejected_at, row_json, reason) VALUES (?, ?, ?, ?, ?)"),
                    (str(uuid.uuid4()), source_id, now, json.dumps(rejection, separators=(",", ":")), rejection["reason"]),
                )

    def save_analysis(self, well_id: str, kind: str, payload: dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                self._sql("INSERT INTO analysis_runs(run_id, well_id, kind, source_mode, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)"),
                (run_id, well_id, kind, "SIMULATION", json.dumps(payload, separators=(",", ":")), now),
            )
        return run_id

    def list_analyses(self, well_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                self._sql("SELECT run_id, well_id, kind, source_mode, payload_json, created_at FROM analysis_runs WHERE well_id = ? ORDER BY created_at DESC LIMIT ?"),
                (well_id, limit),
            ).fetchall()
        return [{
            "run_id": row[0], "well_id": row[1], "kind": row[2],
            "source_mode": row[3], "result": json.loads(row[4]), "created_at": row[5]
        } for row in rows]

    # --- Authentication, sessions, and security audit ---
    def create_auth_user(self, user: dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                self._sql("INSERT INTO auth_users(user_id,username,username_normalized,password_hash,role,is_active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)"),
                (user["user_id"], user["username"], user["username_normalized"], user["password_hash"],
                 user["role"], int(user["is_active"]), user["created_at"], user["updated_at"]),
            )

    def get_auth_user_by_username(self, username_normalized: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT user_id,username,password_hash,role,is_active,created_at,updated_at FROM auth_users WHERE username_normalized=?"
            ), (username_normalized,)).fetchone()
        return ({"user_id":row[0],"username":row[1],"username_normalized":row[1].casefold(),
                 "password_hash":row[2],"role":row[3],"is_active":bool(row[4]),
                 "created_at":row[5],"updated_at":row[6]} if row else None)

    def get_auth_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT user_id,username,password_hash,role,is_active,created_at,updated_at FROM auth_users WHERE user_id=?"
            ), (user_id,)).fetchone()
        return ({"user_id":row[0],"username":row[1],"username_normalized":row[1].casefold(),
                 "password_hash":row[2],"role":row[3],"is_active":bool(row[4]),
                 "created_at":row[5],"updated_at":row[6]} if row else None)

    def list_auth_users(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT user_id,username,role,is_active,created_at,updated_at FROM auth_users ORDER BY username_normalized"
            ).fetchall()
        return [{"user_id":r[0],"username":r[1],"role":r[2],"is_active":bool(r[3]),
                 "created_at":r[4],"updated_at":r[5]} for r in rows]

    def update_auth_user(self, user_id: str, *, role: str | None = None,
                         is_active: bool | None = None, password_hash: str | None = None) -> None:
        updates = []
        values: list[Any] = []
        for column, value in (("role", role), ("is_active", int(is_active) if is_active is not None else None),
                              ("password_hash", password_hash)):
            if value is not None:
                updates.append(f"{column}=?")
                values.append(value)
        if not updates:
            return
        updates.append("updated_at=?")
        values.extend([datetime.now(timezone.utc).isoformat(), user_id])
        with self._connection() as conn:
            conn.execute(self._sql(f"UPDATE auth_users SET {','.join(updates)} WHERE user_id=?"), tuple(values))

    def create_auth_session(self, session: dict[str, str]) -> None:
        with self._connection() as conn:
            conn.execute(self._sql(
                "INSERT INTO auth_sessions(session_id,user_id,issued_at,expires_at,revoked_at) VALUES (?,?,?,?,NULL)"
            ), (session["session_id"], session["user_id"], session["issued_at"], session["expires_at"]))

    def get_auth_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT session_id,user_id,issued_at,expires_at,revoked_at FROM auth_sessions WHERE session_id=?"
            ), (session_id,)).fetchone()
        return ({"session_id":row[0],"user_id":row[1],"issued_at":row[2],
                 "expires_at":row[3],"revoked_at":row[4]} if row else None)

    def revoke_auth_session(self, session_id: str, revoked_at: str) -> None:
        with self._connection() as conn:
            conn.execute(self._sql(
                "UPDATE auth_sessions SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL"
            ), (revoked_at, session_id))

    def revoke_user_sessions(self, user_id: str, revoked_at: str) -> None:
        with self._connection() as conn:
            conn.execute(self._sql(
                "UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL"
            ), (revoked_at, user_id))

    def write_auth_audit_event(self, event: dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(self._sql(
                "INSERT INTO auth_audit_events(event_id,user_id,action,resource,outcome,ip_address,correlation_id,created_at,details_json) VALUES (?,?,?,?,?,?,?,?,?)"
            ), (event["event_id"], event.get("user_id"), event["action"], event.get("resource", ""),
                event["outcome"], event.get("ip_address"), event.get("correlation_id"),
                event["created_at"], json.dumps(event.get("details", {}), separators=(",", ":"))))

    def list_auth_audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(self._sql(
                "SELECT event_id,user_id,action,resource,outcome,ip_address,correlation_id,created_at,details_json "
                "FROM auth_audit_events ORDER BY created_at DESC LIMIT ?"
            ), (max(1, min(limit, 1000)),)).fetchall()
        return [{
            "event_id":r[0],"user_id":r[1],"action":r[2],"resource":r[3],"outcome":r[4],
            "ip_address":r[5],"correlation_id":r[6],"created_at":r[7],"details":json.loads(r[8])
        } for r in rows]

    def save_agent_run(self, run: dict[str, Any]) -> dict[str, Any]:
        value = {
            "run_id": run.get("run_id") or str(uuid.uuid4()),
            "created_at": run.get("created_at") or datetime.now(timezone.utc).isoformat(),
            **run,
        }
        with self._connection() as conn:
            conn.execute(self._sql(
                "INSERT INTO agent_runs(run_id,well_id,actor_user_id,provider_model,status,prompt,answer,tool_trace_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)"
            ), (value["run_id"], value["well_id"], value.get("actor_user_id"), value["provider_model"],
                value["status"], value["prompt"], value["answer"],
                json.dumps(value.get("tool_trace", []), separators=(",", ":"), default=str), value["created_at"]))
        return value

    def list_agent_runs(self, well_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(self._sql(
                "SELECT run_id,well_id,actor_user_id,provider_model,status,prompt,answer,tool_trace_json,created_at "
                "FROM agent_runs WHERE well_id=? ORDER BY created_at DESC LIMIT ?"
            ), (well_id, max(1, min(limit, 200)))).fetchall()
        return [{
            "run_id":r[0],"well_id":r[1],"actor_user_id":r[2],"provider_model":r[3],
            "status":r[4],"prompt":r[5],"answer":r[6],"tool_trace":json.loads(r[7]),"created_at":r[8]
        } for r in rows]

    def register_field_model(self, model: dict[str, Any]) -> dict[str, Any]:
        value = {
            "model_id": model.get("model_id") or str(uuid.uuid4()),
            "created_at": model.get("created_at") or datetime.now(timezone.utc).isoformat(),
            **model,
        }
        with self._connection() as conn:
            conn.execute(self._sql(
                "INSERT INTO model_registry(model_id,well_id,model_family,horizon_days,lifecycle_status,feature_schema_json,dataset_fingerprint,sample_count,train_count,validation_count,test_count,metrics_json,artifact_path,artifact_sha256,created_at,approved_at,approved_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ), (
                value["model_id"], value["well_id"], value["model_family"], value["horizon_days"],
                value["lifecycle_status"], json.dumps(value["feature_schema"], separators=(",", ":")),
                value["dataset_fingerprint"], value["sample_count"], value["train_count"],
                value["validation_count"], value["test_count"],
                json.dumps(value["metrics"], separators=(",", ":"), default=str),
                value.get("artifact_path"), value.get("artifact_sha256"), value["created_at"],
                value.get("approved_at"), value.get("approved_by"),
            ))
        return self.get_field_model(value["model_id"])

    def get_field_model(self, model_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT model_id,well_id,model_family,horizon_days,lifecycle_status,feature_schema_json,dataset_fingerprint,sample_count,train_count,validation_count,test_count,metrics_json,artifact_path,artifact_sha256,created_at,approved_at,approved_by FROM model_registry WHERE model_id=?"
            ), (model_id,)).fetchone()
        return self._field_model_row(row)

    def list_field_models(self, well_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(self._sql(
                "SELECT model_id,well_id,model_family,horizon_days,lifecycle_status,feature_schema_json,dataset_fingerprint,sample_count,train_count,validation_count,test_count,metrics_json,artifact_path,artifact_sha256,created_at,approved_at,approved_by FROM model_registry WHERE well_id=? ORDER BY created_at DESC LIMIT ?"
            ), (well_id, max(1, min(limit, 200)))).fetchall()
        return [self._field_model_row(row) for row in rows if row]

    def get_active_field_model(self, well_id: str, horizon_days: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT model_id,well_id,model_family,horizon_days,lifecycle_status,feature_schema_json,dataset_fingerprint,sample_count,train_count,validation_count,test_count,metrics_json,artifact_path,artifact_sha256,created_at,approved_at,approved_by FROM model_registry WHERE well_id=? AND horizon_days=? AND lifecycle_status='ACTIVE' ORDER BY approved_at DESC LIMIT 1"
            ), (well_id, horizon_days)).fetchone()
        return self._field_model_row(row)

    @staticmethod
    def _field_model_row(row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "model_id":row[0],"well_id":row[1],"model_family":row[2],"horizon_days":row[3],
            "lifecycle_status":row[4],"feature_schema":json.loads(row[5]),"dataset_fingerprint":row[6],
            "sample_count":row[7],"train_count":row[8],"validation_count":row[9],"test_count":row[10],
            "metrics":json.loads(row[11]),"artifact_path":row[12],"artifact_sha256":row[13],
            "created_at":row[14],"approved_at":row[15],"approved_by":row[16],
        }

    def promote_field_model(self, model_id: str, approved_by: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row = conn.execute(self._sql(
                "SELECT well_id,horizon_days,lifecycle_status FROM model_registry WHERE model_id=?"
            ), (model_id,)).fetchone()
            if row is None:
                raise KeyError("Field model not found")
            if row[2] != "CANDIDATE_REVIEW_REQUIRED":
                raise ValueError("Only candidates that beat the persistence baseline can be promoted")
            conn.execute(self._sql(
                "UPDATE model_registry SET lifecycle_status='SUPERSEDED' WHERE well_id=? AND horizon_days=? AND lifecycle_status='ACTIVE'"
            ), (row[0], row[1]))
            conn.execute(self._sql(
                "UPDATE model_registry SET lifecycle_status='ACTIVE',approved_at=?,approved_by=? WHERE model_id=?"
            ), (now, approved_by, model_id))
        return self.get_field_model(model_id)
